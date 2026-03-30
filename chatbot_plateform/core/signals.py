import logging
import os

import httpx
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from core.models import Document, UserProfile

logger = logging.getLogger(__name__)

AUTH_GATEWAY_URL    = os.getenv("AUTH_GATEWAY_URL",    "http://auth-gateway:9000")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "change_me_in_production")


# ── Signal existant — inchangé ─────────────────────────────────────
@receiver(post_save, sender=Document)
def process_document_after_upload(sender, instance, created, **kwargs):
    if created and not instance.is_processed:
        try:
            from chatbot_runtime.rag_pipeline.pipeline import RAGPipeline
            print(f"[Signal] Nouveau document détecté : '{instance.title}'")
            RAGPipeline().process_document(instance)
        except Exception as e:
            logger.error(f"[Signal RAG] Erreur : {e}")


# ── NOUVEAU : invalider cache chatbots quand allowed_chatbots change
@receiver(m2m_changed, sender=UserProfile.allowed_chatbots.through)
def invalidate_gateway_user_cache(sender, instance, action, **kwargs):
    """
    Quand l'admin ajoute/retire un chatbot dans UserProfile.allowed_chatbots
    → notifier le gateway de vider le cache de cet utilisateur.
    """
    if action not in ("post_add", "post_remove", "post_clear"):
        return

    # Récupère le keycloak_id de cet utilisateur
    keycloak_id = getattr(instance, "keycloak_id", None)
    if not keycloak_id:
        logger.warning(
            f"[Signal] UserProfile {instance} n'a pas de keycloak_id — "
            "cache non invalidé. Renseignez le keycloak_id dans Django Admin."
        )
        return

    try:
        resp = httpx.post(
            f"{AUTH_GATEWAY_URL}/internal/invalidate-user-cache/{keycloak_id}",
            headers={"X-Internal-Secret": INTERNAL_API_SECRET},
            timeout=3.0,
        )
        if resp.status_code == 200:
            logger.info(f"[Signal] Cache chatbots invalidé pour user {keycloak_id}")
        else:
            logger.warning(f"[Signal] Invalidation user cache retourné {resp.status_code}")
    except Exception as e:
        logger.warning(f"[Signal] Gateway injoignable pour invalidation user cache : {e}")