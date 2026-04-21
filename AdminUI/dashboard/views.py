from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.contrib.admin.views.decorators import staff_member_required
from .models import Chatbot, RAGAgent, DocumentReference, SQLAgent
from .forms import (
    ChatbotForm, SQLAgentForm, RAGAgentForm,
    ActionAgentForm, SQLAgentFormSet, ActionAgentFormSet
)
from django.contrib.auth.models import User
from django.db import models  
from .models import UserProfile
from api.gateway import sync_sql_chatbot, upload_rag_document, query_sql_agent, query_rag_agent, ServiceGatewayError
import json
import logging

logger = logging.getLogger(__name__)

from .services.supabase_service import (
    get_supabase_admin,
    grant_chatbot_access, 
    revoke_chatbot_access, 
    get_user_chatbot_access,
    get_supabase_user_by_email,
    get_supabase_users
)


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

            if chatbot.sql_enabled:
                names        = request.POST.getlist('sql_connection_name[]')
                db_names     = request.POST.getlist('sql_db_name[]')
                db_types     = request.POST.getlist('sql_db_type[]')
                agent_descs  = request.POST.getlist('sql_agent_description[]')
                
                sqlite_paths = request.POST.getlist('sql_sqlite_path[]')
                
                hosts        = request.POST.getlist('sql_host[]')
                ports        = request.POST.getlist('sql_port[]')
                databases    = request.POST.getlist('sql_database[]')
                usernames    = request.POST.getlist('sql_username[]')
                passwords    = request.POST.getlist('sql_password[]')
                
                created_count = 0
                
                for i, name in enumerate(names):
                    name = name.strip()
                    if not name:
                        continue 
                    
                    db_type = db_types[i] if i < len(db_types) else 'postgresql'
                    db_name_value = db_names[i].strip() if i < len(db_names) else name
                    agent_desc_value = agent_descs[i].strip() if i < len(agent_descs) else ''
                    
                    # ── SQLite ──────────────────────────────────────────────────
                    if db_type == 'sqlite':
                        sqlite_path = sqlite_paths[i].strip() if i < len(sqlite_paths) else ''
                        if not sqlite_path:
                            continue 
                        
                        SQLAgent.objects.create(
                            chatbot=chatbot,
                            name=name,
                            db_name=db_name_value,
                            db_type=db_type,
                            sqlite_path=sqlite_path,
                            agent_description=agent_desc_value,
                            is_active=True,
                        )
                        created_count += 1
                    
                    else:
                        host = hosts[i].strip() if i < len(hosts) else ''
                        port = ports[i].strip() if i < len(ports) else ''
                        database = databases[i].strip() if i < len(databases) else ''
                        username = usernames[i].strip() if i < len(usernames) else ''
                        password = passwords[i].strip() if i < len(passwords) else ''
                        

                        if not host or not port or not database:
                            continue
                        

                        try:
                            port_int = int(port)
                        except (ValueError, TypeError):
                            continue
                        
                        SQLAgent.objects.create(
                            chatbot=chatbot,
                            name=name,
                            db_name=db_name_value,
                            db_type=db_type,
                            host=host,
                            port=port_int,
                            database=database,
                            username=username or None,
                            password=password or None,
                            agent_description=agent_desc_value,
                            is_active=True,
                        )
                        created_count += 1
                
                if created_count:
                    try:
                        sync_sql_chatbot(chatbot)
                        messages.success(request, f"SQL Agent synced ({created_count} connexion(s)).")
                    except ServiceGatewayError as exc:
                        messages.warning(request, f"Connexions SQL sauvegardées, mais sync échouée : {exc}")
                else:
                    messages.warning(request, "SQL activé mais aucune connexion valide fournie.")


            if chatbot.rag_enabled:
                rag_config = RAGAgent.objects.create(
                    chatbot=chatbot,
                    use_reranker=request.POST.get('use_reranker') == 'on',
                    use_query_expansion=request.POST.get('use_query_expansion') == 'on',
                    top_k=int(request.POST.get('top_k', 5)),
                    embedding_model=request.POST.get(
                        'embedding_model', 'sentence-transformers/all-MiniLM-L6-v2'
                    ),
                    agent_description=request.POST.get('rag_agent_description', '').strip(),
                )

                uploaded_file = request.FILES.get("file")
                if uploaded_file:
                    local_doc_type = request.POST.get("doc_type", "other")
                    rag_doc_type_map = {
                        "fiche_technique": "fiche_technique",
                        "faq":             "faq",
                        "manual":          "general",
                        "report":          "general",
                        "guide":           "general",
                        "other":           "general",
                    }
                    rag_doc_type = rag_doc_type_map.get(local_doc_type, "general")

                    try:
                        result = upload_rag_document(
                            chatbot_id=chatbot.name,
                            uploaded_file=uploaded_file,
                            doc_type=rag_doc_type,
                            description="",
                        )
                        DocumentReference.objects.create(
                            rag_agent=rag_config,
                            name=uploaded_file.name,
                            doc_type=local_doc_type,
                            file_path=uploaded_file.name,
                            content_type=uploaded_file.content_type or "",
                            is_indexed=True,
                            chunks_indexed=result.get("chunks_indexed", 0),
                        )
                        messages.success(request, f"Document indexé : {uploaded_file.name}")
                    except ServiceGatewayError as exc:
                        messages.warning(request, f"Chatbot créé, mais upload RAG échoué : {exc}")

            messages.success(request, f'Chatbot "{chatbot.name}" créé avec succès !')
            return redirect('dashboard:chatbot_detail', pk=chatbot.pk)
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
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
        "doc_type_choices": DocumentReference.DOC_TYPE_CHOICES
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
        
        # Les formsets utilisent automatiquement les nouveaux champs du modèle
        # car SQLAgentForm a été mis à jour avec les nouveaux widgets
        sql_formset    = SQLAgentFormSet(request.POST, instance=chatbot, prefix='sql')
        action_formset = ActionAgentFormSet(request.POST, instance=chatbot, prefix='action')

        rag_should_be_enabled = request.POST.get('rag_enabled') == 'on'
        rag_form = RAGAgentForm(request.POST, instance=rag_instance) if rag_should_be_enabled else None

        form_is_valid   = form.is_valid()
        sql_is_valid    = sql_formset.is_valid()
        action_is_valid = action_formset.is_valid()
        rag_is_valid    = rag_form.is_valid() if rag_form else True

        if form_is_valid and sql_is_valid and action_is_valid and rag_is_valid:
            chatbot = form.save()

            # Handle SQL connections
            if chatbot.sql_enabled:
                # Sauvegarde automatique des connexions SQL
                # Les nouveaux champs (host, port, database, username, password, sqlite_path)
                # sont automatiquement gérés par le formset car SQLAgentForm les inclut
                sql_formset.save()
                try:
                    sync_sql_chatbot(chatbot)
                    messages.success(request, "SQL Agent synchronisé.")
                except ServiceGatewayError as exc:
                    messages.warning(request, f"SQL sauvegardé localement, sync échouée : {exc}")
            else:
                chatbot.sql_connections.all().delete()

            # Handle RAG configuration
            if chatbot.rag_enabled:
                rag_config, _ = RAGAgent.objects.get_or_create(chatbot=chatbot)
                rag_config.use_reranker       = rag_form.cleaned_data['use_reranker']
                rag_config.use_query_expansion = rag_form.cleaned_data['use_query_expansion']
                rag_config.top_k              = rag_form.cleaned_data['top_k']
                rag_config.embedding_model    = rag_form.cleaned_data['embedding_model']
                rag_config.agent_description  = rag_form.cleaned_data.get('agent_description', '')
                rag_config.save()
            else:
                RAGAgent.objects.filter(chatbot=chatbot).delete()

            # Handle Actions
            if chatbot.action_enabled:
                action_formset.save()
            else:
                chatbot.actions.all().delete()

            messages.success(request, f'Chatbot "{chatbot.name}" mis à jour !')
            return redirect('dashboard:chatbot_detail', pk=chatbot.pk)
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        form           = ChatbotForm(instance=chatbot)
        sql_formset    = SQLAgentFormSet(instance=chatbot, prefix='sql')
        action_formset = ActionAgentFormSet(instance=chatbot, prefix='action')
        rag_form       = RAGAgentForm(instance=rag_instance) if chatbot.rag_enabled and rag_instance else None

    context = {
        'form':           form,
        'chatbot':        chatbot,
        'sql_formset':    sql_formset,
        'action_formset': action_formset,
        'rag_form':       rag_form,
        'is_create':      False
    }
    return render(request, 'dashboard/chatbot_form.html', context)


