from django import forms
from django.forms import inlineformset_factory
from .models import Chatbot, SQLAgent, RAGAgent, DocumentReference, ActionAgent


class ChatbotForm(forms.ModelForm):
    """Main chatbot configuration form"""
    
    class Meta:
        model = Chatbot
        fields = [
            'name', 'description', 'role', 'scope', 'base_model',
            'sql_enabled', 'sql_llm', 'rag_enabled', 'action_enabled', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Enter chatbot name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 3,
                'placeholder': 'Brief description of the chatbot purpose'
            }),
            'role': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm',
                'rows': 6,
                'placeholder': 'You are a helpful assistant specialized in...'
            }),
            'scope': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm',
                'rows': 4,
                'placeholder': 'Define boundaries and guardrails...'
            }),
            'base_model': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'sql_llm': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'sql_enabled': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 rounded focus:ring-blue-500',
                'x-model': 'sqlEnabled'
            }),
            'rag_enabled': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 rounded focus:ring-blue-500',
                'x-model': 'ragEnabled'
            }),
            'action_enabled': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 rounded focus:ring-blue-500',
                'x-model': 'actionEnabled'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-green-600 rounded focus:ring-green-500'
            }),
        }


class SQLAgentForm(forms.ModelForm):
    """SQL Agent connection form"""

    class Meta:
        model = SQLAgent
        fields = ['name', 'db_name', 'db_type', 'connection_string', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Connection identifier (e.g., flight_db_01)'
            }),
            'db_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Database name (e.g., Global Flight Operations)'
            }),
            'db_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'connection_string': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm',
                'placeholder': 'sqlite:///database/flight.sqlite or postgresql://user:pass@host:5432/dbname',
                'type': 'password'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 rounded focus:ring-blue-500'
            }),
        }


class RAGAgentForm(forms.ModelForm):
    """RAG Agent configuration form"""
    
    class Meta:
        model = RAGAgent
        fields = ['use_reranker', 'use_query_expansion', 'top_k', 'embedding_model']
        widgets = {
            'use_reranker': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 rounded focus:ring-blue-500',
                'x-model': 'rerankerEnabled'
            }),
            'use_query_expansion': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 rounded focus:ring-blue-500',
                'x-model': 'queryExpansionEnabled'
            }),
            'top_k': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'min': 1,
                'max': 20
            }),
            'embedding_model': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm',
                'placeholder': 'sentence-transformers/all-MiniLM-L6-v2'
            }),
        }


class DocumentReferenceForm(forms.ModelForm):
    """Document reference form for RAG"""

    class Meta:
        model = DocumentReference
        fields = ['name', 'doc_type', 'file_path', 'url', 'content_type']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Document name'
            }),
            'doc_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'file_path': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': '/path/to/document.pdf'
            }),
            'url': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'https://example.com/document.pdf'
            }),
            'content_type': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'application/pdf'
            }),
        }


class ActionAgentForm(forms.ModelForm):
    """Action/Tool definition form"""
    
    class Meta:
        model = ActionAgent
        fields = ['name', 'description', 'endpoint', 'method', 'headers', 'payload_template', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Action name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 2,
                'placeholder': 'What does this action do?'
            }),
            'endpoint': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'https://api.example.com/endpoint'
            }),
            'method': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'headers': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm',
                'rows': 3,
                'placeholder': '{"Authorization": "Bearer token", "Content-Type": "application/json"}'
            }),
            'payload_template': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm',
                'rows': 4,
                'placeholder': '{"key": "value"}'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 rounded focus:ring-blue-500'
            }),
        }


# Formsets for dynamic row injection
SQLAgentFormSet = inlineformset_factory(
    Chatbot,
    SQLAgent,
    form=SQLAgentForm,
    extra=1,
    can_delete=True
)

DocumentReferenceFormSet = inlineformset_factory(
    RAGAgent,
    DocumentReference,
    form=DocumentReferenceForm,
    extra=1,
    can_delete=True
)

ActionAgentFormSet = inlineformset_factory(
    Chatbot,
    ActionAgent,
    form=ActionAgentForm,
    extra=1,
    can_delete=True
)