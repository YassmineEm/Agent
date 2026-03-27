from django.contrib import admin
from .models import Chatbot, DatabaseConfig, AgentConfig, Scope, ConversationMemory, Document
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserProfile

class DatabaseConfigInline(admin.TabularInline):
    model   = DatabaseConfig
    extra   = 1          
    fields  = ['name', 'db_engine', 'db_name', 'host', 'port',
            'username', 'password', 'allowed_tables', 'db_type', 'active']
    show_change_link = True   


class DocumentInline(admin.TabularInline):
    model   = Document
    extra   = 1
    fields  = ['title', 'file', 'doc_type', 'is_processed']
    readonly_fields = ['is_processed'] 

class AgentConfigInline(admin.StackedInline):  
    model  = AgentConfig
    extra  = 1
    fieldsets = [
        (None, {
            'fields': ['agent_type', 'enabled', 'priority']
        }),
        ('Configuration LLM de cet agent', {
            'fields': ['llm_model', 'agent_prompt'],
            'classes': ['collapse'],   
            'description': 'Modèle et prompt spécifiques à cet agent'
        }),
        ('Paramètres avancés', {
            'fields': ['config'],
            'classes': ['collapse'],
        }),
    ]
class ScopeInline(admin.StackedInline):
    model = Scope
    extra = 1
    fields = ['max_response_length', 'response_style']


@admin.register(Chatbot)
class ChatbotAdmin(admin.ModelAdmin):
    list_display  = ['name', 'llm_model', 'active', 'is_default', 'created_at']  # ← is_default
    list_filter   = ['active', 'llm_model', 'is_default']                          # ← filtre
    list_editable = ['is_default', 'active']                                        # ← éditable inline
    search_fields = ['name', 'description']
    inlines       = [DatabaseConfigInline, AgentConfigInline, ScopeInline, DocumentInline]
    fieldsets = [
        ("Informations générales", {
            "fields": ["name", "description", "active", "is_default"],  # ← is_default ici
            "description": "Cocher 'Chatbot par défaut' pour l'assigner automatiquement aux nouveaux clients"
        }),
        ("Configuration LLM", {
            "fields": ["llm_model", "system_prompt"],
            "classes": ["collapse"],
        }),
    ]


@admin.register(ConversationMemory)
class ConversationMemoryAdmin(admin.ModelAdmin):
    list_display    = ['user_id', 'chatbot', 'key', 'value', 'updated_at']
    list_filter     = ['chatbot', 'key']
    search_fields   = ['user_id', 'key', 'value']
    readonly_fields = ['updated_at']

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display    = ['title', 'chatbot', 'doc_type', 'is_processed', 'uploaded_at']
    list_filter     = ['chatbot', 'doc_type', 'is_processed']
    search_fields   = ['title', 'chatbot__name']
    readonly_fields = ['is_processed', 'uploaded_at']

class UserProfileInline(admin.StackedInline):
    model  = UserProfile
    extra  = 0
    fields = ['role', 'allowed_chatbots', 'keycloak_id']

    # Afficher un lien d'aide pour trouver l'UUID dans Keycloak
    readonly_fields = []

class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'get_role', 'get_keycloak_id', 'is_active', 'date_joined']

    def get_role(self, obj):
        try: return obj.userprofile.get_role_display()
        except: return '—'
    get_role.short_description = 'Rôle'

    # ← NOUVEAU : afficher l'UUID Keycloak dans la liste
    def get_keycloak_id(self, obj):
        try:
            kid = obj.userprofile.keycloak_id
            return kid[:8] + '…' if kid else '⚠️ Non lié'
        except: return '—'
    get_keycloak_id.short_description = 'Keycloak ID'

admin.site.unregister(User)
admin.site.register(User, UserAdmin)