@require_http_methods(["POST"])
def rag_upload_document(request, pk):
    """Upload a RAG document via API gateway."""
    chatbot = get_object_or_404(Chatbot, pk=pk)

    if not chatbot.rag_enabled:
        messages.error(request, "RAG n'est pas activé pour ce chatbot.")
        return redirect('dashboard:chatbot_detail', pk=chatbot.pk)

    uploaded_file = request.FILES.get("file") or request.FILES.get("rag_upload_file")
    if not uploaded_file:
        messages.error(request, "Veuillez sélectionner un fichier.")
        return redirect('dashboard:chatbot_edit', pk=chatbot.pk)

    local_doc_type = request.POST.get("doc_type") or request.POST.get("rag_upload_doc_type") or "other"
    description    = request.POST.get("description", "")

    rag_doc_type_map = {
        "fiche_technique": "fiche_technique",
        "faq":             "faq",
        "manual":          "general",
        "report":          "general",
        "guide":           "general",
        "other":           "general",
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
        messages.success(request, f"Document indexé : {uploaded_file.name}")
    except ServiceGatewayError as exc:
        messages.error(request, f"Upload RAG échoué : {exc}")

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
        messages.success(request, f'Chatbot "{name}" supprimé !')
        return redirect('dashboard:index')

    return render(request, 'dashboard/chatbot_confirm_delete.html', {'chatbot': chatbot})


@require_http_methods(["GET"])
def test_sql_agent(request, pk):
    """Test SQL agent with a query"""
    chatbot = get_object_or_404(Chatbot, pk=pk)

    if not chatbot.sql_enabled:
        return JsonResponse({'success': False, 'error': 'SQL Agent non activé'})

    question = request.GET.get('question', '')
    if not question:
        return JsonResponse({'success': False, 'error': 'Paramètre question requis'})

    try:
        result = query_sql_agent(chatbot_id=chatbot.name, user_question=question)
        return JsonResponse({'success': True, 'result': result})
    except ServiceGatewayError as exc:
        return JsonResponse({'success': False, 'error': str(exc)})


@require_http_methods(["POST"])
def test_rag_agent(request, pk):
    """Test RAG agent with a query"""
    chatbot = get_object_or_404(Chatbot, pk=pk)

    if not chatbot.rag_enabled:
        return JsonResponse({'success': False, 'error': 'RAG Agent non activé'})

    try:
        data     = json.loads(request.body)
        question = data.get('question', '')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalide'})

    if not question:
        return JsonResponse({'success': False, 'error': 'Paramètre question requis'})

    try:
        result = query_rag_agent(chatbot_id=chatbot.name, question=question)
        return JsonResponse({'success': True, 'result': result})
    except ServiceGatewayError as exc:
        return JsonResponse({'success': False, 'error': str(exc)})


@require_http_methods(["GET"])
def list_chatbots(request):
    """API endpoint: Get list of all available chatbots"""
    chatbots = Chatbot.objects.all()
    data = {
        'count': chatbots.count(),
        'chatbots': [
            {
                'id':          chatbot.id,
                'name':        chatbot.name,
                'description': chatbot.description,
                'active':      chatbot.is_active,
            }
            for chatbot in chatbots
        ]
    }
    return JsonResponse(data)


@require_http_methods(["GET"])
def chatbot_config(request, chat_id):
    """API endpoint: Get detailed chatbot configuration"""
    try:
        chatbot = Chatbot.objects.get(id=chat_id)
    except Chatbot.DoesNotExist:
        return JsonResponse({'error': f'Chatbot {chat_id} introuvable'}, status=404)

    chatbot_data = {
        'id':            chatbot.id,
        'name':          chatbot.name,
        'description':   chatbot.description,
        'system_prompt': chatbot.role,
        'scope':         chatbot.scope,        # ← AJOUTÉ (utile pour l'orchestrateur)
        'llm_model':     chatbot.base_model,
        'active':        chatbot.is_active,
    }

    # ── Descriptions SQL agrégées depuis toutes les connexions actives ────────
    sql_desc_parts = [
        conn.agent_description
        for conn in chatbot.sql_connections.filter(is_active=True)
        if conn.agent_description
    ]
    sql_description = " | ".join(sql_desc_parts) if sql_desc_parts else None

    # ── Description RAG ───────────────────────────────────────────────────────
    rag_description = None
    if chatbot.rag_enabled and hasattr(chatbot, 'rag_config'):
        rag_description = chatbot.rag_config.agent_description or None

    agents = [
        {
            'agent_type':  'sql',
            'enabled':     chatbot.sql_enabled,
            'llm_model':   chatbot.sql_llm if chatbot.sql_enabled else None,
            'description': sql_description,    # ← NOUVEAU
        },
        {
            'agent_type':  'rag',
            'enabled':     chatbot.rag_enabled,
            'description': rag_description,    # ← NOUVEAU
        },
        {
            'agent_type':  'weather',
            'enabled':     getattr(chatbot, 'weather_enabled', False),
            'description': None,
        },
        {
            'agent_type':  'location',
            'enabled':     getattr(chatbot, 'location_enabled', False),
            'description': None,
        },
        {
            'agent_type':  'custom',
            'enabled':     chatbot.action_enabled,
            # Description agrégée des actions actives
            'description': " | ".join([    # ← NOUVEAU
                f"{a.name}: {a.description}"
                for a in chatbot.actions.filter(is_active=True)
                if a.description
            ]) or None,
        },
    ]

    database_configs = []
    for sql_conn in chatbot.sql_connections.filter(is_active=True):
        database_configs.append({
            'name':              sql_conn.db_name,
            'db_engine':         sql_conn.db_type,
            'db_name':           sql_conn.db_name,
            'active':            sql_conn.is_active,
            'connection_string': sql_conn.connection_string,
            'description':       sql_conn.agent_description or None, 
        })

    rag_data = None
    if chatbot.rag_enabled:
        try:
            rag_agent = chatbot.rag_config
            rag_data  = {
                'agent_description': rag_agent.agent_description or None,  
                'documents': [
                    {'id': doc.id, 'title': doc.name, 'doc_type': doc.doc_type}
                    for doc in rag_agent.documents.all()
                ],
            }
        except RAGAgent.DoesNotExist:
            rag_data = {'agent_description': None, 'documents': []}

    response_data = {
        'chatbot':          chatbot_data,
        'agents':           agents,
        'database_configs': database_configs,
    }
    if rag_data:
        response_data['rag'] = rag_data

    return JsonResponse(response_data)


def chatbots_sql_list(request):
    chatbots = (
        Chatbot.objects
        .filter(sql_enabled=True, is_active=True)
        .prefetch_related('sql_connections')
    )
    result = []
    for bot in chatbots:
        active_dbs = bot.sql_connections.filter(is_active=True)
        if not active_dbs.exists():
            continue
        result.append({
            "chatbot_id": bot.name,
            "chatbot_name": bot.name,
            "model_name": bot.sql_llm or bot.base_model,
            "databases": [
                {
                    "db_id": db.db_id,
                    "db_name": db.db_name,
                    "connection_uri": db.connection_string,
                }
                for db in active_dbs
            ]
        })
    return JsonResponse({"chatbots": result})


# dashboard/views.py
# REMPLACER la fonction user_list existante par celle-ci

def user_list(request):
    """
    Display all registered users from Supabase with search/filter support.
    """
    # Récupérer les utilisateurs depuis Supabase
    supabase_users = get_supabase_users(force_refresh=True)
    
    # Transformer les données Supabase en format compatible avec le template
    users_data = []
    for sb_user in supabase_users:
        # Chercher si l'utilisateur existe aussi dans Django (pour la compatibilité)
        django_user = None
        try:
            django_user = User.objects.get(email=sb_user.email)
        except User.DoesNotExist:
            pass
        
        # Compter les chatbots assignés (si existe dans Django)
        chatbot_count = 0
        if django_user and hasattr(django_user, 'profile'):
            chatbot_count = django_user.profile.chatbots.count()
        
        users_data.append({
            'id': sb_user.id,
            'email': sb_user.email,
            'username': sb_user.email.split('@')[0],
            'full_name': sb_user.user_metadata.get('display_name', '') if sb_user.user_metadata else '',
            'is_active': True,  # Les utilisateurs Supabase sont actifs par défaut
            'date_joined': sb_user.created_at,
            'last_sign_in': sb_user.last_sign_in_at,
            'chatbot_count': chatbot_count,
            'has_django_profile': django_user is not None,
            'django_id': django_user.id if django_user else None,
        })
    
    # Filtres
    q = request.GET.get('q', '').strip()
    if q:
        users_data = [
            u for u in users_data 
            if q.lower() in u['email'].lower() 
            or q.lower() in u['username'].lower()
            or q.lower() in u['full_name'].lower()
        ]
    
    status = request.GET.get('status', '')
    if status == 'active':
        users_data = [u for u in users_data if u['is_active']]
    elif status == 'inactive':
        users_data = [u for u in users_data if not u['is_active']]
    
    # Réponse AJAX pour le filtrage en temps réel
    if request.GET.get('ajax') == '1':
        data = []
        for u in users_data:
            data.append({
                "id": u['id'],
                "email": u['email'],
                "name": u['full_name'] or u['username'],
                "is_active": u['is_active'],
                "chatbot_count": u['chatbot_count'],
                "date_joined": u['date_joined'].strftime("%b %d, %Y") if u['date_joined'] else "Unknown",
            })
        return JsonResponse({"users": data})
    
    context = {
        'users': users_data,
        'q': q,
        'status': status,
        'total_count': len(supabase_users),
    }
    
    return render(request, 'dashboard/user_list.html', context)
 
# dashboard/views.py
# MODIFIER la fonction user_detail pour utiliser l'ID Supabase

def user_detail(request, user_id):
    """
    Show user information from Supabase by Supabase ID.
    """
    # Récupérer l'utilisateur depuis Supabase par son ID
    supabase = get_supabase_admin()
    try:
        response = supabase.auth.admin.get_user_by_id(user_id)
        sb_user = response.user
    except Exception as e:
        messages.error(request, f"Utilisateur Supabase non trouvé : {e}")
        return redirect('dashboard:user_list')
    
    # Chercher si l'utilisateur existe dans Django, sinon le créer
    django_user = None
    try:
        django_user = User.objects.get(email=sb_user.email)
    except User.DoesNotExist:
        username = sb_user.email.split('@')[0]
        # S'assurer que le username est unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        django_user = User.objects.create_user(
            username=username,
            email=sb_user.email,
            password=None  # Pas de mot de passe, l'auth se fait via Supabase
        )
        django_user.is_active = True
        django_user.save()
        messages.info(request, f"Utilisateur Django créé automatiquement pour {sb_user.email}")
    
    # Get or create profile
    profile, _ = UserProfile.objects.get_or_create(user=django_user)
    
    # Synchroniser le supabase_id
    if not profile.supabase_id:
        profile.supabase_id = str(sb_user.id)
        profile.save()

    afriquia_chatbot = Chatbot.objects.filter(name="Afriquia", is_active=True).first()
    if afriquia_chatbot:
        # Ajouter localement (Django) si pas déjà présent
        if afriquia_chatbot not in profile.chatbots.all():
            profile.chatbots.add(afriquia_chatbot)
            logger.info(f"Chatbot 'Afriquia' ajouté au profil AdminUI pour {django_user.email}")
    
    supabase_id = str(sb_user.id)
    
    # Gestion des POST (grant/revoke via Supabase)
    if request.method == "POST":
        action = request.POST.get("action")
        chatbot_id = request.POST.get("chatbot_id")
        
        if action == "grant_supabase" and supabase_id:
            if grant_chatbot_access(supabase_id, chatbot_id):
                messages.success(request, f"Accès accordé via Supabase au chatbot ID {chatbot_id}")
            else:
                messages.error(request, f"Erreur lors de l'octroi d'accès")
        
        elif action == "revoke_supabase" and supabase_id:
            if revoke_chatbot_access(supabase_id, chatbot_id):
                messages.success(request, f"Accès révoqué via Supabase au chatbot ID {chatbot_id}")
            else:
                messages.error(request, f"Erreur lors de la révocation")
        
        elif action == "add" and django_user and profile:
            chatbot_id_post = request.POST.get('chatbot_id')
            if chatbot_id_post:
                chatbot = get_object_or_404(Chatbot, pk=chatbot_id_post)
                profile.chatbots.add(chatbot)
                messages.success(request, f'Accès à "{chatbot.name}" accordé (système local).')
        
        elif action == "remove" and django_user and profile:
            chatbot_id_post = request.POST.get('chatbot_id')
            if chatbot_id_post:
                chatbot = get_object_or_404(Chatbot, pk=chatbot_id_post)
                profile.chatbots.remove(chatbot)
                messages.success(request, f'Accès à "{chatbot.name}" révoqué (système local).')
        
        return redirect('dashboard:user_detail', user_id=user_id)
    
    # Chatbots assignés localement (maintenant profile existe)
    assigned_chatbots = []
    available_chatbots = []
    if profile:
        assigned_chatbots = profile.chatbots.all()
        assigned_ids = profile.chatbots.values_list('id', flat=True)
        available_chatbots = Chatbot.objects.exclude(id__in=assigned_ids).filter(is_active=True)
    
    # Chatbots accessibles via Supabase
    supabase_granted_ids = set(get_user_chatbot_access(supabase_id))
    
    # Tous les chatbots actifs
    all_active_chatbots = Chatbot.objects.filter(is_active=True)
    
    # Objet user pour le template
    class UserProxy:
        def __init__(self, sb_user, django_user):
            self.id = sb_user.id
            self.email = sb_user.email
            self.username = sb_user.email.split('@')[0]
            self.first_name = sb_user.user_metadata.get('display_name', '') if sb_user.user_metadata else ''
            self.last_name = ''
            self.is_active = True
            self.is_staff = False
            self.date_joined = sb_user.created_at
            self.last_login = sb_user.last_sign_in_at
            self.django_user = django_user
        
        def get_full_name(self):
            return self.first_name or self.username
    
    user_obj = UserProxy(sb_user, django_user)
    
    context = {
        'user_obj': user_obj,
        'profile': profile,
        'assigned_chatbots': assigned_chatbots,
        'available_chatbots': available_chatbots,
        'supabase_granted_ids': supabase_granted_ids,
        'supabase_id': supabase_id,
        'has_supabase_id': True,
        'all_chatbots': all_active_chatbots,
        'has_django_profile': django_user is not None,
    }
    return render(request, 'dashboard/user_detail.html', context)
 
 
