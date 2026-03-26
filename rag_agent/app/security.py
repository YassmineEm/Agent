"""
security.py — Middleware de sécurité
- Validation clé API pour les routes admin
- Génération et validation des trace_id
- Header validation
"""
import uuid
from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)

# Schéma de sécurité pour swagger UI
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def require_admin_key(
    x_admin_key: str = Security(api_key_header),
) -> str:
    """
    Dependency FastAPI pour les routes admin.
    Vérifie la clé API dans le header X-Admin-Key.
    """
    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        log.warning("Tentative d'accès admin non autorisée")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clé API admin invalide ou manquante. Header requis: X-Admin-Key",
        )
    return x_admin_key


def generate_trace_id() -> str:
    """Génère un ID unique pour tracer une requête dans les logs."""
    return str(uuid.uuid4())[:8]