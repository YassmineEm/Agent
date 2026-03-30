from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from .models import Chatbot, RAGAgent, DocumentReference
from .forms import (
    ChatbotForm, SQLAgentForm, RAGAgentForm,
    ActionAgentForm, SQLAgentFormSet, ActionAgentFormSet
)
from api.gateway import sync_sql_chatbot, upload_rag_document, ServiceGatewayError


def index(request):
    """Dashboard home - list all chatbots"""
    chatbots = Chatbot.objects.all()
    context = {
        'chatbots': chatbots
    }
    return render(request, 'dashboard/index.html', context)


def chatbot_create(request):
    """Create new chatbot with dynamic configuration"""
    if request.method == 'POST':
        form = ChatbotForm(request.POST)
        
        if form.is_valid():
            chatbot = form.save()
            
            # Create RAG config if enabled
            if chatbot.rag_enabled:
                RAGAgent.objects.create(
                    chatbot=chatbot,
                    use_reranker=request.POST.get('use_reranker') == 'on',
                    use_query_expansion=request.POST.get('use_query_expansion') == 'on',
                    top_k=int(request.POST.get('top_k', 5)),
                    embedding_model=request.POST.get('embedding_model', 'sentence-transformers/all-MiniLM-L6-v2'),
                )

            if chatbot.sql_enabled:
                try:
                    sync_sql_chatbot(chatbot)
                    messages.success(request, "SQL Agent synced successfully.")
                except ServiceGatewayError as exc:
                    messages.warning(request, f"Chatbot created, but SQL sync failed: {exc}")
            
            messages.success(request, f'Chatbot "{chatbot.name}" created successfully!')
            return redirect('dashboard:chatbot_detail', pk=chatbot.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ChatbotForm()
    
    context = {
        'form': form,
        'is_create': True
    }
    return render(request, 'dashboard/chatbot_form.html', context)


def chatbot_detail(request, pk):
    """View chatbot configuration details"""
    chatbot = get_object_or_404(Chatbot, pk=pk)
    
    context = {
        'chatbot': chatbot,
        'sql_connections': chatbot.sql_connections.all(),
        'actions': chatbot.actions.all(),
        "doc_type_choices" : DocumentReference.DOC_TYPE_CHOICES
    }
    
    if chatbot.rag_enabled and hasattr(chatbot, 'rag_config'):
        context['rag_config'] = chatbot.rag_config
        context['documents'] = chatbot.rag_config.documents.all()
    
    return render(request, 'dashboard/chatbot_detail.html', context)


def chatbot_edit(request, pk):
    """Edit existing chatbot configuration"""
    chatbot = get_object_or_404(Chatbot, pk=pk)
    rag_instance = chatbot.rag_config if hasattr(chatbot, 'rag_config') else None
    
    if request.method == 'POST':
        form = ChatbotForm(request.POST, instance=chatbot)
        sql_formset = SQLAgentFormSet(request.POST, instance=chatbot, prefix='sql')
        action_formset = ActionAgentFormSet(request.POST, instance=chatbot, prefix='action')

        rag_should_be_enabled = request.POST.get('rag_enabled') == 'on'
        rag_form = RAGAgentForm(request.POST, instance=rag_instance) if rag_should_be_enabled else None

        form_is_valid = form.is_valid()
        sql_is_valid = sql_formset.is_valid()
        action_is_valid = action_formset.is_valid()
        rag_is_valid = rag_form.is_valid() if rag_form else True

        if form_is_valid and sql_is_valid and action_is_valid and rag_is_valid:
            chatbot = form.save()

            # Handle SQL connections
            if chatbot.sql_enabled:
                sql_formset.save()
                try:
                    sync_sql_chatbot(chatbot)
                    messages.success(request, "SQL Agent synced successfully.")
                except ServiceGatewayError as exc:
                    messages.warning(request, f"SQL saved locally, but sync failed: {exc}")
            else:
                chatbot.sql_connections.all().delete()
            
            # Handle RAG configuration
            if chatbot.rag_enabled:
                rag_config, _ = RAGAgent.objects.get_or_create(chatbot=chatbot)
                rag_config.use_reranker = rag_form.cleaned_data['use_reranker']
                rag_config.use_query_expansion = rag_form.cleaned_data['use_query_expansion']
                rag_config.top_k = rag_form.cleaned_data['top_k']
                rag_config.embedding_model = rag_form.cleaned_data['embedding_model']
                rag_config.save()
            else:
                RAGAgent.objects.filter(chatbot=chatbot).delete()
            
            # Handle Actions
            if chatbot.action_enabled:
                action_formset.save()
            else:
                chatbot.actions.all().delete()
            
            messages.success(request, f'Chatbot "{chatbot.name}" updated successfully!')
            return redirect('dashboard:chatbot_detail', pk=chatbot.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ChatbotForm(instance=chatbot)
        sql_formset = SQLAgentFormSet(instance=chatbot, prefix='sql')
        action_formset = ActionAgentFormSet(instance=chatbot, prefix='action')
        rag_form = RAGAgentForm(instance=rag_instance) if chatbot.rag_enabled and rag_instance else None
    
    context = {
        'form': form,
        'chatbot': chatbot,
        'sql_formset': sql_formset,
        'action_formset': action_formset,
        'rag_form': rag_form,
        'is_create': False
    }
    return render(request, 'dashboard/chatbot_form.html', context)

@require_http_methods(["POST"])
def rag_upload_document(request, pk):
    """Upload a RAG document via API gateway."""
    chatbot = get_object_or_404(Chatbot, pk=pk)

    if not chatbot.rag_enabled:
        messages.error(request, "RAG is not enabled for this chatbot.")
        return redirect('dashboard:chatbot_detail', pk=chatbot.pk)

    uploaded_file = request.FILES.get("file") or request.FILES.get("rag_upload_file")
    if not uploaded_file:
        messages.error(request, "Please select a file.")
        return redirect('dashboard:chatbot_edit', pk=chatbot.pk)

    local_doc_type = request.POST.get("doc_type") or request.POST.get("rag_upload_doc_type") or "other"
    description = request.POST.get("description", "")

    rag_doc_type_map = {
        "fiche_technique": "fiche_technique",
        "faq": "faq",
        "manual": "general",
        "report": "general",
        "guide": "general",
        "other": "general",
    }
    rag_doc_type = rag_doc_type_map.get(local_doc_type, "general")

    try:
        result = upload_rag_document(
            chatbot_id=chatbot.name,
            uploaded_file=uploaded_file,
            doc_type=rag_doc_type,
            description=description,
        )

        rag_config, _ = RAGAgent.objects.get_or_create(chatbot=chatbot)
        DocumentReference.objects.create(
            rag_agent=rag_config,
            name=uploaded_file.name,
            doc_type=local_doc_type,
            file_path=uploaded_file.name,
            content_type=uploaded_file.content_type or "",
            is_indexed=True,
            chunks_indexed=result.get("chunks_indexed", 0),
        )

        messages.success(request, f"Document uploaded and indexed: {uploaded_file.name}")
    except ServiceGatewayError as exc:
        messages.error(request, f"RAG upload failed: {exc}")

    return redirect('dashboard:chatbot_edit', pk=chatbot.pk)

@require_http_methods(["POST", "GET"])
def add_sql_row(request):
    """HTMX endpoint to add SQL connection row"""
    form = SQLAgentForm()
    html = render_to_string('dashboard/partials/sql_row.html', {'form': form})
    return HttpResponse(html)


@require_http_methods(["POST", "GET"])
def add_action_row(request):
    """HTMX endpoint to add action row"""
    form = ActionAgentForm()
    html = render_to_string('dashboard/partials/action_row.html', {'form': form})
    return HttpResponse(html)


def chatbot_delete(request, pk):
    """Delete chatbot"""
    chatbot = get_object_or_404(Chatbot, pk=pk)
    
    if request.method == 'POST':
        name = chatbot.name
        chatbot.delete()
        messages.success(request, f'Chatbot "{name}" deleted successfully!')
        return redirect('dashboard:index')
    
    return render(request, 'dashboard/chatbot_confirm_delete.html', {'chatbot': chatbot})