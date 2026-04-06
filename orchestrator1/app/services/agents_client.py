import httpx
import time
from app.config import AGENT_URLS, AGENT_TIMEOUT
from app.utils.logger import get_logger

log = get_logger(__name__)

_failures:   dict[str, int]   = {}
_open_until: dict[str, float] = {}
CB_THRESHOLD = 3
CB_TIMEOUT   = 60

# ── Phrases d'échec métier à détecter ────────────────────────────────────────
FAILURE_PHRASES = [
    # Français
    "je ne peux pas répondre",
    "je n'ai pas",
    "je n'ai aucune",
    "aucune information",
    "aucun résultat",
    "aucune donnée",
    "données non disponibles",
    "données insuffisantes",
    "pas de données",
    "pas d'information",
    "pas de résultat",
    "introuvable",
    "non disponible",
    "impossible de répondre",
    "je ne sais pas",
    "aucune réponse",
    "je ne trouve pas",
    "résultat vide",
    "tableau vide",
    "aucun enregistrement",
    # Anglais (le planner génère parfois des questions en anglais)
    "cannot answer",
    "can't answer",
    "no data",
    "no result",
    "no information",
    "not available",
    "not found",
    "unable to answer",
    "unable to find",
    "i don't know",
    "i do not know",
    "no records found",
    "empty result",
    "no rows",
]

# Longueur minimale pour qu'une réponse soit considérée valide
MIN_ANSWER_LENGTH = 15


def _is_failure_answer(answer: str) -> bool:
    """
    Détecte si une réponse est un échec métier déguisé en succès HTTP 200.
    Ex : "Je ne peux pas répondre à cette question avec les données disponibles."
    """
    if not answer:
        return True

    normalized = answer.lower().strip()

    # Trop court = probablement inutile
    if len(normalized) < MIN_ANSWER_LENGTH:
        return True

    # Contient une phrase d'échec connue
    for phrase in FAILURE_PHRASES:
        if phrase in normalized:
            log.warning(
                "Réponse agent détectée comme échec métier",
                phrase_détectée=phrase,
                answer_preview=answer[:80],
            )
            return True

    return False


def _can_call(agent: str) -> bool:
    if agent in _open_until:
        if time.time() < _open_until[agent]:
            log.warning("Circuit OPEN", agent=agent)
            return False
        else:
            del _open_until[agent]
            _failures[agent] = 0
            log.info("Circuit HALF-OPEN", agent=agent)
    return True


def _record_failure(agent: str):
    _failures[agent] = _failures.get(agent, 0) + 1
    if _failures[agent] >= CB_THRESHOLD:
        _open_until[agent] = time.time() + CB_TIMEOUT
        log.warning("Circuit OPENED", agent=agent, pause=CB_TIMEOUT)


def _record_success(agent: str):
    _failures[agent] = 0


def _normalize_response(agent: str, raw: dict) -> dict:
    """
    Normalise la réponse de n'importe quel agent
    vers un format uniforme attendu par l'orchestrateur.

    Format cible :
    {
        "answer":     str,
        "confidence": float,
        "agent":      str,
        "_success":   bool,
        "metadata":   dict
    }
    """
    # ── Extraire l'answer ────────────────────────────────────────────────────
    answer = (
        raw.get("answer") or
        raw.get("response") or
        raw.get("result") or
        raw.get("text") or
        ""
    )
    answer = str(answer).strip() if answer else ""

    # ── Extraire la confidence ───────────────────────────────────────────────
    confidence = float(
        raw.get("confidence") or
        raw.get("score") or
        raw.get("similarity") or
        0.5
    )

    # ── Normaliser le nom de l'agent ─────────────────────────────────────────
    agent_name_map = {
        "rag_agent":      "rag",
        "sql_agent":      "sql",
        "location_agent": "location",
    }
    normalized_agent = agent_name_map.get(
        raw.get("agent", agent), agent
    )

    # ── Construire les métadonnées spécifiques par agent ─────────────────────
    if agent == "sql":
        metadata = {
            "selected_db": raw.get("metadata", {}).get("selected_db") or raw.get("selected_db"),
            "db_name":     raw.get("metadata", {}).get("db_name")     or raw.get("db_name"),
            "sql":         raw.get("metadata", {}).get("sql")         or raw.get("sql"),
            "error":       raw.get("metadata", {}).get("error")       or raw.get("error"),
            "rows":        raw.get("metadata", {}).get("rows") or raw.get("rows", []),
        }
    elif agent == "rag":
        metadata = {
            "sources":     raw.get("sources", []),
            "chunks_used": raw.get("chunks_used", 0),
            "model_used":  raw.get("model_used", ""),
        }
    elif agent == "location":
        metadata = {
            "locations": raw.get("locations", []),
            "map_url":   raw.get("map_url", ""),
        }
    else:
        metadata = {}

    # ── Déterminer _success avec détection des faux succès ───────────────────
    is_failure = _is_failure_answer(answer)
    is_success = bool(answer) and not is_failure

    # Si c'est un faux succès → réduire la confidence à 0
    if not is_success and answer:
        confidence = 0.0
        log.warning(
            "Faux succès détecté — réponse marquée _success=False",
            agent=normalized_agent,
            answer_preview=answer[:80],
        )

    return {
        "answer":     answer if is_success else "",
        "confidence": confidence,
        "agent":      normalized_agent,
        "_success":   is_success,
        "metadata":   metadata,
    }


async def call_agent(agent: str, question: str, chatbot_id: str = "",extra:      dict = None,language:   str = "fr",) -> dict:
    if not _can_call(agent):
        return {
            "agent":    agent,
            "answer":   None,
            "error":    "circuit_open",
            "_success": False,
            "metadata": {}
        }

    url = AGENT_URLS.get(agent)
    if not url:
        return {
            "agent":    agent,
            "answer":   None,
            "error":    "unknown_agent",
            "_success": False,
            "metadata": {}
        }

    payload = {"question": question, "chatbot_id": chatbot_id, "language":   language,}
    if extra:
        payload.update(extra)

    try:
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            raw  = res.json()

            data = _normalize_response(agent, raw)

            # ── Circuit breaker : ne compte pas comme succès si faux succès ──
            if data["_success"]:
                _record_success(agent)
            else:
                # Echec métier : on ne pénalise pas le circuit breaker
                # (le service HTTP est UP, c'est la donnée qui manque)
                log.info(
                    "Agent répondu mais sans donnée valide",
                    agent=data["agent"],
                    answer_preview=str(raw.get("answer", ""))[:80],
                )

            log.info(
                "Agent OK" if data["_success"] else "Agent KO (faux succès)",
                agent=data["agent"],
                success=data["_success"],
                confidence=round(data["confidence"], 2),
                answer_length=len(str(data.get("answer", ""))),
            )
            return data

    except httpx.TimeoutException:
        _record_failure(agent)
        log.warning("Agent timeout", agent=agent, timeout=AGENT_TIMEOUT)
        return {
            "agent":    agent,
            "answer":   None,
            "error":    "timeout",
            "_success": False,
            "metadata": {}
        }

    except Exception as e:
        _record_failure(agent)
        log.error("Agent error", agent=agent, error=str(e))
        return {
            "agent":    agent,
            "answer":   None,
            "error":    str(e),
            "_success": False,
            "metadata": {}
        }