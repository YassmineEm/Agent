import re
import uuid
import structlog
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from contextlib import asynccontextmanager

from app.graph import run
from app.utils.logger import setup_logging, get_logger

setup_logging()
log = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION AUTOMATIQUE DE LANGUE
# ══════════════════════════════════════════════════════════════════════════════

def detect_language(text: str) -> str:
    """
    Détecte la langue de la question depuis le texte brut.
    Priorité : arabe > anglais > français (défaut).

    - Arabe  : présence d'un caractère dans le bloc Unicode arabe (U+0600–U+06FF)
    - Anglais: présence d'au moins 1 mot-clé anglais courant
    - Français: défaut si rien ne matche
    """
    # ── Arabe ─────────────────────────────────────────────────────────────────
    if re.search(r'[\u0600-\u06FF]', text):
        return "ar"

    # ── Anglais ───────────────────────────────────────────────────────────────
    english_markers = {
        "what", "where", "when", "how", "which", "who", "why",
        "is", "are", "was", "were", "the", "a", "an",
        "nearest", "closest", "station", "show", "find",
        "weather", "price", "give", "tell", "me", "my",
        "can", "could", "please", "want", "need", "get",
    }
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if words & english_markers:
        return "en"

    # ── Français (défaut) ─────────────────────────────────────────────────────
    return "fr"


def resolve_language(requested: str, question: str) -> str:
    """
    Détermine la langue finale à utiliser.

    Règle :
    - Si le front-end envoie explicitement une langue ≠ "fr" → on la respecte
    - Si le front-end envoie "fr" (valeur par défaut) → on détecte depuis la question
      car le front-end n'a peut-être pas géré l'envoi de la langue

    Ainsi, un front-end qui envoie toujours "fr" sera corrigé automatiquement,
    mais un front-end qui envoie explicitement "ar" ou "en" sera toujours respecté.
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
    language:   str = "fr"          # le front-end peut forcer la langue ici

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
    language_used:          str     # ← utile pour debug front-end


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(
    req: QueryRequest,
    debug: bool = Query(False),
):
    # Résolution finale de la langue (détection auto si front-end envoie "fr" par défaut)
    language = resolve_language(req.language, req.question)

    log.info(
        "Requête reçue",
        question=req.question[:60],
        language_requested=req.language,
        language_resolved=language,
        has_geo=bool(req.lat and req.lng),
    )

    result = await run(
        question   = req.question,
        chatbot_id = req.chatbot_id,
        session_id = req.session_id,
        geo        = {"lat": req.lat, "lng": req.lng} if req.lat and req.lng else None,
        language   = language,
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
    )


@app.get("/health")
async def health():
    from app.services.memory import r
    return {
        "status":  "healthy",
        "redis":   r is not None,
        "version": "2.0.0",
    }