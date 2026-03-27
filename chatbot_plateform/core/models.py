import os

from django.db import models
from django.contrib.auth.models import User

class Chatbot(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom du chatbot"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Description courte pour l'admin"
    )
    system_prompt = models.TextField(
        blank=True,
        verbose_name="Prompt système",
        help_text="Instructions pour le LLM. Ex: Tu es AlloGaz, assistant spécialisé en livraison de gaz. Réponds dans la langue de l'utilisateur."
    )
    llm_model = models.CharField(
        max_length=100,
        default='mistral',
        verbose_name="Modèle LLM",
        help_text="Ex: mistral, llama3, phi3"
    )
    active = models.BooleanField(
        default=True,
        verbose_name="Actif"
    )

    # ← NOUVEAU : ce chatbot est assigné automatiquement aux nouveaux clients
    is_default = models.BooleanField(
        default=False,
        verbose_name="Chatbot par défaut",
        help_text="Si coché, ce chatbot sera automatiquement assigné à tout nouveau client lors de sa première connexion"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Créé le"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Modifié le"
    )

    class Meta:
        verbose_name = "Chatbot"
        verbose_name_plural = "Chatbots"
        ordering = ['name']

    def __str__(self):
        status = "Actif" if self.active else "Inactif"
        return f"{self.name} ({status})"


class DatabaseConfig(models.Model):
    DB_TYPES = [
        ('gaz',       'Gaz'),
        ('carburant', 'Carburant'),
        ('stations',  'Stations'),
        ('general',   'Général'),
    ]

    chatbot = models.ForeignKey(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='database_configs',   
        verbose_name="Chatbot"
    )
    name = models.CharField(
        max_length=100,
        default='DB principale',
        verbose_name="Nom de la configuration",
        help_text="Ex: Base commandes AlloGaz, Base stations Maroc"
    )
    
    db_engine = models.CharField(
        max_length=20,
        choices=[
            ('postgresql', 'PostgreSQL'),
            ('mysql',      'MySQL'),
            ('sqlite',     'SQLite'),
        ],
        default='postgresql',
        verbose_name="Moteur de base de données"
    )
    db_name = models.CharField(
        max_length=100,
        verbose_name="Nom de la base de données"
    )
    host = models.CharField(
        max_length=255,
        default='localhost',
        verbose_name="Hôte"
    )
    port = models.IntegerField(
        default=5432,
        verbose_name="Port"
    )
    username = models.CharField(
        max_length=100,
        verbose_name="Utilisateur DB"
    )
    password = models.CharField(
        max_length=255,
        verbose_name="Mot de passe DB"
    )
    allowed_tables = models.JSONField(
        default=list,
        verbose_name="Tables autorisées",
        help_text='Ex: ["stations", "fuel_stock", "prices"]'
    )
    db_type = models.CharField(
        max_length=20,
        choices=DB_TYPES,
        default='general',
        verbose_name="Type de données"
    )

    active = models.BooleanField(       
        default=True,
        verbose_name="Active"
    )

    class Meta:
        verbose_name = "Configuration DB"
        verbose_name_plural = "Configurations DB"

    def __str__(self):
        return f"DB Config de {self.chatbot.name} → {self.db_name}"


def document_upload_path(instance, filename):
    # Sauvegarde dans : media/documents/nom_chatbot/fichier.pdf
    return f'documents/{instance.chatbot.name}/{filename}'


class Document(models.Model):
    DOC_TYPES = [
        ('pdf',      'PDF'),
        ('word',     'Word (.docx)'),
        ('txt',      'Texte (.txt)'),
        ('csv',      'CSV'),
    ]

    chatbot = models.ForeignKey(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name="Chatbot"
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Titre du document"
    )
    file = models.FileField(
        upload_to=document_upload_path,
        verbose_name="Fichier"
    )
    doc_type = models.CharField(
        max_length=10,
        choices=DOC_TYPES,
        verbose_name="Type de document"
    )
    # Status du pipeline RAG
    is_processed = models.BooleanField(
        default=False,
        verbose_name="Traité (indexé dans Qdrant)",
        help_text="Devient True après chunking et embedding"
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Uploadé le"
    )

    class Meta:
        verbose_name = "Document RAG"
        verbose_name_plural = "Documents RAG"
        ordering = ['-uploaded_at']

    def __str__(self):
        status = "✓ Indexé" if self.is_processed else "⏳ En attente"
        return f"{self.title} — {self.chatbot.name} [{status}]"

    def filename(self):
        return os.path.basename(self.file.name)
    
    
