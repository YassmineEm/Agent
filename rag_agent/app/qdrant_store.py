from qdrant_client import QdrantClient, AsyncQdrantClient, models
from qdrant_client.http.models import (
    Distance, VectorParams,
    SparseVectorParams, SparseIndexParams,
    Filter, FieldCondition, MatchValue
)
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from langchain_ollama import OllamaEmbeddings
from langchain.schema import Document
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)

EMBED_VECTOR_SIZE = 1024
EMBED_MODEL_NAME  = "bge-m3"


class QdrantStore:

    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=10,
        )
        self.async_client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=10,
        )

        log.info(
            "Chargement embeddings bge-m3 via Ollama",
            model=EMBED_MODEL_NAME,
            ollama_url=settings.OLLAMA_BASE_URL,
        )
        self.dense_embeddings = OllamaEmbeddings(
            model=EMBED_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
        )

        try:
            test_vec = self.dense_embeddings.embed_query("test connexion bge-m3")
            actual_size = len(test_vec)
            if actual_size != EMBED_VECTOR_SIZE:
                log.warning("Taille vecteur inattendue", expected=EMBED_VECTOR_SIZE, actual=actual_size)
            log.info("bge-m3 opérationnel", vector_size=actual_size)
        except Exception as e:
            log.error("bge-m3 inaccessible", error=str(e))
            raise RuntimeError(
                f"bge-m3 inaccessible sur {settings.OLLAMA_BASE_URL}.\n"
                f"Solution : ollama pull bge-m3\nErreur : {e}"
            )

        self.sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
        log.info("QdrantStore initialisé", host=settings.QDRANT_HOST, port=settings.QDRANT_PORT,
                 embed_model=EMBED_MODEL_NAME, vector_size=EMBED_VECTOR_SIZE)

    # ── Setup collections ─────────────────────────────────────────────────────

    def ensure_collection(self, collection_name: str):
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(size=EMBED_VECTOR_SIZE, distance=Distance.COSINE, on_disk=False)
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(
                        index=SparseIndexParams(on_disk=False),
                        modifier=models.Modifier.IDF,
                    )
                },
                hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100, full_scan_threshold=10_000),
            )
            log.info("Collection créée", collection=collection_name, vector_size=EMBED_VECTOR_SIZE)
        else:
            info = self.client.get_collection(collection_name)
            existing_size = info.config.params.vectors.get("dense").size
            if existing_size != EMBED_VECTOR_SIZE:
                raise RuntimeError(
                    f"Collection '{collection_name}' contient des vecteurs de taille "
                    f"{existing_size} mais bge-m3 produit {EMBED_VECTOR_SIZE}.\n"
                    f"Solution : docker-compose down -v && docker-compose up -d"
                )
            log.info("Collection existante OK", collection=collection_name)

    def setup_collection(self):
        self.ensure_collection(settings.QDRANT_COLLECTION)

    # ── VectorStore helper ────────────────────────────────────────────────────

    def get_vectorstore(self, collection_name: str) -> QdrantVectorStore:
        return QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embedding=self.dense_embeddings,
            sparse_embedding=self.sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",
        )

    # ── Indexation ────────────────────────────────────────────────────────────

    def add_documents(self, collection_name: str, documents: List[Document]) -> int:
        vs = self.get_vectorstore(collection_name)
        ids = vs.add_documents(documents)
        log.info("Documents indexés", collection=collection_name, count=len(ids))
        return len(ids)

    # ── Recherche ─────────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def hybrid_search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 20,
        doc_type_filter: Optional[str] = None,
    ) -> List[Document]:
        filter_condition = None
        if doc_type_filter:
            filter_condition = Filter(
                must=[FieldCondition(key="metadata.doc_type", match=MatchValue(value=doc_type_filter))]
            )

        vs = self.get_vectorstore(collection_name)
        docs = await vs.asimilarity_search(query=query, k=top_k, filter=filter_condition)
        log.info("Hybrid search effectué", collection=collection_name,
                 query_len=len(query), results=len(docs), filter=doc_type_filter)
        return docs

    # ── Lister les documents ──────────────────────────────────────────────────

    def list_documents(self, collection_name: str) -> list[dict]:
        """
        Liste tous les documents uniques indexés dans une collection.
        Regroupe les chunks par filename — 1 entrée par document.
        """
        try:
            all_points, _ = self.client.scroll(
                collection_name=collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )

            docs = {}
            for point in all_points:
                meta = point.payload.get("metadata", {})
                filename = meta.get("filename", "Inconnu")
                doc_type = meta.get("doc_type", "general")

                if filename not in docs:
                    docs[filename] = {
                        "filename": filename,
                        "doc_type": doc_type,
                        "collection": collection_name,
                        "chunks_count": 0,
                    }
                docs[filename]["chunks_count"] += 1

            result = list(docs.values())
            log.info("Documents listés", collection=collection_name, count=len(result))
            return result

        except Exception as e:
            log.error("Erreur listing documents", collection=collection_name, error=str(e))
            return []

    # ── Supprimer un document ─────────────────────────────────────────────────

    def delete_document(self, collection_name: str, filename: str) -> int:
        """
        Supprime tous les chunks d'un document par son filename.
        Retourne le nombre de chunks supprimés.
        CORRECTION : query_filter au lieu de scroll_filter.
        """
        try:
            # Compter les chunks — paramètre correct : query_filter
            existing, _ = self.client.scroll(
                collection_name=collection_name,
                query_filter=Filter(
                    must=[FieldCondition(key="metadata.filename", match=MatchValue(value=filename))]
                ),
                limit=10000,
                with_payload=False,
                with_vectors=False,
            )
            count = len(existing)

            if count == 0:
                log.warning("Document non trouvé", filename=filename, collection=collection_name)
                return 0

            self.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="metadata.filename", match=MatchValue(value=filename))]
                ),
            )

            log.info("Document supprimé", filename=filename,
                     collection=collection_name, chunks_deleted=count)
            return count

        except Exception as e:
            log.error("Erreur suppression document", filename=filename, error=str(e))
            raise

    # ── Health check ──────────────────────────────────────────────────────────

    def is_healthy(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            log.error("Qdrant health check failed", error=str(e))
            return False


# Singleton
qdrant_store = QdrantStore()