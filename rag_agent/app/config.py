"""
config.py — Configuration centralisée du microservice RAG Agent
Toutes les variables sont lues depuis .env (jamais hardcodées)
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    OLLAMA_BASE_URL: str
    RAG_LLM_MODEL: str = "qwen3:8b"

    EMBED_MODEL:       str = "bge-m3"
    EMBED_VECTOR_SIZE: int = 1024

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "akwa_knowledge"

    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    TOP_K_RETRIEVE: int = 20
    TOP_K_FINAL: int = 4
    MIN_CONFIDENCE_SCORE: float = 0.3

    # ── API ───────────────────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8005
    API_SECRET_KEY: str  
    ADMIN_API_KEY: str    

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_TTL_SECONDS: int = 3600

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


    VISION_MODEL: str = "qwen2.5vl"
    VISION_MIN_IMAGE_BYTES: int = 5000
    VISION_TIMEOUT: int = 120
    VISION_ENABLED: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Singleton — settings chargés une seule fois."""
    return Settings()


settings = get_settings()