# dashboard/views.py

@require_http_methods(["POST"])
def user_add_chatbot(request, user_id):
    """
    Add chatbot access to a user.
    Agit à la fois sur le stockage local (Django) et cloud (Supabase).
    """
    django_user = None
    
    if len(user_id) > 30 and '-' in user_id:
        supabase = get_supabase_admin()
        try:
            response = supabase.auth.admin.get_user_by_id(user_id)
            sb_user = response.user
            try:
                django_user = User.objects.get(email=sb_user.email)
            except User.DoesNotExist:
                messages.error(request, f"Utilisateur Django non trouvé pour {sb_user.email}")
                return redirect('dashboard:user_list')
        except Exception as e:
            messages.error(request, f"Utilisateur Supabase non trouvé : {e}")
            return redirect('dashboard:user_list')
    else:
        django_user = get_object_or_404(User, pk=user_id)
    
    profile, _ = UserProfile.objects.get_or_create(user=django_user)
    
    chatbot_id = request.POST.get('chatbot_id')
    if not chatbot_id:
        messages.error(request, "Please select a chatbot.")
        return redirect('dashboard:user_detail', user_id=user_id)
    
    chatbot = get_object_or_404(Chatbot, pk=chatbot_id)
    
    profile.chatbots.add(chatbot)
    
    supabase_id = profile.supabase_id
    if supabase_id:
        grant_chatbot_access(supabase_id, str(chatbot.id))
        messages.success(request, f'Accès à "{chatbot.name}" accordé (local + cloud).')
    else:
        messages.success(request, f'Accès à "{chatbot.name}" accordé (local uniquement).')
    
    return redirect('dashboard:user_detail', user_id=user_id)