class AgentConfig(models.Model):
    AGENT_TYPES = [
        ('sql',        'SQL Agent'),
        ('rag',        'RAG Agent'),
        ('arithmetic', 'Arithmetic Agent'),
        ('custom',     'Agent personnalisé'),
    ]

    LLM_CHOICES = [
        ('qwen3:8b', 'qwen3:8b  — Logique & SQL'),
        ('gemma3',   'gemma3   — RAG & Génération NL'),
        ('phi4',     'phi4     — Calculs & Tâches légères'),
    ]

    chatbot = models.ForeignKey(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='agents',
        verbose_name="Chatbot"
    )
    agent_type = models.CharField(
        max_length=50,
        choices=AGENT_TYPES,
        verbose_name="Type d'agent"
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name="Activé"
    )
    priority = models.IntegerField(
        default=1,
        verbose_name="Priorité",
        help_text="Ordre d'appel des agents. 1 = premier"
    )

    llm_model = models.CharField(
        max_length=100,
        choices=LLM_CHOICES,
        default='qwen3:8b',
        verbose_name="Modèle LLM",
        help_text="Modèle utilisé par cet agent spécifiquement"
    )
    agent_prompt = models.TextField(
        blank=True,
        verbose_name="Prompt technique de l'agent",
        help_text="Instructions techniques spécifiques à cet agent. "
            "Ex pour SQL: 'Génère uniquement des SELECT. Tables autorisées: {tables}'"
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuration spécifique",
        help_text='Ex: {"max_rows": 100, "timeout": 30}'
    )

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"
        unique_together = ['chatbot', 'agent_type']
        ordering = ['priority']

    def __str__(self):
        status = "ON" if self.enabled else "OFF"
        return f"{self.agent_type} — {self.chatbot.name} [{status}]"


class Scope(models.Model):
    chatbot = models.OneToOneField(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='scope',
        verbose_name="Chatbot"
    )
    max_response_length = models.IntegerField(
        default=500,
        verbose_name="Longueur max réponse (tokens)"
    )
    response_style = models.CharField(
        max_length=20,
        choices=[
            ('concise',  'Concis'),
            ('formal',   'Formel'),
            ('friendly', 'Friendly'),
        ],
        default='concise',
        verbose_name="Style de réponse"
    )

    class Meta:
        verbose_name = "Scope (Paramètres)"
        verbose_name_plural = "Scopes (Paramètres)"

    def __str__(self):
        return f"Scope {self.chatbot.name}"


class ConversationMemory(models.Model):
    user_id = models.CharField(
        max_length=255,
        verbose_name="ID Utilisateur"
    )
    chatbot = models.ForeignKey(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='memories',
        verbose_name="Chatbot"
    )
    key = models.CharField(
        max_length=100,
        verbose_name="Clé",
        help_text='Ex: fuel_type, location, quantity'
    )
    value = models.TextField(
        verbose_name="Valeur",
        help_text='Ex: diesel, Maarif, 3'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Mis à jour le"
    )

    class Meta:
        verbose_name = "Mémoire Conversation"
        verbose_name_plural = "Mémoires Conversations"
        unique_together = ['user_id', 'chatbot', 'key']
        ordering = ['-updated_at']

    def __str__(self):
        return f"User {self.user_id} | {self.chatbot.name} | {self.key} = {self.value}"
    


class UserProfile(models.Model):
    ROLES = [
        ('admin',  '🔴 Administrateur'),
        ('editor', '🟡 Éditeur'),
        ('viewer', '⚪ Lecteur'),
    ]
    user             = models.OneToOneField(User, on_delete=models.CASCADE)
    role             = models.CharField(max_length=20, choices=ROLES, default='viewer')
    allowed_chatbots = models.ManyToManyField('Chatbot', blank=True)

    keycloak_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        verbose_name="UUID Keycloak",
        help_text="Le 'sub' du JWT Keycloak — copié depuis la console Keycloak → Users → ID"
    )

    class Meta:
        verbose_name = "Profil utilisateur"

    def __str__(self):
        return f"{self.user.username} — {self.role}"
    
