from django.db import models
from django.core.validators import URLValidator

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
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    role = models.TextField(
        help_text="System prompt defining the chatbot's role and behavior"
    )
    scope = models.TextField(
        help_text="Guardrails and boundaries for the chatbot",
        blank=True
    )
    base_model = models.CharField(
        max_length=100,
        choices=MODEL_CHOICES,
        default='qwen3:8b'
    )
    
    # Module activation flags
    sql_enabled = models.BooleanField(default=False)
    rag_enabled = models.BooleanField(default=False)
    action_enabled = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
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
    connection_string = models.CharField(
        max_length=1024,
        help_text="Database connection URI (e.g., 'sqlite:///path/to/db.sqlite')"
    )
    llm = models.CharField(
        max_length=100,
        choices=Chatbot.MODEL_CHOICES,
        default='Qwen/Qwen2.5-7B-Instruct',
        help_text="LLM used by SQL agent for this connection"
    )
    is_active = models.BooleanField(default=True)
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
        """Alias for connection_string to match microservice API"""
        return self.connection_string


class RAGAgent(models.Model):
    """RAG Agent configuration"""
    
    chatbot = models.OneToOneField(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='rag_config'
    )
    use_reranker = models.BooleanField(
        default=False,
        help_text="Enable semantic reranking of retrieved documents"
    )
    use_query_expansion = models.BooleanField(
        default=False,
        help_text="Expand queries with synonyms and related terms"
    )
    top_k = models.IntegerField(
        default=5,
        help_text="Number of top documents to retrieve"
    )
    embedding_model = models.CharField(
        max_length=255,
        default='sentence-transformers/all-MiniLM-L6-v2'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'RAG Configuration'
        verbose_name_plural = 'RAG Configurations'
    
    def __str__(self):
        return f"RAG Config - {self.chatbot.name}"


class DocumentReference(models.Model):
    """Document references for RAG agent"""

    DOC_TYPE_CHOICES = [
        ('fiche_technique', 'Fiche Technique'),
        ('faq', 'FAQ'),
        ('manual', 'Manual'),
        ('report', 'Report'),
        ('guide', 'Guide'),
        ('other', 'Other'),
    ]

    rag_agent = models.ForeignKey(
        RAGAgent,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    name = models.CharField(max_length=255)
    doc_type = models.CharField(
        max_length=50,
        choices=DOC_TYPE_CHOICES,
        default='other',
        help_text="Type of document for RAG classification"
    )
    file_path = models.CharField(max_length=1024, blank=True)
    url = models.URLField(blank=True, validators=[URLValidator()])
    content_type = models.CharField(max_length=100, blank=True)
    is_indexed = models.BooleanField(default=False)
    chunks_indexed = models.IntegerField(
        default=0,
        help_text="Number of chunks indexed by RAG agent"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Document Reference'
        verbose_name_plural = 'Document References'

    def __str__(self):
        return self.name


class ActionAgent(models.Model):
    """Action/Tool definitions for the chatbot"""
    
    METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
        ('PATCH', 'PATCH'),
    ]
    
    chatbot = models.ForeignKey(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='actions'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(
        help_text="Description of what this action does"
    )
    endpoint = models.URLField(
        max_length=1024,
        validators=[URLValidator()]
    )
    method = models.CharField(
        max_length=10,
        choices=METHOD_CHOICES,
        default='POST'
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="HTTP headers as JSON object"
    )
    payload_template = models.JSONField(
        default=dict,
        blank=True,
        help_text="Request payload template"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Action'
        verbose_name_plural = 'Actions'

    def __str__(self):
        return f"{self.chatbot.name} - {self.name}"