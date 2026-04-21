import hashlib
import json
import redis as sync_redis
from app.config import REDIS_HOST, REDIS_PORT, REDIS_TTL
from app.utils.logger import get_logger

log = get_logger(__name__)

try:
    r = sync_redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    log.info("Redis connecté", host=REDIS_HOST, port=REDIS_PORT)
except Exception as e:
    r = None
    log.warning("Redis indisponible — cache désactivé", error=str(e))


def _make_key(question: str, chatbot_id: str = "", geo: dict = None) -> str:
    """
    Construit la clé de cache Redis.

    FIX: la version originale ignorait la géolocalisation.
    Deux utilisateurs à des positions différentes posant la même question
    (ex: 'station la plus proche') recevaient la même réponse cachée.

    Désormais, lat/lng sont arrondis à 2 décimales (~1 km de précision)
    et inclus dans la clé. Les questions sans geo conservent le même
    comportement qu'avant.
    """
    normalized = question.lower().strip().rstrip("?!.").strip()
    normalized = " ".join(normalized.split())

    # FIX: inclure la position GPS arrondie à ~1 km de précision
    geo_part = ""
    if geo and geo.get("lat") is not None and geo.get("lng") is not None:
        try:
            geo_part = f"|{round(float(geo['lat']), 2)},{round(float(geo['lng']), 2)}"
        except (ValueError, TypeError):
            pass  # geo malformé → ignoré, clé sans geo

    raw = f"{chatbot_id}|{normalized}{geo_part}"
    return "orch:resp:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_cache(question: str, chatbot_id: str = "", geo: dict = None) -> dict | None:
    """
    Retourne la réponse cachée ou None.

    FIX: accepte geo pour construire une clé unique par position.
    """
    if not r:
        return None
    try:
        key = _make_key(question, chatbot_id, geo)
        raw = r.get(key)
        if raw:
            log.info("Cache HIT", key=key[:20])
            return json.loads(raw)
    except Exception as e:
        log.warning("Erreur lecture cache", error=str(e))
    return None


def save_cache(question: str, response: dict, chatbot_id: str = "", geo: dict = None):
    """
    Sauvegarde la réponse en cache.

    FIX: accepte geo pour construire une clé unique par position.
    """
    if not r:
        return
    try:
        key = _make_key(question, chatbot_id, geo)
        r.setex(key, REDIS_TTL, json.dumps(response, ensure_ascii=False))
        log.info("Cache SET", key=key[:20], ttl=REDIS_TTL)
    except Exception as e:
        log.warning("Erreur écriture cache", error=str(e))


def get_session_last_agent(session_id: str) -> str | None:
    """Retourne le dernier agent utilisé dans cette session."""
    if not r or not session_id:
        return None
    try:
        return r.get(f"orch:session:{session_id}:last_agent")
    except Exception:
        return None


def save_session_agent(session_id: str, agent: str):
    if not r or not session_id:
        return
    try:
        r.setex(f"orch:session:{session_id}:last_agent", 1800, agent)
    except Exception:
        pass


SESSION_SUMMARY_TTL = 1800  # 30 minutes d'inactivité → résumé oublié


def get_session_summary(session_id: str) -> str | None:
    """Retourne le résumé de la session courante."""
    if not r or not session_id:
        return None
    try:
        value = r.get(f"orch:session:{session_id}:summary")
        if value:
            log.info("Session summary found", session_id=session_id[:8], length=len(value))
        return value
    except Exception as e:
        log.warning("Erreur lecture summary", error=str(e))
        return None


def save_session_summary(session_id: str, summary: str):
    """Sauvegarde le résumé de session avec TTL."""
    if not r or not session_id or not summary:
        return
    try:
        r.setex(
            f"orch:session:{session_id}:summary",
            SESSION_SUMMARY_TTL,
            summary,
        )
        log.info("Session summary saved", session_id=session_id[:8], length=len(summary))
    except Exception as e:
        log.warning("Erreur sauvegarde summary", error=str(e))


def _save_raw_turn(session_id: str, question: str, answer: str) -> None:
    """Stocke les tours bruts récents (tampon court terme, max 6 entrées)."""
    if not r or not session_id:
        return
    key = f"orch:session:{session_id}:turns"
    try:
        turn = json.dumps({"q": question[:200], "a": answer[:300]})
        r.rpush(key, turn)
        r.ltrim(key, -6, -1)
        r.expire(key, SESSION_SUMMARY_TTL)
    except Exception as e:
        log.warning("Erreur sauvegarde turn brut", error=str(e))


def get_recent_turns(session_id: str) -> list[dict]:
    """Récupère les tours bruts récents pour injecter dans le contexte."""
    if not r or not session_id:
        return []
    key = f"orch:session:{session_id}:turns"
    try:
        items = r.lrange(key, 0, -1)
        return [json.loads(i) for i in items]
    except Exception:
        return []


def get_turn_count(session_id: str) -> int:
    """Récupère le compteur de tours de la session depuis Redis."""
    if not r or not session_id:
        return 0
    try:
        val = r.get(f"orch:session:{session_id}:turn_count")
        return int(val) if val else 0
    except Exception:
        return 0


def save_turn_count(session_id: str, count: int):
    """Persiste le compteur de tours en Redis."""
    if not r or not session_id:
        return
    try:
        r.setex(f"orch:session:{session_id}:turn_count", SESSION_SUMMARY_TTL, str(count))
    except Exception:
        pass