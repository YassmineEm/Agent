# dashboard/services/supabase_service.py
from supabase import create_client, Client
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

_supabase_client = None
_supabase_users_cache = None  


def get_supabase_admin() -> Client:
    """Retourne le client Supabase avec les droits admin (service_role)."""
    global _supabase_client
    
    if _supabase_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            logger.error("SUPABASE_URL ou SUPABASE_SERVICE_KEY non configurés dans settings.py")
            raise ValueError("Configuration Supabase manquante")
        
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
        logger.info("Client Supabase admin initialisé")
    
    return _supabase_client


def clear_supabase_cache():
    """Vider le cache des utilisateurs Supabase."""
    global _supabase_users_cache
    _supabase_users_cache = None
    logger.info("Cache Supabase vidé")


def get_supabase_users(force_refresh: bool = False) -> list:
    """Lister tous les users depuis Supabase (pour la page Users de l'AdminUI)."""
    global _supabase_users_cache
    
    # Si on force le rafraîchissement, vider le cache
    if force_refresh:
        clear_supabase_cache()
    
    # Retourner le cache s'il existe
    if _supabase_users_cache is not None:
        logger.debug(f"Cache: {len(_supabase_users_cache)} utilisateurs")
        return _supabase_users_cache
    
    supabase = get_supabase_admin()
    try:
        response = supabase.auth.admin.list_users()
        
        # La réponse peut être une liste directement ou un objet avec .users
        if isinstance(response, list):
            users = response
        elif hasattr(response, 'users'):
            users = response.users
        else:
            users = []
        
        # Mettre en cache
        _supabase_users_cache = users
        
        logger.info(f"{len(users)} utilisateurs récupérés depuis Supabase")
        return users
    except Exception as e:
        logger.error(f"Erreur get_supabase_users : {e}")
        return []


def get_supabase_user_by_email(email: str):
    """Récupérer un utilisateur Supabase par son email."""
    supabase = get_supabase_admin()
    try:
        response = supabase.auth.admin.list_users()
        
        # CORRECTION : La réponse peut être une liste directement ou un objet avec .users
        if isinstance(response, list):
            users = response
        elif hasattr(response, 'users'):
            users = response.users
        else:
            users = []
        
        for user in users:
            if user.email == email:
                logger.debug(f"Utilisateur trouvé : {email} -> {user.id}")
                return user
        
        logger.warning(f"Utilisateur non trouvé : {email}")
        return None
    except Exception as e:
        logger.error(f"Erreur get_supabase_user_by_email : {e}")
        return None


def grant_chatbot_access(user_supabase_id: str, chatbot_id: str) -> bool:
    """Donner accès à un chatbot à un utilisateur."""
    if not user_supabase_id:
        logger.error("user_supabase_id manquant")
        return False
    
    supabase = get_supabase_admin()
    try:
        supabase.table("user_chatbot_access").upsert({
            "user_id": user_supabase_id,
            "chatbot_id": str(chatbot_id),
        }).execute()
        logger.info(f"Accès accordé : user={user_supabase_id}, chatbot={chatbot_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur grant_chatbot_access : {e}")
        return False


def revoke_chatbot_access(user_supabase_id: str, chatbot_id: str) -> bool:
    """Retirer l'accès à un chatbot."""
    if not user_supabase_id:
        logger.error("user_supabase_id manquant")
        return False
    
    supabase = get_supabase_admin()
    try:
        supabase.table("user_chatbot_access") \
            .delete() \
            .eq("user_id", user_supabase_id) \
            .eq("chatbot_id", str(chatbot_id)) \
            .execute()
        logger.info(f"Accès révoqué : user={user_supabase_id}, chatbot={chatbot_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur revoke_chatbot_access : {e}")
        return False


def get_user_chatbot_access(user_supabase_id: str) -> list:
    """Récupérer la liste des chatbot_ids auxquels un user a accès."""
    if not user_supabase_id:
        logger.warning("user_supabase_id manquant, retour liste vide")
        return []
    
    supabase = get_supabase_admin()
    try:
        result = supabase.table("user_chatbot_access") \
            .select("chatbot_id") \
            .eq("user_id", user_supabase_id) \
            .execute()
        chatbot_ids = [row["chatbot_id"] for row in (result.data or [])]
        logger.debug(f"Accès pour user {user_supabase_id}: {chatbot_ids}")
        return chatbot_ids
    except Exception as e:
        logger.error(f"Erreur get_user_chatbot_access : {e}")
        return []