@require_http_methods(["POST"])
def user_remove_chatbot(request, user_id, chatbot_id):
    """
    Remove chatbot access from a user.
    Agit à la fois sur le stockage local (Django) et cloud (Supabase).
    """
    django_user = None
    
    if len(user_id) > 30 and '-' in user_id:
        supabase = get_supabase_admin()
        try:
            response = supabase.auth.admin.get_user_by_id(user_id)
            sb_user = response.user
            try:
                django_user = User.objects.get(email=sb_user.email)
            except User.DoesNotExist:
                messages.error(request, f"Utilisateur Django non trouvé pour {sb_user.email}")
                return redirect('dashboard:user_list')
        except Exception as e:
            messages.error(request, f"Utilisateur Supabase non trouvé : {e}")
            return redirect('dashboard:user_list')
    else:
        django_user = get_object_or_404(User, pk=user_id)
    
    profile, _ = UserProfile.objects.get_or_create(user=django_user)
    chatbot = get_object_or_404(Chatbot, pk=chatbot_id)
    

    profile.chatbots.remove(chatbot)
    
    supabase_id = profile.supabase_id
    if supabase_id:
        revoke_chatbot_access(supabase_id, str(chatbot.id))
        messages.success(request, f'Accès à "{chatbot.name}" révoqué (local + cloud).')
    else:
        messages.success(request, f'Accès à "{chatbot.name}" révoqué (local uniquement).')
    
    return redirect('dashboard:user_detail', user_id=user_id)

# dashboard/views.py



@require_http_methods(["POST"])
def sync_user_supabase(request, user_id):
    """
    Déprécié - Les utilisateurs sont maintenant chargés directement depuis Supabase.
    Cette vue est conservée pour compatibilité mais ne fait plus rien.
    """
    messages.info(request, "La synchronisation manuelle n'est plus nécessaire. Les utilisateurs sont chargés automatiquement depuis Supabase.")
    return redirect('dashboard:user_list')