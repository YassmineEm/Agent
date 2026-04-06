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


def _make_key(question: str, chatbot_id: str = "") -> str:
    # Normalisation : minuscules, sans ponctuation finale, espaces réduits
    normalized = question.lower().strip().rstrip("?!.").strip()
    normalized = " ".join(normalized.split())
    raw = f"{chatbot_id}|{normalized}"
    return "orch:resp:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_cache(question: str, chatbot_id: str = "") -> dict | None:
    if not r:
        return None
    try:
        key = _make_key(question, chatbot_id)
        raw = r.get(key)
        if raw:
            log.info("Cache HIT", key=key[:20])
            return json.loads(raw)
    except Exception as e:
        log.warning("Erreur lecture cache", error=str(e))
    return None


def save_cache(question: str, response: dict, chatbot_id: str = ""):
    if not r:
        return
    try:
        key = _make_key(question, chatbot_id)
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
        r.setex(f"orch:session:{session_id}:last_agent", 1800, agent)  # 30min
    except Exception:
        pass

SESSION_SUMMARY_TTL = 1800  # 30 minutes d'inactivité → résumé oublié
 
 
def get_session_summary(session_id: str) -> str | None:
    """
    Retourne le résumé de la session courante.
 
    Le résumé est en français (langue de stockage interne).
    Retourne None si absent ou expiré (TTL dépassé).
    """
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
    """
    Sauvegarde le résumé de session avec TTL.
 
    Le résumé est reset à 30 min à chaque mise à jour.
    Une session inactive depuis 30 min repart de zéro.
    """
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
        import json
        turn = json.dumps({"q": question[:200], "a": answer[:300]})
        r.rpush(key, turn)
        r.ltrim(key, -6, -1)   # garde les 6 derniers tours
        r.expire(key, SESSION_SUMMARY_TTL)
    except Exception as e:
        log.warning("Erreur sauvegarde turn brut", error=str(e))


def get_recent_turns(session_id: str) -> list[dict]:
    """Récupère les tours bruts récents pour injecter dans le contexte."""
    if not r or not session_id:
        return []
    key = f"orch:session:{session_id}:turns"
    try:
        import json
        items = r.lrange(key, 0, -1)
        return [json.loads(i) for i in items]
    except Exception:
        return []