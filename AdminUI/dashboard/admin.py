from django.contrib import admin
from .models import Chatbot, SQLAgent, RAGAgent, DocumentReference, ActionAgent


class SQLAgentInline(admin.TabularInline):
    model = SQLAgent
    extra = 1


class ActionAgentInline(admin.TabularInline):
    model = ActionAgent
    extra = 1


@admin.register(Chatbot)
class ChatbotAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_model', 'sql_enabled', 'rag_enabled', 'action_enabled', 'is_active', 'created_at']
    list_filter = ['base_model', 'sql_enabled', 'rag_enabled', 'action_enabled', 'is_active']
    search_fields = ['name', 'description']
    inlines = [SQLAgentInline, ActionAgentInline]
    
    fieldsets = (
        ('Identity', {
            'fields': ('name', 'description', 'role', 'scope', 'base_model')
        }),
        ('Module Activation', {
            'fields': ('sql_enabled', 'rag_enabled', 'action_enabled', 'is_active')
        }),
    )


@admin.register(RAGAgent)
class RAGAgentAdmin(admin.ModelAdmin):
    list_display = ['chatbot', 'use_reranker', 'use_query_expansion', 'top_k', 'embedding_model']
    list_filter = ['use_reranker', 'use_query_expansion']


@admin.register(DocumentReference)
class DocumentReferenceAdmin(admin.ModelAdmin):
    list_display = ['name', 'rag_agent', 'content_type', 'is_indexed', 'created_at']
    list_filter = ['is_indexed', 'content_type']
    search_fields = ['name', 'file_path', 'url']


@admin.register(SQLAgent)
class SQLAgentAdmin(admin.ModelAdmin):
    list_display = ['name', 'chatbot', 'db_type', 'is_active', 'created_at']
    list_filter = ['db_type', 'is_active']
    search_fields = ['name', 'chatbot__name']


@admin.register(ActionAgent)
class ActionAgentAdmin(admin.ModelAdmin):
    list_display = ['name', 'chatbot', 'method', 'endpoint', 'is_active', 'created_at']
    list_filter = ['method', 'is_active']
    search_fields = ['name', 'chatbot__name', 'description']