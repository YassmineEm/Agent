import os
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET        # ← manquait
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User

from .models import UserProfile, Chatbot

logger = logging.getLogger(__name__)

INTERNAL_SECRET = os.getenv("INTERNAL_API_SECRET", "change_me_in_production")


def _check_secret(request):
    if request.headers.get("X-Internal-Secret", "") != INTERNAL_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


@require_GET
@csrf_exempt
def platform_config_api(request):
    """Config plateforme fixe — lue depuis settings.py, jamais depuis la DB."""
    err = _check_secret(request)
    if err:
        return err

    return JsonResponse({
        "platform_name":      "Afriquia",
        "keycloak_url":       settings.KEYCLOAK_URL,
        "keycloak_realm":     settings.KEYCLOAK_REALM,
        "keycloak_client_id": settings.KEYCLOAK_CLIENT_ID,
        "keycloak_audience":  settings.KEYCLOAK_AUDIENCE,
        "orchestrator_url":   settings.ORCHESTRATOR_URL,
        "jwks_cache_ttl":     settings.JWKS_CACHE_TTL,
    })


@require_GET
@csrf_exempt
def user_chatbots_api(request, user_id: str):
    """Retourne les chatbots autorisés — avec auto-provisioning au premier login."""
    err = _check_secret(request)
    if err:
        return err

    try:
        profile = UserProfile.objects.select_related('user').get(keycloak_id=user_id)
        chatbots = profile.allowed_chatbots.filter(active=True).values(
            "id", "name", "description", "llm_model"
        )
        return JsonResponse(list(chatbots), safe=False)

    except UserProfile.DoesNotExist:
        return _provision_new_user(request, user_id)


def _provision_new_user(request, keycloak_id: str) -> JsonResponse:
    """Crée automatiquement User + UserProfile au premier login."""
    email    = request.GET.get("email",    f"{keycloak_id}@unknown.ma")
    username = request.GET.get("username", keycloak_id[:30])

    logger.info(f"[Auto-provisioning] {email} (keycloak_id={keycloak_id[:8]}…)")

    user, _ = User.objects.get_or_create(
        username=keycloak_id,
        defaults={
            "email":      email,
            "first_name": username,
            "is_active":  True,
            "is_staff":   False,
            "is_superuser": False,
        }
    )

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"keycloak_id": keycloak_id, "role": "viewer"}
    )

    default_chatbots = Chatbot.objects.filter(active=True, is_default=True)
    if default_chatbots.exists():
        profile.allowed_chatbots.set(default_chatbots)

    chatbots = profile.allowed_chatbots.filter(active=True).values(
        "id", "name", "description", "llm_model"
    )
    return JsonResponse(list(chatbots), safe=False)