import logging
import httpx
import os
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Chatbot, SQLAgent

logger = logging.getLogger(__name__)
SQL_AGENT_URL = os.getenv("SQL_AGENT_URL", "http://localhost:8006")
RAG_AGENT_URL = os.getenv("RAG_AGENT_URL", "http://akwa_rag_agent:8005")
RAG_ADMIN_API_KEY = os.getenv("RAG_AGENT_ADMIN_API_KEY", "akwa_admin_secret_2025")


def _build_payload(chatbot: Chatbot) -> dict | None:
    """
    Construit le payload pour le sql_agent.
    Retourne None si le chatbot n'est pas éligible.
    """
    if not chatbot.sql_enabled or not chatbot.is_active:
        return None

    active_dbs = chatbot.sql_connections.filter(is_active=True)
    if not active_dbs.exists():
        return None

    return {
        "chatbot_id": str(chatbot.id),
        "model_name": chatbot.sql_llm or chatbot.base_model,
        "databases": [
            {
                "db_id": db.db_id,
                "db_name": db.db_name,
                "connection_uri": db.connection_string,
            }
            for db in active_dbs
        ]
    }


def _sync_to_agent(payload: dict):
    """Envoie le payload au sql_agent de façon synchrone."""
    try:
        resp = httpx.post(
            f"{SQL_AGENT_URL}/sync/chatbot",
            json=payload,
            timeout=10
        )
        resp.raise_for_status()
        logger.info(f"Chatbot '{payload['chatbot_id']}' synchronisé vers sql_agent")
    except Exception as e:
        logger.warning(f"Sync sql_agent échoué: {e}")


# ── Signal sur Chatbot (ex: activation de sql_enabled) ──────────────────────
@receiver(post_save, sender=Chatbot)
def on_chatbot_save(sender, instance, **kwargs):
    payload = _build_payload(instance)
    if payload:
        _sync_to_agent(payload)


# ── Signal sur SQLAgent (ajout / modification d'une DB) ─────────────────────
@receiver(post_save, sender=SQLAgent)
def on_sqlagent_save(sender, instance, **kwargs):
    payload = _build_payload(instance.chatbot)
    if payload:
        _sync_to_agent(payload)


# ── Signal sur suppression d'une SQLAgent DB ────────────────────────────────
@receiver(post_delete, sender=SQLAgent)
def on_sqlagent_delete(sender, instance, **kwargs):
    # Resynchronise avec les DBs restantes (ou retire le chatbot si plus rien)
    chatbot = instance.chatbot
    remaining = chatbot.sql_connections.filter(is_active=True)
    
    if remaining.exists() and chatbot.sql_enabled:
        payload = _build_payload(chatbot)
        if payload:
            _sync_to_agent(payload)
    else:
        # Plus de DB → supprimer du cache du sql_agent
        try:
            httpx.delete(
                f"{SQL_AGENT_URL}/sync/chatbot/{chatbot.id}",
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Suppression sql_agent échouée: {e}")


# ── Signal sur suppression du Chatbot entier ────────────────────────────────
@receiver(post_delete, sender=Chatbot)
def on_chatbot_delete(sender, instance, **kwargs):
    """
    Quand un chatbot est supprimé dans l'AdminUI,
    le retirer du cache du sql_agent s'il y était.
    """
    try:
        resp = httpx.delete(
            f"{SQL_AGENT_URL}/sync/chatbot/{instance.id}",
            timeout=10
        )
        # 404 = n'était pas dans sql_agent (pas sql_enabled), c'est normal
        if resp.status_code not in (200, 404):
            resp.raise_for_status()
        logger.info(f"Chatbot '{instance.name}' supprimé du sql_agent")
    except Exception as e:
        logger.warning(f"Suppression sql_agent échouée pour '{instance.name}': {e}")

@receiver(post_delete, sender=Chatbot)
def delete_chatbot_collection(sender, instance, **kwargs):
    """
    Quand un chatbot est supprimé dans l'AdminUI,
    supprime sa collection Qdrant dans le RAG Agent.
    """
    if not instance.rag_enabled:
        # Si le RAG n'était pas activé, pas de collection à supprimer
        logger.info(f"Chatbot '{instance.name}' supprimé mais RAG non activé → pas de collection à nettoyer")
        return
    
    try:
        # Appeler l'API du RAG Agent pour supprimer la collection
        response = httpx.delete(
            f"{RAG_AGENT_URL}/admin/collection/{instance.name}",
            headers={"X-Admin-Key": RAG_ADMIN_API_KEY},
            timeout=10.0,
        )
        
        if response.status_code == 200:
            logger.info(f" Collection Qdrant supprimée pour le chatbot '{instance.name}'")
        elif response.status_code == 404:
            logger.warning(f" Collection non trouvée pour '{instance.name}' (déjà supprimée ?)")
        else:
            logger.warning(f" Erreur suppression collection '{instance.name}': {response.status_code} - {response.text}")
            
    except httpx.ConnectError:
        logger.warning(f" RAG Agent inaccessible, collection non supprimée pour '{instance.name}'")
    except Exception as e:
        logger.warning(f" Erreur lors de la suppression de la collection '{instance.name}': {e}")