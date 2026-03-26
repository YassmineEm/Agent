"""
main.py — Application FastAPI du microservice RAG Agent

Endpoints :
  POST /query                      → Question → Réponse RAG (rate limit : 10 req/min/IP)
  POST /admin/upload               → Upload document (admin seulement)
  GET  /admin/documents            → Lister les documents indexés (admin)
  DELETE /admin/documents/{name}   → Supprimer un document (admin)
  GET  /admin/stats                → Statistiques (admin seulement)
  GET  /health                     → Statut du service
  GET  /docs                       → Swagger UI automatique
"""
import time
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, UploadFile, File, Form, HTTPException, Query,
    Request, Depends, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import structlog

from .config import settings
from .logger import setup_logging, get_logger
from .models import (
    QueryRequest, QueryResponse,
    IngestResponse, HealthResponse, ErrorResponse,
    DocType, DeleteResponse
)
from .agent import rag_agent
from .ingestion import ingestion
from .cache import cache_service
from .qdrant_store import qdrant_store
from .security import require_admin_key, generate_trace_id

setup_logging()
log = get_logger(__name__)

# ── Constantes rate limiting ──────────────────────────────────────────────────
RATE_LIMIT_MAX_REQUESTS = 10   # requêtes max par fenêtre
RATE_LIMIT_WINDOW_SEC   = 60   # fenêtre en secondes


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Démarrage RAG Agent microservice", version="1.0.0")

    await cache_service.connect()

    # Note: Plus de setup_collection() automatique car les collections sont créées
    # dynamiquement à l'upload. La collection par défaut est créée à la demande.
    log.info(
        "RAG Agent prêt à recevoir des requêtes",
        port=settings.API_PORT,
        rate_limit=f"{RATE_LIMIT_MAX_REQUESTS} req/{RATE_LIMIT_WINDOW_SEC}s par IP",
    )

    yield

    log.info("Arrêt du RAG Agent...")
    await cache_service.disconnect()
    log.info("RAG Agent arrêté proprement")


# ── Application FastAPI ────────────────────────────────────────────────────────

app = FastAPI(
    title="AKWA RAG Agent",
    description="Microservice RAG — Retrieval-Augmented Generation pour documents AKWA Gaz & Carburant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware logging ────────────────────────────────────────────────────────

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
    start = time.time()

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    log.info(
        "Requête reçue",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown",
    )

    response = await call_next(request)
    elapsed = round(time.time() - start, 3)

    log.info("Requête traitée", status=response.status_code, elapsed_s=elapsed)

    response.headers["X-Trace-ID"] = trace_id
    response.headers["X-Response-Time"] = str(elapsed)
    return response


# ── Handler d'erreurs global ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = request.headers.get("X-Trace-ID", "unknown")
    log.error("Erreur non gérée", error=str(exc), path=request.url.path, trace_id=trace_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Erreur interne du serveur",
            detail=str(exc) if settings.LOG_LEVEL == "DEBUG" else None,
            trace_id=trace_id,
        ).model_dump(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

# ── POST /query ───────────────────────────────────────────────────────────────

@app.post(
    "/query",
    response_model=QueryResponse,
    summary="Interroger la base de connaissances AKWA",
    tags=["RAG"],
    responses={
        429: {"description": "Trop de requêtes — limite dépassée"},
    },
)
async def query_rag(req: QueryRequest, request: Request) -> QueryResponse:
    """
    **Endpoint principal du RAG Agent.**

    Prend une question en langage naturel, cherche dans les documents du chatbot
    via Hybrid Search (Dense bge-m3 + BM25) + Reranking, génère une réponse avec qwen3:8b.

    La langue est détectée automatiquement (FR / AR / EN).
    Chaque chatbot a sa propre collection isolée dans Qdrant.

    **Rate limiting :** 10 requêtes par minute par IP.
    Au-delà → HTTP 429 avec header `Retry-After: 60`.
    """
    trace_id = request.headers.get("X-Trace-ID", generate_trace_id())
    client_ip = request.client.host if request.client else "unknown"

    # ── Rate limiting : 10 requêtes / 60 secondes par IP ─────────────────────
    is_allowed, remaining = await cache_service.check_rate_limit(
        client_ip=client_ip,
        max_requests=RATE_LIMIT_MAX_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SEC,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Trop de requêtes. Limite : {RATE_LIMIT_MAX_REQUESTS} requêtes "
                   f"par {RATE_LIMIT_WINDOW_SEC} secondes.",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW_SEC)},
        )

    try:
        result = await rag_agent.query(
            question=req.question,
            chatbot_id=req.chatbot_id,  # ← NOUVEAU : identifiant du chatbot
            doc_type_filter=req.doc_type_filter.value if req.doc_type_filter else None,
            session_id=req.session_id,
            trace_id=trace_id,
            language=req.language,
        )
        return result

    except Exception as e:
        log.error("Erreur query RAG", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du traitement de la requête: {str(e)}",
        )


# ── POST /admin/upload ────────────────────────────────────────────────────────

