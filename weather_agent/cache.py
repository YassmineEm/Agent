import redis.asyncio as aioredis
import hashlib
import json
import os
from typing import Optional

_redis_client: Optional[aioredis.Redis] = None


def _get_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_WEATHER_URL", "redis://localhost:6381")
        _redis_client = aioredis.from_url(url, decode_responses=True)
    return _redis_client


# TTL calibrés selon la volatilité des données
TTL_BY_INTENT: dict[str, int] = {
    "current":  600,    # 10 minutes — change fréquemment
    "forecast": 3600,   # 1 heure    — stable sur la journée
    "alert":    300,    # 5 minutes  — critique, refrais fréquent
}


def _make_key(lat: float, lng: float, intent: str, days: int) -> str:
    raw = f"{lat:.3f}:{lng:.3f}:{intent}:{days}"
    digest = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"wthr:{digest}"


async def get(lat: float, lng: float, intent: str, days: int) -> Optional[dict]:
    try:
        client = _get_client()
        value = await client.get(_make_key(lat, lng, intent, days))
        return json.loads(value) if value else None
    except Exception:
        return None


async def set(lat: float, lng: float, intent: str, days: int, data: dict) -> None:
    try:
        client = _get_client()
        ttl    = TTL_BY_INTENT.get(intent, 600)
        key    = _make_key(lat, lng, intent, days)
        await client.setex(key, ttl, json.dumps(data, ensure_ascii=False))
    except Exception:
        pass  # Le cache est non-bloquant — une erreur Redis ne fait pas planter l'agent