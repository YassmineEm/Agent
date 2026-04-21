"""
models.py — Schémas Pydantic pour le RAG Agent
Validation stricte de toutes les entrées/sorties
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum


class DocType(str, Enum):
    """Types de documents acceptés dans Qdrant."""
    FICHE_TECHNIQUE = "fiche_technique"
    FAQ = "faq"
    NORME = "norme"
    VEHICULE = "vehicule"
    PROCEDURE = "procedure"
    GENERAL = "general"


class QueryRequest(BaseModel):
    """Requête client → RAG Agent. Une seule collection, pas besoin de la préciser."""
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Question de l'utilisateur en langage naturel"
    )
    chatbot_id: str = Field(
        ..., 
        min_length=1, 
        description="ID du chatbot (définit la collection Qdrant)"
    )
    doc_type_filter: Optional[DocType] = Field(
        default=None,
        description="Filtrer par type de document (optionnel)"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="ID session pour la mémoire conversationnelle"
    )
    language: str = Field(
        default="auto",
        description="Langue de la réponse (auto-détectée si non précisée)"
    )

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La question ne peut pas être vide.")
        return v.strip()


class IngestRequest(BaseModel):
    """Métadonnées pour l'upload d'un document."""
    chatbot_id: str = Field(..., description="ID du chatbot cible")
    doc_type: DocType = DocType.GENERAL
    description: Optional[str] = None


class SourceDoc(BaseModel):
    """Source citée dans la réponse."""
    filename: str
    doc_type: str
    chunk_preview: str = Field(description="80 premiers caractères du chunk")


class QueryResponse(BaseModel):
    """Réponse complète du RAG Agent."""
    answer: str
    sources: List[SourceDoc]
    chunks_used: int
    confidence: float = Field(ge=0.0, le=1.0)
    agent: str = "rag_agent"
    model_used: str
    session_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Le gazoil B7 est recommandé pour votre Toyota Corolla 2019.",
                "sources": [{"filename": "guide_vehicules.pdf", "doc_type": "vehicule", "chunk_preview": "Toyota Corolla diesel..."}],
                "chunks_used": 3,
                "confidence": 0.87,
                "agent": "rag_agent",
                "model_used": "qwen3:8b"
            }
        }


class IngestResponse(BaseModel):
    """Résultat de l'indexation d'un document."""
    status: str
    filename: str
    chunks_indexed: int
    collection: str
    doc_type: str
    # NOUVEAU : détail des chunks texte vs visuels
    text_chunks: int = Field(default=0, description="Chunks issus du texte")
    visual_chunks: int = Field(default=0, description="Chunks issus de l'analyse vision (graphiques, schémas)")


class HealthResponse(BaseModel):
    """Statut du service."""
    status: str
    service: str = "rag_agent"
    model: str
    qdrant_connected: bool
    redis_connected: bool
    version: str = "1.0.0"
    # NOUVEAU : état du module vision
    vision_enabled: bool = False
    vision_model: Optional[str] = None


class ErrorResponse(BaseModel):
    """Format d'erreur standardisé."""
    error: str
    detail: Optional[str] = None
    trace_id: Optional[str] = None


class DocumentInfo(BaseModel):
    """Informations sur un document indexé."""
    filename: str
    doc_type: str
    collection: str
    chunks_count: int


class DeleteResponse(BaseModel):
    """Résultat de la suppression d'un document."""
    status: str
    filename: str
    collection: str
    chunks_deleted: int


class BatchIngestResponse(BaseModel):
    """Résultat de l'indexation de plusieurs documents."""
    status: str
    total_files: int
    succeeded: int
    failed: int
    results: List[IngestResponse]
    errors: List[dict] = []