@app.post(
    "/admin/upload",
    response_model=IngestResponse,
    summary="Uploader un document dans la base de connaissances",
    tags=["Admin"],
    dependencies=[Depends(require_admin_key)],
)
async def upload_document(
    file: UploadFile = File(..., description="Fichier : PDF, DOCX, CSV, XLSX, TXT, JSON, MD"),
    chatbot_id: str = Form(..., description="ID du chatbot cible"),
    doc_type: DocType = Form(default=DocType.GENERAL, description="Type de document (optionnel)"),
    description: str = Form(default="", description="Description optionnelle"),
) -> IngestResponse:
    """
    **Upload et indexation d'un document dans Qdrant.**

    Réservé aux administrateurs (header `X-Admin-Key` requis).
    Chaque chatbot a sa propre collection isolée.

    Le document est automatiquement :
    1. Découpé en chunks (512 tokens, overlap 64)
    2. Enrichi avec les métadonnées (doc_type, filename...)
    3. Indexé en Dense (bge-m3) + Sparse (BM25) dans Qdrant

    **Types acceptés :** PDF, DOCX/DOC, CSV, XLSX/XLS, TXT, JSON, Markdown
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant.")

    import os as _os
    from .ingestion import SUPPORTED_EXTENSIONS
    ext = _os.path.splitext(file.filename.lower())[1]
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté : '{file.filename}'. Acceptés : {supported}",
        )

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux. Maximum: 50 MB")

    log.info(
        "Upload document",
        filename=file.filename,
        chatbot_id=chatbot_id,
        doc_type=doc_type,
        size_kb=len(content) // 1024,
    )

    try:
        # Créer la collection si elle n'existe pas
        qdrant_store.ensure_collection(chatbot_id)
        
        result = await ingestion.ingest_file(
            file_bytes=content,
            filename=file.filename,
            doc_type=doc_type.value,
            collection=chatbot_id,  # ← Utilise chatbot_id comme nom de collection
            description=description,
        )
        return IngestResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Erreur ingestion", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'indexation: {str(e)}")


# ── GET /health ───────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Statut du service",
    tags=["Monitoring"],
)
async def health_check() -> HealthResponse:
    """Vérifie la connexion Qdrant, Redis et le modèle LLM configuré."""
    qdrant_ok = qdrant_store.is_healthy()
    redis_ok = cache_service.is_healthy()

    return HealthResponse(
        status="healthy" if qdrant_ok else "degraded",
        model=settings.RAG_LLM_MODEL,
        qdrant_connected=qdrant_ok,
        redis_connected=redis_ok,
        vision_enabled=settings.VISION_ENABLED,
        vision_model=settings.VISION_MODEL if settings.VISION_ENABLED else None,
    )


# ── GET /admin/stats ──────────────────────────────────────────────────────────

@app.get(
    "/admin/stats",
    summary="Statistiques du service",
    tags=["Admin"],
    dependencies=[Depends(require_admin_key)],
)
async def get_stats(chatbot_id: str = Query(..., description="ID du chatbot")) -> dict:
    """Retourne les statistiques de requêtes pour un chatbot spécifique."""
    if not cache_service.is_healthy():
        return {"error": "Redis non disponible"}

    stats = {}
    for key in [f"rag_queries:{chatbot_id}", f"rag_cache_hits:{chatbot_id}"]:
        try:
            val = await cache_service._redis.get(f"stats:{key}")
            stats[key] = int(val) if val else 0
        except Exception:
            stats[key] = 0

    queries = stats.get(f"rag_queries:{chatbot_id}", 0)
    hits = stats.get(f"rag_cache_hits:{chatbot_id}", 0)
    
    stats["cache_hit_rate"] = round(hits / queries * 100, 1) if queries > 0 else 0
    stats["collection"] = chatbot_id
    stats["rate_limit"] = f"{RATE_LIMIT_MAX_REQUESTS} req/{RATE_LIMIT_WINDOW_SEC}s par IP"
    stats["vision_enabled"] = settings.VISION_ENABLED
    stats["vision_model"] = settings.VISION_MODEL if settings.VISION_ENABLED else None
    return stats


# ── GET /admin/documents ──────────────────────────────────────────────────────

@app.get(
    "/admin/documents",
    summary="Lister tous les documents indexés",
    tags=["Admin"],
    dependencies=[Depends(require_admin_key)],
)
async def list_documents(chatbot_id: str = Query(..., description="ID du chatbot")) -> list:
    """
    **Liste tous les documents indexés pour un chatbot spécifique.**

    Retourne 1 entrée par document avec le nombre de chunks.
    """
    try:
        return qdrant_store.list_documents(chatbot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur listing : {str(e)}")


# ── DELETE /admin/documents/{filename} ───────────────────────────────────────

@app.delete(
    "/admin/documents/{filename}",
    response_model=DeleteResponse,
    summary="Supprimer un document de la base de connaissances",
    tags=["Admin"],
    dependencies=[Depends(require_admin_key)],
)
async def delete_document(
    filename: str,
    chatbot_id: str = Query(..., description="ID du chatbot")
) -> DeleteResponse:
    """
    **Supprime tous les chunks d'un document par son nom de fichier.**

    Le filename doit correspondre exactement au nom utilisé lors de l'upload.
    """
    try:
        chunks_deleted = qdrant_store.delete_document(
            collection_name=chatbot_id,
            filename=filename,
        )

        if chunks_deleted == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{filename}' non trouvé pour le chatbot '{chatbot_id}'.",
            )

        log.info("Suppression document via API", filename=filename, chatbot_id=chatbot_id, chunks=chunks_deleted)

        return DeleteResponse(
            status="deleted",
            filename=filename,
            collection=chatbot_id,
            chunks_deleted=chunks_deleted,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur suppression : {str(e)}")


# ── GET / ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
async def root():
    return {
        "service": "AKWA RAG Agent",
        "version": "1.0.0",
        "status": "running",
        "rate_limit": f"{RATE_LIMIT_MAX_REQUESTS} req/{RATE_LIMIT_WINDOW_SEC}s par IP",
        "docs": "/docs",
        "health": "/health",
        "vision_enabled": settings.VISION_ENABLED,
        "vision_model": settings.VISION_MODEL if settings.VISION_ENABLED else None,
    }