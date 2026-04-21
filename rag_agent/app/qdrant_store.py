from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance, VectorParams,
    SparseVectorParams, SparseIndexParams,
    Filter, FieldCondition, MatchValue
)
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from langchain_core.embeddings import Embeddings
from fastembed import TextEmbedding, SparseTextEmbedding
from langchain.schema import Document
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio
import numpy as np
import httpx

from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)

# Taille des vecteurs pour bge-small-en-v1.5
EMBED_VECTOR_SIZE = 384
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"


# ─── Classe d'embeddings dense compatible LangChain ───────────────────────────
class FastEmbedLangChainWrapper(Embeddings):
    """
    Wrapper FastEmbed compatible avec l'interface LangChain Embeddings.
    """
    def __init__(self, model_name: str = EMBED_MODEL_NAME):
        self.model = TextEmbedding(model_name=model_name)
        log.info("FastEmbedLangChainWrapper initialisé", model=model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        results = list(self.model.embed(texts))
        return [r.tolist() if hasattr(r, 'tolist') else list(r) for r in results]

    def embed_query(self, text: str) -> List[float]:
        results = list(self.model.embed([text]))
        vec = results[0]
        return vec.tolist() if hasattr(vec, 'tolist') else list(vec)


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

        # ── Dense embeddings ──────────────────────────────────────────────────
        log.info("Chargement embeddings via FastEmbed", model=EMBED_MODEL_NAME)
        self.dense_embeddings = FastEmbedLangChainWrapper(model_name=EMBED_MODEL_NAME)

        try:
            test_vec = self.dense_embeddings.embed_query("test connexion")
            actual_size = len(test_vec)
            if actual_size != EMBED_VECTOR_SIZE:
                log.warning("Taille vecteur inattendue", expected=EMBED_VECTOR_SIZE, actual=actual_size)
            log.info("FastEmbed opérationnel", model=EMBED_MODEL_NAME, vector_size=actual_size)
        except Exception as e:
            log.error("FastEmbed inaccessible", error=str(e))
            raise RuntimeError(
                f"FastEmbed avec modèle {EMBED_MODEL_NAME} inaccessible.\n"
                f"Vérifiez que fastembed est installé correctement.\nErreur : {e}"
            )

        # ── Sparse embeddings : FastEmbedSparse pour LangChain (add_documents) ─
        # Utilisé UNIQUEMENT par QdrantVectorStore.add_documents().
        # LangChain gère lui-même la conversion interne — pas de parsing manuel.
        self.sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

        # ── Sparse embeddings : SparseTextEmbedding direct pour hybrid_search ──
        # On bypass FastEmbedSparse pour le search car son format de sortie
        # via embed_query() est instable selon les versions de langchain-qdrant :
        # au lieu de retourner (array_indices, array_values), il retourne parfois
        # [('indices', [...ints...]), ('values', [...floats...])] — un générateur
        # de paires clé/valeur qui casse le parsing.
        # SparseTextEmbedding (fastembed natif) retourne des objets avec
        # .indices (np.ndarray[uint32]) et .values (np.ndarray[float32]) fiables.
        log.info("Chargement SparseTextEmbedding direct", model="Qdrant/bm25")
        try:
            self._sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
            # Validation au démarrage
            _test = list(self._sparse_model.embed(["test bm25 validation"]))[0]
            log.info(
                "SparseTextEmbedding opérationnel",
                sample_indices=_test.indices[:3].tolist() if hasattr(_test.indices, 'tolist') else list(_test.indices)[:3],
                sample_values=_test.values[:3].tolist() if hasattr(_test.values, 'tolist') else list(_test.values)[:3],
            )
        except Exception as e:
            log.error(
                "SparseTextEmbedding inaccessible — hybrid search dégradé en dense-only",
                error=str(e),
            )
            self._sparse_model = None

        log.info(
            "QdrantStore initialisé",
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            dense_model=EMBED_MODEL_NAME,
            dense_size=EMBED_VECTOR_SIZE,
            sparse_model="Qdrant/bm25",
            sparse_direct_available=self._sparse_model is not None,
        )

    # ─── Sparse embedding direct (fiable) ─────────────────────────────────────

    def _embed_sparse(self, text: str) -> Optional[tuple]:
        """
        Génère le vecteur sparse BM25 via SparseTextEmbedding (fastembed natif).

        Retourne (indices: list[int], values: list[float]) ou None si indisponible.

        SparseTextEmbedding.embed() retourne des objets SparseEmbedding avec :
          - .indices : np.ndarray[uint32]  — indices des tokens BM25
          - .values  : np.ndarray[float32] — scores TF-IDF associés

        Ce format est stable et ne dépend pas de la version de langchain-qdrant.
        """
        if self._sparse_model is None:
            return None

        try:
            results = list(self._sparse_model.embed([text]))
            if not results:
                return None

            vec = results[0]
            indices = vec.indices.tolist() if hasattr(vec.indices, 'tolist') else [int(i) for i in vec.indices]
            values  = vec.values.tolist()  if hasattr(vec.values,  'tolist') else [float(v) for v in vec.values]

            # Garantie de type : Qdrant exige des int et des float
            indices = [int(i) for i in indices]
            values  = [float(v) for v in values]

            if not indices:
                log.warning("Vecteur sparse BM25 vide pour cette requête", text_preview=text[:50])
                return None

            return indices, values

        except Exception as e:
            log.warning("Erreur _embed_sparse", error=str(e), text_preview=text[:50])
            return None

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
            log.info("Collection créée", collection=collection_name, vector_size=EMBED_VECTOR_SIZE)
        else:
            info = self.client.get_collection(collection_name)
            existing_size = info.config.params.vectors.get("dense").size
            if existing_size != EMBED_VECTOR_SIZE:
                raise RuntimeError(
                    f"Collection '{collection_name}' a des vecteurs de taille {existing_size} "
                    f"mais {EMBED_MODEL_NAME} produit {EMBED_VECTOR_SIZE}. "
                    f"Solution : docker-compose down -v && docker-compose up -d"
                )
            log.info("Collection existante OK", collection=collection_name)

    def setup_collection(self):
        """Crée la collection par défaut si elle n'existe pas."""
        self.ensure_collection(settings.QDRANT_COLLECTION)

    # ── VectorStore (utilisé uniquement pour add_documents) ──────────────────

    def get_vectorstore(self, collection_name: str) -> QdrantVectorStore:
        """
        Crée un QdrantVectorStore avec FastEmbedSparse pour l'indexation.
        FastEmbedSparse est utilisé ici uniquement via LangChain qui gère
        lui-même la conversion interne — pas de parsing manuel nécessaire.
        """
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
        Hybrid search (dense COSINE + sparse BM25 + RRF fusion).

        Utilise SparseTextEmbedding directement pour le vecteur sparse,
        ce qui garantit des indices entiers et des valeurs float fiables,
        sans dépendre du format de sortie instable de FastEmbedSparse.embed_query().

        Dégrade gracieusement vers dense-only si le sparse échoue.
        """
        filter_condition = None
        if doc_type_filter:
            filter_condition = Filter(
                must=[FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value=doc_type_filter)
                )]
            )

        # 1. Dense embedding (executor pour ne pas bloquer la boucle asyncio)
        def _get_dense():
            return self.dense_embeddings.embed_query(query)

        dense_vector = await asyncio.get_event_loop().run_in_executor(None, _get_dense)

        # 2. Sparse BM25 via SparseTextEmbedding (executor aussi — CPU-bound)
        def _get_sparse():
            return self._embed_sparse(query)

        sparse_result = await asyncio.get_event_loop().run_in_executor(None, _get_sparse)

        # 3. Construction des prefetch legs
        prefetch = [
            models.Prefetch(
                query=dense_vector,
                using="dense",
                limit=top_k,
                filter=filter_condition,
            ),
        ]

        if sparse_result is not None:
            indices, values = sparse_result
            prefetch.append(
                models.Prefetch(
                    query=models.SparseVector(indices=indices, values=values),
                    using="sparse",
                    limit=top_k,
                    filter=filter_condition,
                )
            )
            log.info("Sparse leg BM25 ajouté", nb_tokens=len(indices))
        else:
            log.warning("Sparse BM25 indisponible, recherche dense uniquement")

        # 4. RRF fusion
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
            nb_prefetch_legs=len(prefetch),
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

    def collection_exists(self, collection_name: str) -> bool:
        try:
            return self.client.collection_exists(collection_name)
        except Exception as e:
            log.error("Erreur vérification collection", collection=collection_name, error=str(e))
            return False

    def delete_collection(self, collection_name: str) -> bool:
        try:
            if not self.client.collection_exists(collection_name):
                log.warning("Collection non trouvée pour suppression", collection=collection_name)
                return False
            self.client.delete_collection(collection_name)
            log.info("Collection supprimée", collection=collection_name)
            return True
        except Exception as e:
            log.error("Erreur suppression collection", collection=collection_name, error=str(e))
            raise


# Singleton
qdrant_store = QdrantStore()