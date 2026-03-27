from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models
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
import asyncio
import numpy as np
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

        log.info("Chargement embeddings bge-m3 via Ollama", model=EMBED_MODEL_NAME)
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

        # Détecter le format retourné par FastEmbedSparse une fois pour toutes
        self._sparse_format = self._detect_sparse_format()
        log.info("QdrantStore initialisé",
                 host=settings.QDRANT_HOST,
                 port=settings.QDRANT_PORT,
                 sparse_format=self._sparse_format)

    def _detect_sparse_format(self) -> str:
        """
        Détecte le format retourné par FastEmbedSparse.embed_query().
        Retourne : 'attrs' | 'tuple' | 'dict'
        """
        try:
            results = list(self.sparse_embeddings.embed_query("test"))
            if not results:
                return "attrs"
            vec = results[0]
            if hasattr(vec, "indices") and hasattr(vec, "values"):
                return "attrs"
            elif isinstance(vec, tuple):
                return "tuple"
            elif isinstance(vec, dict):
                return "dict"
            else:
                log.warning("Format sparse inconnu, fallback attrs", type=str(type(vec)))
                return "attrs"
        except Exception as e:
            log.warning("Détection format sparse échouée", error=str(e))
            return "attrs"

    def _parse_sparse_vector(self, vec) -> tuple[list, list]:
        """
        Convertit un vecteur sparse en (indices, values) quel que soit
        le format retourné par la version installée de FastEmbedSparse.
        """
        if self._sparse_format == "tuple":
            # (array_indices, array_values)
            raw_indices, raw_values = vec[0], vec[1]
            indices = raw_indices.tolist() if hasattr(raw_indices, "tolist") else list(raw_indices)
            values  = raw_values.tolist()  if hasattr(raw_values,  "tolist") else list(raw_values)
        elif self._sparse_format == "dict":
            indices = list(vec.get("indices", []))
            values  = list(vec.get("values",  []))
        else:
            # format 'attrs' : objet avec .indices et .values (numpy arrays)
            indices = vec.indices.tolist() if hasattr(vec.indices, "tolist") else list(vec.indices)
            values  = vec.values.tolist()  if hasattr(vec.values,  "tolist") else list(vec.values)
        return indices, values

    # ── Collections ───────────────────────────────────────────────────────────

    def ensure_collection(self, collection_name: str):
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=EMBED_VECTOR_SIZE,
                        distance=Distance.COSINE,
                        on_disk=False,
                    )
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(
                        index=SparseIndexParams(on_disk=False),
                        modifier=models.Modifier.IDF,
                    )
                },
                hnsw_config=models.HnswConfigDiff(
                    m=16, ef_construct=100, full_scan_threshold=10_000
                ),
            )
            log.info("Collection créée", collection=collection_name)
        else:
            info = self.client.get_collection(collection_name)
            existing_size = info.config.params.vectors.get("dense").size
            if existing_size != EMBED_VECTOR_SIZE:
                raise RuntimeError(
                    f"Collection '{collection_name}' a des vecteurs de taille {existing_size} "
                    f"mais bge-m3 produit {EMBED_VECTOR_SIZE}. "
                    f"Solution : docker-compose down -v && docker-compose up -d"
                )
            log.info("Collection existante OK", collection=collection_name)

    def setup_collection(self):
        self.ensure_collection(settings.QDRANT_COLLECTION)

    # ── VectorStore (utilisé uniquement pour add_documents) ──────────────────

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

    def add_documents(self, collection_name: str, documents: List[Document]) -> int:
        vs = self.get_vectorstore(collection_name)
        ids = vs.add_documents(documents)
        log.info("Documents indexés", collection=collection_name, count=len(ids))
        return len(ids)

    # ── Hybrid search ─────────────────────────────────────────────────────────

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
        """
        Hybrid search (dense + sparse RRF) avec filtre appliqué sur les deux legs.
        Utilise l'API query_points de Qdrant directement pour éviter le bug
        de propagation du filtre dans langchain-qdrant en mode HYBRID.
        """
        filter_condition = None
        if doc_type_filter:
            filter_condition = Filter(
                must=[FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value=doc_type_filter)
                )]
            )

        # 1. Dense embedding (synchrone → exécuteur pour rester async)
        dense_vector = await asyncio.get_event_loop().run_in_executor(
            None, self.dense_embeddings.embed_query, query
        )

        # 2. Sparse embedding + parsing robuste du format
        sparse_results = list(self.sparse_embeddings.embed_query(query))
        sparse_vec = sparse_results[0] if sparse_results else None

        # 3. Construction des prefetch legs
        prefetch = [
            models.Prefetch(
                query=dense_vector,
                using="dense",
                limit=top_k,
                filter=filter_condition,
            ),
        ]

        if sparse_vec is not None:
            try:
                indices, values = self._parse_sparse_vector(sparse_vec)
                prefetch.append(
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=indices,
                            values=values,
                        ),
                        using="sparse",
                        limit=top_k,
                        filter=filter_condition,
                    )
                )
            except Exception as e:
                log.warning("Sparse vector parsing échoué, dense only", error=str(e))

        # 4. RRF fusion via query API Qdrant
        results = await self.async_client.query_points(
            collection_name=collection_name,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )

        # 5. Conversion en LangChain Documents
        docs = []
        for point in results.points:
            payload = point.payload or {}
            metadata = payload.get("metadata", {})
            page_content = payload.get("page_content", "")
            if page_content:
                docs.append(Document(page_content=page_content, metadata=metadata))

        log.info(
            "Hybrid search effectué",
            collection=collection_name,
            query_len=len(query),
            results=len(docs),
            filter=doc_type_filter,
        )
        return docs

    # ── Listing documents ─────────────────────────────────────────────────────

    def list_documents(self, collection_name: str) -> list[dict]:
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

    # ── Suppression document ──────────────────────────────────────────────────

    def delete_document(self, collection_name: str, filename: str) -> int:
        try:
            existing, _ = self.client.scroll(
                collection_name=collection_name,
                query_filter=Filter(
                    must=[FieldCondition(
                        key="metadata.filename",
                        match=MatchValue(value=filename)
                    )]
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
                    must=[FieldCondition(
                        key="metadata.filename",
                        match=MatchValue(value=filename)
                    )]
                ),
            )
            log.info("Document supprimé", filename=filename,
                    collection=collection_name, chunks_deleted=count)
            return count
        except Exception as e:
            log.error("Erreur suppression", filename=filename, error=str(e))
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