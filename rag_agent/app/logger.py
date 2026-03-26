"""
logger.py — Logging structuré JSON pour le microservice RAG Agent
Chaque log a un trace_id pour tracer une requête de bout en bout
"""
import structlog
import logging
import sys
from app.config import settings


def setup_logging():
    """Configure structlog avec output JSON en production."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Processeurs structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if settings.LOG_LEVEL == "DEBUG":
        # Dev : lisible console
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # Prod : JSON structuré
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Logger stdlib pour uvicorn / fastapi
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str):
    return structlog.get_logger(name)