import re
import uuid
import time
import structlog
import httpx
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from contextlib import asynccontextmanager

from app.graph import run
from langdetect import detect, DetectorFactory
from app.utils.logger import setup_logging, get_logger

setup_logging()
log = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION ADMIN UI
# ══════════════════════════════════════════════════════════════════════════════

ADMIN_API_URL  = os.getenv("ADMIN_API_URL", "http://host.docker.internal:8000")

# FIX: cache avec TTL — la version originale utilisait un dict permanent
# jamais invalidé. Une modification dans l'AdminUI (ajout d'un agent,
# changement de description) était ignorée jusqu'au prochain redémarrage.
_chatbot_configs:    dict[str, dict]  = {}
_chatbot_configs_ts: dict[str, float] = {}
CONFIG_CACHE_TTL = 300  # 5 minutes — suffisant pour éviter les appels répétés


async def get_chatbot_config(chatbot_id: str) -> dict:
    """
    Charge la configuration du chatbot depuis l'AdminUI.
    Résultat mis en cache 5 minutes (TTL).

    Retourne {
        "system_prompt": "role + scope",
        "agent_descriptions": {"sql": "...", "rag": "...", ...}
    }
    """
    now = time.time()

    # FIX: vérifier le TTL avant de servir le cache
    if chatbot_id in _chatbot_configs:
        age = now - _chatbot_configs_ts.get(chatbot_id, 0)
        if age < CONFIG_CACHE_TTL:
            return _chatbot_configs[chatbot_id]
        log.info(
            "Config cache expiré — rechargement depuis AdminUI",
            chatbot_id=chatbot_id,
            age_seconds=int(age),
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{ADMIN_API_URL}/api/chatbots/")
            r.raise_for_status()
            chatbots = r.json().get("chatbots", [])
            chat_id  = next((b["id"] for b in chatbots if b["name"] == chatbot_id), None)

            if not chat_id:
                log.warning("Chatbot non trouvé dans l'AdminUI", chatbot_id=chatbot_id)
                return {"system_prompt": "", "agent_descriptions": {}}

            r2 = await client.get(f"{ADMIN_API_URL}/api/chatbots/{chat_id}/")
            r2.raise_for_status()
            config = r2.json()

        chatbot_data  = config.get("chatbot", {})
        role          = chatbot_data.get("system_prompt", "")
        scope         = chatbot_data.get("scope", "")
        system_prompt = f"{role}\n\nGUARDRAILS:\n{scope}" if scope else role

        agent_descriptions = {}
        for agent in config.get("agents", []):
            agent_type = agent.get("agent_type")
            desc       = agent.get("description")
            if agent_type and desc:
                agent_descriptions[agent_type] = desc

        log.info(
            "Configuration chargée depuis AdminUI",
            chatbot_id=chatbot_id,
            has_system_prompt=bool(system_prompt),
            agent_descriptions_found=list(agent_descriptions.keys()),
        )

        result = {
            "system_prompt":      system_prompt,
            "agent_descriptions": agent_descriptions,
        }

        # FIX: stocker avec timestamp pour le TTL
        _chatbot_configs[chatbot_id]    = result
        _chatbot_configs_ts[chatbot_id] = now

        return result

    except httpx.TimeoutException:
        log.warning("Timeout chargement config AdminUI", chatbot_id=chatbot_id)
        return {"system_prompt": "", "agent_descriptions": {}}
    except Exception as e:
        log.warning("Impossible de charger config AdminUI", chatbot_id=chatbot_id, error=str(e))
        return {"system_prompt": "", "agent_descriptions": {}}


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION AUTOMATIQUE DE LANGUE
# ══════════════════════════════════════════════════════════════════════════════

DetectorFactory.seed = 0


def detect_language(text: str) -> str:
    """
    Détecte la langue de la question.
    Priorité: arabe (détection manuelle) > langdetect > fallback fr
    """
    if re.search(r'[\u0600-\u06FF]', text):
        return "ar"
    try:
        lang = detect(text)
        if lang.startswith('fr'):
            return "fr"
        elif lang.startswith('en'):
            return "en"
        elif lang.startswith('ar'):
            return "ar"
        else:
            return "fr"
    except Exception as e:
        print(f"Lang detection error: {e}")
        return "fr"


def resolve_language(requested: str, question: str) -> str:
    """
    Détermine la langue finale à utiliser.
    Si le frontend envoie "fr" (valeur par défaut), on détecte depuis la question.
    Si le frontend envoie explicitement "ar" ou "en", on respecte.
    """
    if requested and requested.lower() != "fr":
        return requested.lower()
    return detect_language(question)


# ══════════════════════════════════════════════════════════════════════════════
# LIFESPAN
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Orchestrateur AKWA démarré")
    log.info(f"AdminUI URL: {ADMIN_API_URL}")
    yield
    log.info("Orchestrateur AKWA arrêté")


# ══════════════════════════════════════════════════════════════════════════════
# APP
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="AKWA Orchestrateur v2",
    description="Multi-agent orchestrator — SQL · RAG · Location",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# MODÈLES
# ══════════════════════════════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    question:   str
    chatbot_id: str
    session_id: str | None = None
    lat:        float | None = None
    lng:        float | None = None
    language:   str = "fr"

    @validator("question")
    def clean(cls, v):
        return v.strip()


class QueryResponse(BaseModel):
    answer:                 str
    agents_used:            list[str]
    confidence:             float
    from_cache:             bool
    needs_clarification:    bool
    clarification_question: str | None
    routing_method:         str
    trace_id:               str
    language_used:          str
    session_id:             str | None


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(
    req:   QueryRequest,
    debug: bool = Query(False),
):
    session_id = req.session_id or str(uuid.uuid4())
    language   = resolve_language(req.language, req.question)

    config             = await get_chatbot_config(req.chatbot_id)
    system_prompt      = config["system_prompt"]
    agent_descriptions = config["agent_descriptions"]

    log.info(
        "Requête reçue",
        question=req.question[:60],
        language_requested=req.language,
        language_resolved=language,
        has_geo=bool(req.lat and req.lng),
        session_id=session_id,
        system_prompt_length=len(system_prompt),
        agent_descriptions=list(agent_descriptions.keys()),
    )

    result = await run(
        question           = req.question,
        chatbot_id         = req.chatbot_id,
        session_id         = session_id,
        geo                = {"lat": req.lat, "lng": req.lng} if req.lat and req.lng else None,
        language           = language,
        system_prompt      = system_prompt,
        agent_descriptions = agent_descriptions,
    )

    if debug:
        return {**result, "language_used": language, "debug": True}

    return QueryResponse(
        answer                 = result.get("final_answer", ""),
        agents_used            = result.get("agents_used", []),
        confidence             = result.get("confidence", 0.0),
        from_cache             = result.get("from_cache", False),
        needs_clarification    = result.get("needs_clarification", False),
        clarification_question = result.get("clarification_question"),
        routing_method         = result.get("routing_method", ""),
        trace_id               = result.get("trace_id", ""),
        language_used          = language,
        session_id             = session_id,
    )


@app.get("/health")
async def health():
    from app.services.memory import r
    return {
        "status":        "healthy",
        "redis":         r is not None,
        "version":       "2.0.0",
        "admin_api_url": ADMIN_API_URL,
    }


@app.get("/config/cache")
async def get_config_cache():
    """Endpoint de debug — configs en cache avec leur âge."""
    now = time.time()
    return {
        "cached_chatbots": {
            cid: {
                "age_seconds": int(now - _chatbot_configs_ts.get(cid, 0)),
                "ttl_seconds": CONFIG_CACHE_TTL,
                "expires_in":  max(0, int(CONFIG_CACHE_TTL - (now - _chatbot_configs_ts.get(cid, 0)))),
            }
            for cid in _chatbot_configs
        },
        "cache_size": len(_chatbot_configs),
    }


@app.post("/config/cache/clear")
async def clear_config_cache():
    """Vide le cache des configurations (utile après modification dans l'AdminUI)."""
    _chatbot_configs.clear()
    _chatbot_configs_ts.clear()
    log.info("Cache des configurations vidé")
    return {"status": "cleared"}