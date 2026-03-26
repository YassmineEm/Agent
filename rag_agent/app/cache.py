import json
import hashlib
from typing import Optional, Any

import redis.asyncio as aioredis

from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)


class CacheService:
    """
    Service Redis async.
    - Graceful degradation : si Redis est down, le service continue (sans cache)
    - TTL configurable par type de données
    - Rate limiting par IP via compteur Redis
    - Support multi-chatbot : isolation des clés par chatbot_id
    """

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """Connexion Redis (appelé au démarrage FastAPI)."""
        try:
            self._redis = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self._redis.ping()
            log.info("Redis connecté", host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        except Exception as e:
            log.warning("Redis non disponible — cache désactivé", error=str(e))
            self._redis = None

    async def disconnect(self):
        """Ferme la connexion proprement."""
        if self._redis:
            await self._redis.aclose()

    def is_healthy(self) -> bool:
        return self._redis is not None



    def _make_key(self, question: str, chatbot_id: str, doc_type: Optional[str]) -> str:
        """Génère une clé de cache isolée par chatbot."""
        raw = f"{chatbot_id}|{question.strip().lower()}|{doc_type or 'all'}"
        return "rag:response:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def get_cached_response(
        self, question: str, chatbot_id: str, doc_type: Optional[str]
    ) -> Optional[dict]:
        """Retourne la réponse en cache si elle existe, sinon None."""
        if not self._redis:
            return None
        try:
            key = self._make_key(question, chatbot_id, doc_type)
            raw = await self._redis.get(key)
            if raw:
                log.info("Cache HIT", key=key, chatbot_id=chatbot_id)
                return json.loads(raw)
        except Exception as e:
            log.warning("Erreur lecture cache", error=str(e))
        return None

    async def set_cached_response(
        self,
        question: str,
        chatbot_id: str,
        doc_type: Optional[str],
        response: dict,
        ttl: int = None,
    ):
        """Met en cache une réponse RAG."""
        if not self._redis:
            return
        try:
            key = self._make_key(question, chatbot_id, doc_type)
            ttl = ttl or settings.REDIS_TTL_SECONDS
            await self._redis.setex(key, ttl, json.dumps(response, ensure_ascii=False))
            log.info("Cache SET", key=key, chatbot_id=chatbot_id, ttl=ttl)
        except Exception as e:
            log.warning("Erreur écriture cache", error=str(e))



    async def get_session(self, chatbot_id: str, session_id: str) -> list:
        """Récupère l'historique de conversation pour un chatbot spécifique."""
        if not self._redis or not session_id:
            return []
        try:
            raw = await self._redis.get(f"session:{chatbot_id}:{session_id}")
            return json.loads(raw) if raw else []
        except Exception:
            return []

    async def update_session(
        self, chatbot_id: str, session_id: str, question: str, answer: str
    ):
        """Ajoute un échange à l'historique de session."""
        if not self._redis or not session_id:
            return
        try:
            history = await self.get_session(chatbot_id, session_id)
            history.append({"q": question, "a": answer})
            # Garder les 10 derniers échanges max
            history = history[-10:]
            await self._redis.setex(
                f"session:{chatbot_id}:{session_id}",
                settings.REDIS_TTL_SECONDS,
                json.dumps(history, ensure_ascii=False),
            )
        except Exception as e:
            log.warning("Erreur update session", error=str(e))



    async def increment_counter(self, key: str):
        """Compteur de requêtes pour monitoring."""
        if self._redis:
            try:
                await self._redis.incr(f"stats:{key}")
            except Exception:
                pass



    async def check_rate_limit(
        self,
        client_ip: str,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """
        Vérifie si le client a dépassé la limite de requêtes.

        Retourne (is_allowed, remaining_requests).
        """
        if not self._redis:
            return True, max_requests

        key = f"rate_limit:{client_ip}"
        try:
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, window_seconds)

            remaining = max(0, max_requests - current)
            is_allowed = current <= max_requests

            if not is_allowed:
                log.warning(
                    "Rate limit dépassé",
                    client_ip=client_ip,
                    current=current,
                    max_requests=max_requests,
                )
            return is_allowed, remaining

        except Exception as e:
            log.warning("Rate limit check échoué, requête autorisée", error=str(e))
            return True, max_requests


# Singleton
cache_service = CacheService()