from django.db import models
from django.core.validators import URLValidator
from django.contrib.auth.models import User

class Chatbot(models.Model):
    """Main orchestrator model for chatbot configuration"""

    MODEL_CHOICES = [
        ('qwen3:8b', 'Qwen3:8b'),
        ('qwen2.5:7b', 'Qwen2.5:7b'),
        ('Qwen/Qwen2.5-7B-Instruct', 'Qwen/Qwen2.5-7B-Instruct'),
        ('Qwen/Qwen3-Coder-32B-Instruct', 'Qwen/Qwen3-Coder-32B-Instruct'),
        ('gemma3', 'Gemma3'),
        ('phi4', 'Phi4'),
        ('llama3.2:3b', 'Llama 3.2 3B'),
        ('llama-3.3-70b-versatile', 'Llama 3.3 70B (Groq)'),
    ]

    name        = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    role        = models.TextField(
        help_text="System prompt définissant le rôle et le comportement du chatbot"
    )
    scope = models.TextField(
        help_text="Guardrails et limites du chatbot",
        blank=True
    )
    base_model = models.CharField(
        max_length=100,
        choices=MODEL_CHOICES,
        default='qwen3:8b'
    )

    # Module activation flags
    sql_enabled    = models.BooleanField(default=False)
    rag_enabled    = models.BooleanField(default=False)
    action_enabled = models.BooleanField(default=False)

    weather_enabled = models.BooleanField(
        default=False,
        verbose_name="Weather Agent",
        help_text="Activer l'agent météo (température, pluie, vent)"
    )
    location_enabled = models.BooleanField(
        default=False,
        verbose_name="Location Agent", 
        help_text="Activer l'agent de géolocalisation (station la plus proche)"
    )

    # SQL Agent LLM configuration (global for all connections)
    sql_llm = models.CharField(
        max_length=100,
        choices=MODEL_CHOICES,
        default='Qwen/Qwen2.5-7B-Instruct',
        help_text="LLM utilisé par l'agent SQL pour toutes les connexions",
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        ordering     = ['-created_at']
        verbose_name = 'Chatbot'
        verbose_name_plural = 'Chatbots'

    def __str__(self):
        return self.name


class SQLAgent(models.Model):
    """SQL Agent configuration with multiple database connections"""

    DB_TYPE_CHOICES = [
        ('postgresql', 'PostgreSQL'),
        ('mysql', 'MySQL'),
        ('sqlite', 'SQLite'),
        ('mssql', 'Microsoft SQL Server'),
        ('oracle', 'Oracle'),
    ]
    
    chatbot = models.ForeignKey(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='sql_connections'
    )
    name = models.CharField(
        max_length=255,
        help_text="Connection identifier (e.g., 'flight_db_01')"
    )
    db_name = models.CharField(
        max_length=255,
        help_text="Human-readable database name (e.g., 'Global Flight Operations')"
    )
    db_type = models.CharField(max_length=50, choices=DB_TYPE_CHOICES)
    
    host = models.CharField(max_length=255, blank=True, null=True)
    port = models.IntegerField(blank=True, null=True)
    database = models.CharField(max_length=255, blank=True, null=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    
    sqlite_path = models.CharField(max_length=1024, blank=True, null=True)
    
    connection_string = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Legacy connection URI (auto-generated from individual fields)"
    )
    
    llm = models.CharField(
        max_length=100,
        choices=Chatbot.MODEL_CHOICES,
        default='Qwen/Qwen2.5-7B-Instruct',
        help_text="(Deprecated - use chatbot.sql_llm instead)",
        blank=True,
        null=True
    )
    is_active = models.BooleanField(default=True)
    agent_description = models.TextField(
        blank=True,
        default="",
        help_text="Schéma DB, mapping codes produits, règles SQL. Utilisé par l'orchestrateur."
    ) 
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'SQL Connection'
        verbose_name_plural = 'SQL Connections'

    def __str__(self):
        return f"{self.chatbot.name} - {self.db_name}"

    @property
    def db_id(self):
        """Returns unique identifier for SQL Agent microservice"""
        return f"{self.chatbot.name}_{self.name}".replace(" ", "_").lower()

    @property
    def connection_uri(self):
        """Build connection URI from individual fields"""
        if self.db_type == 'sqlite':
            return f"sqlite:///{self.sqlite_path}" if self.sqlite_path else ""
        
        auth = f"{self.username}:{self.password}@" if self.username and self.password else ""
        if self.username and not self.password:
            auth = f"{self.username}@"
        
        return f"{self.db_type}://{auth}{self.host}:{self.port}/{self.database}"
    
    def save(self, *args, **kwargs):
        """Auto-generate connection_string from individual fields for compatibility"""
        if self.db_type == 'sqlite' and self.sqlite_path:
            self.connection_string = f"sqlite:///{self.sqlite_path}"
        elif self.db_type != 'sqlite' and self.host and self.port and self.database:
            self.connection_string = self.connection_uri
        super().save(*args, **kwargs)


class RAGAgent(models.Model):
    """RAG Agent — configuration de la recherche documentaire"""

    chatbot = models.OneToOneField(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='rag_config'
    )

    # ── NOUVEAU ──────────────────────────────────────────────────────────────
    agent_description = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Décris les documents indexés dans ce RAG. "
            "Utilisé par le router pour choisir cet agent. "
            "Ex: 'Contient les fiches techniques huiles moteur (Qualix, Havoline, Delo), "
            "normes API/ACEA, spécifications viscosité et guides d\\'utilisation.'"
        )
    )
    # ─────────────────────────────────────────────────────────────────────────

    use_reranker       = models.BooleanField(
        default=False,
        help_text="Activer le reranking sémantique des documents récupérés"
    )
    use_query_expansion = models.BooleanField(
        default=False,
        help_text="Étendre les requêtes avec synonymes et termes associés"
    )
    top_k = models.IntegerField(
        default=5,
        help_text="Nombre de documents à récupérer"
    )
    embedding_model = models.CharField(
        max_length=255,
        default='sentence-transformers/all-MiniLM-L6-v2'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration RAG'
        verbose_name_plural = 'Configurations RAG'

    def __str__(self):
        return f"RAG Config — {self.chatbot.name}"


class DocumentReference(models.Model):
    """Documents indexés dans le RAG"""

    DOC_TYPE_CHOICES = [
        ('fiche_technique', 'Fiche Technique'),
        ('faq',             'FAQ'),
        ('manual',          'Manual'),
        ('report',          'Report'),
        ('guide',           'Guide'),
        ('other',           'Other'),
    ]

    rag_agent    = models.ForeignKey(
        RAGAgent,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    name         = models.CharField(max_length=255)
    doc_type     = models.CharField(
        max_length=50,
        choices=DOC_TYPE_CHOICES,
        default='other',
        help_text="Type de document pour la classification RAG"
    )
    file_path    = models.CharField(max_length=1024, blank=True)
    url          = models.URLField(blank=True, validators=[URLValidator()])
    content_type = models.CharField(max_length=100, blank=True)
    is_indexed   = models.BooleanField(default=False)
    chunks_indexed = models.IntegerField(
        default=0,
        help_text="Nombre de chunks indexés"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ['name']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return self.name


class ActionAgent(models.Model):
    """Actions / outils externes"""

    METHOD_CHOICES = [
        ('GET',    'GET'),
        ('POST',   'POST'),
        ('PUT',    'PUT'),
        ('DELETE', 'DELETE'),
        ('PATCH',  'PATCH'),
    ]

    chatbot = models.ForeignKey(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='actions'
    )
    name = models.CharField(max_length=255)

    # ── NOUVEAU ──────────────────────────────────────────────────────────────
    # Ce champ existait déjà sur ActionAgent — on améliore juste son help_text
    description = models.TextField(
        help_text=(
            "Décris ce que fait cette action ET quand le router doit l'utiliser. "
            "Ex: 'Envoie une notification SMS au client. À utiliser quand l\\'utilisateur "
            "demande un rappel, une confirmation ou un code de vérification.'"
        )
    )
    # ─────────────────────────────────────────────────────────────────────────

    endpoint         = models.URLField(max_length=1024, validators=[URLValidator()])
    method           = models.CharField(max_length=10, choices=METHOD_CHOICES, default='POST')
    headers          = models.JSONField(default=dict, blank=True)
    payload_template = models.JSONField(default=dict, blank=True)
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ['name']
        verbose_name = 'Action'
        verbose_name_plural = 'Actions'

    def __str__(self):
        return f"{self.chatbot.name} — {self.name}"

class UserProfile(models.Model):
    """
    Extends the built-in User model to track which chatbots each user
    is allowed to access.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='User'
    )
    chatbots = models.ManyToManyField(
        Chatbot,
        blank=True,
        related_name='allowed_users',
        verbose_name='Assigned Chatbots'
    )
    supabase_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
 
    def __str__(self):
        return f"Profile – {self.user.email}"
    
    def get_supabase_id(self):
        """Retourne le supabase_id ou None s'il n'existe pas."""
        return self.supabase_id

    # AJOUTER CETTE MÉTHODE
    def set_supabase_id(self, supabase_id):
        """Définit le supabase_id et sauvegarde."""
        self.supabase_id = supabase_id
        self.save(update_fields=['supabase_id'])

    # AJOUTER CETTE MÉTHODE
    def has_supabase_sync(self):
        """Vérifie si l'utilisateur est synchronisé avec Supabase."""
        return bool(self.supabase_id)