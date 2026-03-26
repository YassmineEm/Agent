"""
tests/test_rag_agent.py — Tests complets du microservice RAG Agent

Comment lancer :
  cd rag_agent
  pytest tests/ -v                    # tous les tests
  pytest tests/ -v -k "health"        # juste les tests health
  pytest tests/ -v -k "query"         # juste les tests query
  pytest tests/ -v -k "cache"         # juste les tests cache
  pytest tests/ -v -k "vision"        # juste les tests vision (NOUVEAU)
  pytest tests/ -v --tb=short         # erreurs courtes
  pytest tests/ -v -s                 # avec print() visible
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app
from app.models import QueryResponse, SourceDoc
from app.config import settings


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_rag_response_fr():
    """Réponse RAG simulée en français."""
    return QueryResponse(
        answer="Le gazoil B7 (norme EN590) est recommandé pour votre Toyota Corolla 2019 diesel.",
        sources=[
            SourceDoc(
                filename="guide_vehicules.pdf",
                doc_type="vehicule",
                chunk_preview="Toyota Corolla 2019 diesel nécessite Gazoil B7...",
            )
        ],
        chunks_used=3,
        confidence=0.87,
        agent="rag_agent",
        model_used="qwen3:8b",
        session_id=None,
    )


@pytest.fixture
def mock_rag_response_ar():
    """Réponse RAG simulée en arabe."""
    return QueryResponse(
        answer="الوقود الموصى به لسيارة داسيا لوغان ديزل هو غازوال B7 (المعيار EN590).",
        sources=[
            SourceDoc(
                filename="guide_vehicules_ar.txt",
                doc_type="vehicule",
                chunk_preview="داسيا لوغان ديزل — الوقود: غازوال B7...",
            )
        ],
        chunks_used=2,
        confidence=0.82,
        agent="rag_agent",
        model_used="qwen3:8b",
        session_id=None,
    )


@pytest.fixture
def mock_rag_response_en():
    """Réponse RAG simulée en anglais."""
    return QueryResponse(
        answer="The recommended fuel for a Dacia Logan diesel is B7 gasoline (EN590 standard).",
        sources=[
            SourceDoc(
                filename="guide_vehicules_ar.txt",
                doc_type="vehicule",
                chunk_preview="Dacia Logan diesel — fuel: B7 gazole...",
            )
        ],
        chunks_used=2,
        confidence=0.79,
        agent="rag_agent",
        model_used="qwen3:8b",
        session_id=None,
    )


@pytest.fixture
def admin_headers():
    """Headers pour les routes admin."""
    return {"X-Admin-Key": settings.ADMIN_API_KEY}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthCheck:

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Le health check doit toujours retourner 200."""
        with patch("app.main.qdrant_store") as mock_qdrant, \
             patch("app.main.cache_service") as mock_cache:
            mock_qdrant.is_healthy.return_value = True
            mock_cache.is_healthy.return_value = True

            response = await client.get("/health")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_contains_required_fields(self, client):
        """La réponse health doit contenir tous les champs requis."""
        with patch("app.main.qdrant_store") as mock_qdrant, \
             patch("app.main.cache_service") as mock_cache:
            mock_qdrant.is_healthy.return_value = True
            mock_cache.is_healthy.return_value = False

            response = await client.get("/health")
            data = response.json()

        assert "status" in data
        assert "qdrant_connected" in data
        assert "redis_connected" in data
        assert "model" in data
        assert data["service"] == "rag_agent"

    @pytest.mark.asyncio
    async def test_health_degraded_when_qdrant_down(self, client):
        """Status dégradé quand Qdrant est down."""
        with patch("app.main.qdrant_store") as mock_qdrant, \
             patch("app.main.cache_service") as mock_cache:
            mock_qdrant.is_healthy.return_value = False
            mock_cache.is_healthy.return_value = True

            response = await client.get("/health")
            data = response.json()

        assert data["status"] == "degraded"
        assert data["qdrant_connected"] is False

    @pytest.mark.asyncio
    async def test_health_healthy_when_all_up(self, client):
        """Status healthy quand Qdrant + Redis sont up."""
        with patch("app.main.qdrant_store") as mock_qdrant, \
             patch("app.main.cache_service") as mock_cache:
            mock_qdrant.is_healthy.return_value = True
            mock_cache.is_healthy.return_value = True

            response = await client.get("/health")
            data = response.json()

        assert data["status"] == "healthy"
        assert data["qdrant_connected"] is True
        assert data["redis_connected"] is True


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : QUERY — FRANÇAIS
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryFrancais:

    @pytest.mark.asyncio
    async def test_query_fr_returns_200(self, client, mock_rag_response_fr):
        """Question en français → 200 avec réponse en français."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)

            response = await client.post("/query", json={
                "question": "Quel carburant pour une Toyota Corolla diesel 2019 ?"
            })

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["chunks_used"] > 0
        assert data["confidence"] > 0.0
        assert data["agent"] == "rag_agent"

    @pytest.mark.asyncio
    async def test_query_fr_answer_is_string(self, client, mock_rag_response_fr):
        """La réponse doit être une chaîne non vide."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)

            response = await client.post("/query", json={
                "question": "Quel carburant pour une Dacia Logan diesel ?"
            })

        data = response.json()
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    @pytest.mark.asyncio
    async def test_query_fr_sources_present(self, client, mock_rag_response_fr):
        """Les sources doivent être présentes avec filename et doc_type."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)

            response = await client.post("/query", json={
                "question": "Normes carburant diesel au Maroc ?"
            })

        data = response.json()
        assert isinstance(data["sources"], list)
        if data["sources"]:
            assert "filename" in data["sources"][0]
            assert "doc_type" in data["sources"][0]
            assert "chunk_preview" in data["sources"][0]


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : QUERY — ARABE
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryArabe:

    @pytest.mark.asyncio
    async def test_query_ar_returns_200(self, client, mock_rag_response_ar):
        """Question en arabe → 200 avec réponse en arabe."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_ar)

            response = await client.post("/query", json={
                "question": "ما هو الوقود المناسب لسيارة داسيا لوغان ديزل؟"
            })

        assert response.status_code == 200
        data = response.json()
        assert data["chunks_used"] > 0
        assert data["confidence"] > 0.0

    @pytest.mark.asyncio
    async def test_query_ar_answer_in_arabic(self, client, mock_rag_response_ar):
        """La réponse à une question arabe doit contenir du texte arabe."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_ar)

            response = await client.post("/query", json={
                "question": "ما هو الوقود المناسب لسيارة داسيا لوغان ديزل؟"
            })

        data = response.json()
        answer = data["answer"]
        has_arabic = any('\u0600' <= c <= '\u06FF' for c in answer)
        assert has_arabic, f"Réponse attendue en arabe, obtenu : {answer}"

    @pytest.mark.asyncio
    async def test_query_ar_sources_from_arabic_doc(self, client, mock_rag_response_ar):
        """Les sources doivent provenir du document arabe."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_ar)

            response = await client.post("/query", json={
                "question": "ما هو وقود تويوتا كورولا؟"
            })

        data = response.json()
        assert len(data["sources"]) > 0
        assert data["sources"][0]["doc_type"] == "vehicule"


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : QUERY — ANGLAIS
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryAnglais:

    @pytest.mark.asyncio
    async def test_query_en_returns_200(self, client, mock_rag_response_en):
        """Question en anglais → 200 avec réponse en anglais."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_en)

            response = await client.post("/query", json={
                "question": "What is the appropriate fuel for a Dacia Logan diesel?"
            })

        assert response.status_code == 200
        data = response.json()
        assert data["chunks_used"] > 0
        assert data["confidence"] > 0.0

    @pytest.mark.asyncio
    async def test_query_en_answer_in_english(self, client, mock_rag_response_en):
        """La réponse à une question anglaise doit être en anglais."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_en)

            response = await client.post("/query", json={
                "question": "What fuel for a Toyota Corolla diesel 2019?"
            })

        data = response.json()
        answer = data["answer"]
        has_arabic = any('\u0600' <= c <= '\u06FF' for c in answer)
        assert not has_arabic, f"Réponse attendue en anglais, pas en arabe : {answer}"

    @pytest.mark.asyncio
    async def test_query_en_context_from_arabic_doc(self, client, mock_rag_response_en):
        """Contexte arabe → réponse anglaise grâce à la traduction du prompt."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_en)

            response = await client.post("/query", json={
                "question": "What fuel for a Volkswagen Golf diesel?"
            })

        data = response.json()
        assert data["chunks_used"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : QUERY — CACHE HIT
# ══════════════════════════════════════════════════════════════════════════════

class TestCacheHit:

    @pytest.mark.asyncio
    async def test_same_question_twice_hits_cache(self, client, mock_rag_response_fr):
        """La même question deux fois → 2ème appel depuis le cache."""
        call_count = 0

        async def mock_query(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_rag_response_fr

        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = mock_query

            r1 = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla diesel ?"
            })
            r2 = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla diesel ?"
            })

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["answer"] == r2.json()["answer"]

    @pytest.mark.asyncio
    async def test_different_questions_different_responses(self, client,
                                                        mock_rag_response_fr,
                                                        mock_rag_response_en):
        """Deux questions différentes → réponses différentes."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(side_effect=[
                mock_rag_response_fr,
                mock_rag_response_en,
            ])

            r1 = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla diesel ?"
            })
            r2 = await client.post("/query", json={
                "question": "What fuel for a Renault Clio petrol?"
            })

        assert r1.json()["answer"] != r2.json()["answer"]

    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_confidence(self, client, mock_rag_response_fr):
        """Le cache doit retourner exactement la même confidence."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)

            r1 = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla diesel ?"
            })
            r2 = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla diesel ?"
            })

        assert r1.json()["confidence"] == r2.json()["confidence"]


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : QUERY — VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryValidation:

    @pytest.mark.asyncio
    async def test_query_empty_question_returns_422(self, client):
        """Question vide → 422."""
        response = await client.post("/query", json={"question": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_missing_question_returns_422(self, client):
        """Absence de question → 422."""
        response = await client.post("/query", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_too_short_returns_422(self, client):
        """Question < 3 chars → 422."""
        response = await client.post("/query", json={"question": "ab"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_with_session_id(self, client, mock_rag_response_fr):
        """session_id accepté → 200."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)

            response = await client.post("/query", json={
                "question": "Quel carburant pour ma voiture ?",
                "session_id": "user_test_123"
            })

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_query_with_doc_type_filter(self, client, mock_rag_response_fr):
        """doc_type_filter accepté → 200."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)

            response = await client.post("/query", json={
                "question": "Normes carburant Maroc ?",
                "doc_type_filter": "norme"
            })

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_trace_id_in_response_headers(self, client, mock_rag_response_fr):
        """X-Trace-ID doit être dans les headers de réponse."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)

            response = await client.post("/query", json={
                "question": "Question de test pour trace id ?"
            })

        assert "x-trace-id" in response.headers

    @pytest.mark.asyncio
    async def test_response_time_in_headers(self, client, mock_rag_response_fr):
        """X-Response-Time doit être dans les headers."""
        with patch("app.main.rag_agent") as mock_agent:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)

            response = await client.post("/query", json={
                "question": "Test response time header ?"
            })

        assert "x-response-time" in response.headers


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : SÉCURITÉ — 403
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurite:

    @pytest.mark.asyncio
    async def test_upload_without_admin_key_returns_403(self, client):
        """Upload sans clé admin → 403."""
        response = await client.post(
            "/admin/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"doc_type": "fiche_technique"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_upload_with_wrong_admin_key_returns_403(self, client):
        """Upload avec mauvaise clé → 403."""
        response = await client.post(
            "/admin/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"doc_type": "fiche_technique"},
            headers={"X-Admin-Key": "mauvaise_cle_123"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_documents_without_key_returns_403(self, client):
        """GET /admin/documents sans clé → 403."""
        response = await client.get("/admin/documents")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_document_without_key_returns_403(self, client):
        """DELETE /admin/documents/{filename} sans clé → 403."""
        response = await client.delete("/admin/documents/test.pdf")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_stats_without_key_returns_403(self, client):
        """GET /admin/stats sans clé → 403."""
        response = await client.get("/admin/stats")
        assert response.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : ENDPOINT /admin/upload
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminUpload:

    @pytest.mark.asyncio
    async def test_upload_valid_pdf_returns_200(self, client, admin_headers):
        """Upload PDF valide → 200."""
        mock_result = {
            "status": "success",
            "filename": "test.pdf",
            "doc_type": "fiche_technique",
            "chunks_indexed": 5,
            "collection": "akwa_knowledge",
        }
        with patch("app.main.ingestion") as mock_ing:
            mock_ing.ingest_file = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/admin/upload",
                files={"file": ("test.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
                data={"doc_type": "fiche_technique"},
                headers=admin_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["chunks_indexed"] == 5
        assert data["collection"] == "akwa_knowledge"

    @pytest.mark.asyncio
    async def test_upload_txt_returns_200(self, client, admin_headers):
        """Upload TXT (guide_vehicules_ar.txt) → 200."""
        mock_result = {
            "status": "success",
            "filename": "guide_vehicules_ar.txt",
            "doc_type": "vehicule",
            "chunks_indexed": 2,
            "collection": "akwa_knowledge",
        }
        with patch("app.main.ingestion") as mock_ing:
            mock_ing.ingest_file = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/admin/upload",
                files={"file": ("guide_vehicules_ar.txt", b"arabic content", "text/plain")},
                data={"doc_type": "vehicule"},
                headers=admin_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["chunks_indexed"] == 2

    @pytest.mark.asyncio
    async def test_upload_unsupported_format_returns_400(self, client, admin_headers):
        """Format non supporté (.png) → 400."""
        response = await client.post(
            "/admin/upload",
            files={"file": ("photo.png", b"fake image data", "image/png")},
            data={"doc_type": "general"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "non supporté" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_without_doc_type_uses_default(self, client, admin_headers):
        """Upload sans doc_type → utilise 'general' par défaut."""
        mock_result = {
            "status": "success",
            "filename": "doc.pdf",
            "doc_type": "general",
            "chunks_indexed": 3,
            "collection": "akwa_knowledge",
        }
        with patch("app.main.ingestion") as mock_ing:
            mock_ing.ingest_file = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/admin/upload",
                files={"file": ("doc.pdf", b"%PDF-1.4 content", "application/pdf")},
                headers=admin_headers,
            )

        assert response.status_code == 200
        assert response.json()["doc_type"] == "general"

    @pytest.mark.asyncio
    async def test_upload_collection_always_akwa_knowledge(self, client, admin_headers):
        """L'upload doit toujours aller dans akwa_knowledge."""
        mock_result = {
            "status": "success",
            "filename": "faq.pdf",
            "doc_type": "faq",
            "chunks_indexed": 4,
            "collection": "akwa_knowledge",
        }
        with patch("app.main.ingestion") as mock_ing:
            mock_ing.ingest_file = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/admin/upload",
                files={"file": ("faq.pdf", b"%PDF-1.4 content", "application/pdf")},
                data={"doc_type": "faq"},
                headers=admin_headers,
            )

        assert response.json()["collection"] == "akwa_knowledge"


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════════

class TestModels:

    def test_query_request_valid(self):
        """QueryRequest valide → créé sans erreur."""
        from app.models import QueryRequest
        req = QueryRequest(question="Quel carburant pour ma voiture ?")
        assert req.question == "Quel carburant pour ma voiture ?"

    def test_query_request_default_language_auto(self):
        """Le language par défaut doit être 'auto'."""
        from app.models import QueryRequest
        req = QueryRequest(question="Question de test valide ?")
        assert req.language == "auto"

    def test_query_request_strips_whitespace(self):
        """La question doit être nettoyée des espaces."""
        from app.models import QueryRequest
        req = QueryRequest(question="  ma question  ")
        assert req.question == "ma question"

    def test_query_request_too_short_raises(self):
        """Question < 3 chars → ValidationError."""
        from app.models import QueryRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QueryRequest(question="ab")

    def test_query_request_no_collection_field(self):
        """QueryRequest ne doit plus avoir de champ collection."""
        from app.models import QueryRequest
        req = QueryRequest(question="Question valide de test ?")
        assert not hasattr(req, "collection")

    def test_query_response_confidence_bounds(self):
        """Confidence > 1 → ValidationError."""
        from app.models import QueryResponse
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QueryResponse(
                answer="test",
                sources=[],
                chunks_used=0,
                confidence=1.5,
                agent="rag_agent",
                model_used="qwen3:8b",
            )

    def test_query_response_confidence_zero_valid(self):
        """Confidence = 0.0 → valide."""
        from app.models import QueryResponse
        resp = QueryResponse(
            answer="Je n'ai pas cette information.",
            sources=[],
            chunks_used=0,
            confidence=0.0,
            agent="rag_agent",
            model_used="qwen3:8b",
        )
        assert resp.confidence == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : CACHE SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class TestCacheService:

    @pytest.mark.asyncio
    async def test_cache_returns_none_when_redis_down(self):
        """Sans Redis, le cache retourne None gracieusement."""
        from app.cache import CacheService
        cs = CacheService()
        cs._redis = None

        result = await cs.get_cached_response("test question", "akwa_knowledge", None)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_does_nothing_when_redis_down(self):
        """Sans Redis, le set ne plante pas."""
        from app.cache import CacheService
        cs = CacheService()
        cs._redis = None

        await cs.set_cached_response("test", "akwa_knowledge", None, {"answer": "ok"})

    @pytest.mark.asyncio
    async def test_cache_key_deterministic(self):
        """La même question génère toujours la même clé."""
        from app.cache import CacheService
        cs = CacheService()

        key1 = cs._make_key("Quel carburant ?", "akwa_knowledge", None)
        key2 = cs._make_key("Quel carburant ?", "akwa_knowledge", None)
        key3 = cs._make_key("Autre question ?", "akwa_knowledge", None)

        assert key1 == key2
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_cache_key_differs_with_filter(self):
        """Même question avec filtre différent → clés différentes."""
        from app.cache import CacheService
        cs = CacheService()

        key1 = cs._make_key("Quel carburant ?", "akwa_knowledge", None)
        key2 = cs._make_key("Quel carburant ?", "akwa_knowledge", "vehicule")

        assert key1 != key2


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : AGENT RERANKING
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentReranking:

    def test_rerank_returns_top_n(self):
        """Le reranking doit retourner exactement top_n documents."""
        from app.agent import RAGAgent
        from langchain.schema import Document

        with patch("app.agent.ChatOllama"), \
            patch("app.agent.CrossEncoder") as mock_ce_class:
            mock_ce = MagicMock()
            mock_ce.predict.return_value = [0.9, 0.3, 0.7, 0.1, 0.5]
            mock_ce_class.return_value = mock_ce

            agent = RAGAgent()
            docs = [Document(page_content=f"doc {i}") for i in range(5)]
            top_docs, scores = agent._rerank("test query", docs, top_n=3)

        assert len(top_docs) == 3
        assert len(scores) == 3

    def test_rerank_orders_by_score_descending(self):
        """Les docs doivent être triés par score décroissant."""
        from app.agent import RAGAgent
        from langchain.schema import Document

        with patch("app.agent.ChatOllama"), \
            patch("app.agent.CrossEncoder") as mock_ce_class:
            mock_ce = MagicMock()
            mock_ce.predict.return_value = [0.1, 0.9, 0.5]
            mock_ce_class.return_value = mock_ce

            agent = RAGAgent()
            docs = [Document(page_content=f"doc {i}") for i in range(3)]
            top_docs, scores = agent._rerank("query", docs, top_n=2)

        assert len(scores) == 2
        assert scores[0] >= scores[1]

    def test_rerank_fewer_docs_than_top_n(self):
        """Si moins de docs que top_n → retourner tous les docs."""
        from app.agent import RAGAgent
        from langchain.schema import Document

        with patch("app.agent.ChatOllama"), \
             patch("app.agent.CrossEncoder") as mock_ce_class:
            mock_ce = MagicMock()
            mock_ce.predict.return_value = [0.8]
            mock_ce_class.return_value = mock_ce

            agent = RAGAgent()
            docs = [Document(page_content="seul doc")]
            top_docs, scores = agent._rerank("query", docs, top_n=5)

        assert len(top_docs) == 1

    def test_rerank_empty_docs_returns_empty(self):
        """Liste vide → listes vides."""
        from app.agent import RAGAgent

        with patch("app.agent.ChatOllama"), \
             patch("app.agent.CrossEncoder") as mock_ce_class:
            mock_ce_class.return_value = MagicMock()
            agent = RAGAgent()
            top_docs, scores = agent._rerank("query", [], top_n=5)

        assert top_docs == []
        assert scores == []

    def test_confidence_score_bounds(self):
        """Le score de confiance doit être entre 0 et 1."""
        from app.agent import RAGAgent
        from langchain.schema import Document

        with patch("app.agent.ChatOllama"), \
             patch("app.agent.CrossEncoder") as mock_ce_class:
            mock_ce_class.return_value = MagicMock()
            agent = RAGAgent()

            docs = [Document(page_content=f"doc {i}") for i in range(4)]
            score_full = agent._compute_confidence(docs, [2.5, 1.2, 0.8, 0.3])
            score_empty = agent._compute_confidence([], [])

        assert 0.0 <= score_full <= 1.0
        assert score_empty == 0.0

    def test_think_tags_removed_from_llm_response(self):
        """Les balises <think> de qwen3 doivent être supprimées de la réponse."""
        import re
        raw = "<think>Je réfléchis...</think>\n\nLe carburant recommandé est B7."
        cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        assert "<think>" not in cleaned
        assert "Le carburant recommandé est B7." in cleaned


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : FORMATS DE FICHIERS
# ══════════════════════════════════════════════════════════════════════════════

class TestFileFormats:

    def test_detect_pdf(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("fiche.pdf") == FileType.PDF

    def test_detect_docx(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("guide.docx") == FileType.DOCX

    def test_detect_doc(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("ancien.doc") == FileType.DOCX

    def test_detect_csv(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("prix_carburant.csv") == FileType.CSV

    def test_detect_xlsx(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("stations.xlsx") == FileType.EXCEL

    def test_detect_xls(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("old_data.xls") == FileType.EXCEL

    def test_detect_txt(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("notes.txt") == FileType.TXT

    def test_detect_json(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("stations.json") == FileType.JSON

    def test_detect_markdown(self):
        from app.ingestion import detect_file_type, FileType
        assert detect_file_type("faq.md") == FileType.MARKDOWN

    def test_detect_unsupported_raises(self):
        from app.ingestion import detect_file_type
        with pytest.raises(ValueError, match="Format non supporté"):
            detect_file_type("image.png")

    def test_csv_loader_produces_one_doc_per_row(self):
        """CSV avec 3 lignes → 3 Documents."""
        import tempfile, os
        from app.ingestion import DocumentIngestion

        csv_content = b"type,prix,region\ngazoil,11.80,Casablanca\nSP95,14.20,Rabat\nSP98,15.10,Fes\n"
        ing = DocumentIngestion()

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        try:
            docs = ing._load_csv(tmp_path, "prix.csv")
            assert len(docs) == 3
            assert "gazoil" in docs[0].page_content
        finally:
            os.unlink(tmp_path)

    def test_json_list_produces_one_doc_per_item(self):
        """JSON liste de 2 objets → 2 Documents."""
        import tempfile, os, json
        from app.ingestion import DocumentIngestion

        data = [
            {"station": "AKWA Maarif", "ville": "Casablanca"},
            {"station": "AKWA Gare",   "ville": "Fes"},
        ]
        ing = DocumentIngestion()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            docs = ing._load_json(tmp_path, "stations.json")
            assert len(docs) == 2
            assert "AKWA Maarif" in docs[0].page_content
        finally:
            os.unlink(tmp_path)

    def test_excel_fallback_openpyxl(self):
        """Excel via openpyxl : chaque ligne de données → 1 Document."""
        import tempfile, os
        from app.ingestion import DocumentIngestion

        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl non installé")

        ing = DocumentIngestion()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["carburant", "prix", "date"])
        ws.append(["gazoil",    11.80,   "2025-01-15"])
        ws.append(["SP95",      14.20,   "2025-01-15"])

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            wb.save(tmp_path)
            docs = ing._load_excel_openpyxl(tmp_path, "prix.xlsx")
            assert len(docs) == 2
            assert "gazoil" in docs[0].page_content
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_upload_csv_accepted(self, client, admin_headers):
        """Upload CSV → 200."""
        mock_result = {
            "status": "success", "filename": "prix.csv",
            "doc_type": "fiche_technique", "chunks_indexed": 10,
            "collection": "akwa_knowledge",
        }
        with patch("app.main.ingestion") as mock_ing:
            mock_ing.ingest_file = AsyncMock(return_value=mock_result)
            response = await client.post(
                "/admin/upload",
                files={"file": ("prix.csv", b"type,prix\ngazoil,11.80\n", "text/csv")},
                data={"doc_type": "fiche_technique"},
                headers=admin_headers,
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_json_accepted(self, client, admin_headers):
        """Upload JSON → 200."""
        mock_result = {
            "status": "success", "filename": "stations.json",
            "doc_type": "general", "chunks_indexed": 5,
            "collection": "akwa_knowledge",
        }
        with patch("app.main.ingestion") as mock_ing:
            mock_ing.ingest_file = AsyncMock(return_value=mock_result)
            response = await client.post(
                "/admin/upload",
                files={"file": ("stations.json", b'[{"name":"AKWA"}]', "application/json")},
                data={"doc_type": "general"},
                headers=admin_headers,
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_png_rejected(self, client, admin_headers):
        """Upload PNG → 400 (les images standalone restent non supportées)."""
        response = await client.post(
            "/admin/upload",
            files={"file": ("photo.png", b"fake image", "image/png")},
            data={"doc_type": "general"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "non supporté" in response.json()["detail"].lower()


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : RATE LIMITING
# ══════════════════════════════════════════════════════════════════════════════

class TestRateLimit:

    @pytest.mark.asyncio
    async def test_rate_limit_allows_first_requests(self, client, mock_rag_response_fr):
        """Les premières requêtes doivent passer (< limite)."""
        with patch("app.main.rag_agent") as mock_agent, \
            patch("app.main.cache_service") as mock_cache:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)
            mock_cache.check_rate_limit = AsyncMock(return_value=(True, 9))
            mock_cache.get_cached_response = AsyncMock(return_value=None)
            mock_cache.set_cached_response = AsyncMock()
            mock_cache.increment_counter = AsyncMock()
            mock_cache.get_session = AsyncMock(return_value=[])

            response = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla ?"
            })

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_when_exceeded(self, client):
        """Quand la limite est dépassée → 429."""
        with patch("app.main.cache_service") as mock_cache:
            mock_cache.check_rate_limit = AsyncMock(return_value=(False, 0))

            response = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla ?"
            })

        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_429_contains_detail(self, client):
        """La réponse 429 doit contenir un message explicatif."""
        with patch("app.main.cache_service") as mock_cache:
            mock_cache.check_rate_limit = AsyncMock(return_value=(False, 0))

            response = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla ?"
            })

        assert response.status_code == 429
        assert "detail" in response.json()
        assert "requêtes" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_rate_limit_429_has_retry_after_header(self, client):
        """Le header Retry-After doit être présent dans la réponse 429."""
        with patch("app.main.cache_service") as mock_cache:
            mock_cache.check_rate_limit = AsyncMock(return_value=(False, 0))

            response = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla ?"
            })

        assert response.status_code == 429
        assert "retry-after" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limit_redis_down_allows_request(self, client, mock_rag_response_fr):
        """Si Redis est down → graceful degradation, requête autorisée."""
        with patch("app.main.rag_agent") as mock_agent, \
            patch("app.main.cache_service") as mock_cache:
            mock_agent.query = AsyncMock(return_value=mock_rag_response_fr)
            mock_cache.check_rate_limit = AsyncMock(return_value=(True, 10))
            mock_cache.get_cached_response = AsyncMock(return_value=None)
            mock_cache.set_cached_response = AsyncMock()
            mock_cache.increment_counter = AsyncMock()
            mock_cache.get_session = AsyncMock(return_value=[])

            response = await client.post("/query", json={
                "question": "Quel carburant pour Toyota Corolla ?"
            })

        assert response.status_code == 200

    def test_rate_limit_key_format(self):
        """La clé Redis doit avoir le bon format rate_limit:{ip}."""
        client_ip = "172.18.0.1"
        expected_key = f"rate_limit:{client_ip}"
        assert expected_key == "rate_limit:172.18.0.1"


# ══════════════════════════════════════════════════════════════════════════════
# TESTS : VISION — MODULE QWEN2.5-VL
# ══════════════════════════════════════════════════════════════════════════════

class TestVision:
    """
    Tests du module vision (vision.py) et de son intégration dans ingestion.py.

    Stratégie : tous les appels Ollama et PyMuPDF sont mockés.
    → Les tests s'exécutent sans serveur Ollama ni fichiers réels.
    → pytest tests/ -v -k "vision" pour lancer uniquement ces tests.
    """

    # ── Settings & Config ─────────────────────────────────────────────────────

    def test_vision_settings_exist(self):
        """Les 4 settings vision sont présents dans la config."""
        from app.config import settings
        assert hasattr(settings, "VISION_ENABLED")
        assert hasattr(settings, "VISION_MODEL")
        assert hasattr(settings, "VISION_MIN_IMAGE_BYTES")
        assert hasattr(settings, "VISION_TIMEOUT")

    def test_vision_settings_types(self):
        """Les settings vision ont les bons types."""
        from app.config import settings
        assert isinstance(settings.VISION_ENABLED, bool)
        assert isinstance(settings.VISION_MODEL, str)
        assert isinstance(settings.VISION_MIN_IMAGE_BYTES, int)
        assert isinstance(settings.VISION_TIMEOUT, int)

    def test_vision_settings_sensible_values(self):
        """Les valeurs par défaut sont cohérentes."""
        from app.config import settings
        assert settings.VISION_MIN_IMAGE_BYTES > 0
        assert settings.VISION_TIMEOUT > 0
        assert len(settings.VISION_MODEL) > 0

    # ── VisionAnalyzer — comportement désactivé ───────────────────────────────

    @pytest.mark.asyncio
    async def test_vision_disabled_returns_none(self):
        """VISION_ENABLED=False → analyze_image() retourne None sans appel Ollama."""
        # Supprimer le mock du conftest pour utiliser la vraie classe
        if "app.vision" in sys.modules:
            del sys.modules["app.vision"]

        with patch("app.config.settings") as mock_cfg:
            mock_cfg.VISION_ENABLED         = False
            mock_cfg.VISION_MODEL           = "qwen2.5vl"
            mock_cfg.VISION_MIN_IMAGE_BYTES = 5000
            mock_cfg.VISION_TIMEOUT         = 120
            mock_cfg.OLLAMA_BASE_URL        = "http://localhost:11434"

            from app.vision import VisionAnalyzer
            analyzer = VisionAnalyzer()
            result = await analyzer.analyze_image(b"x" * 10000)

        assert result is None

    @pytest.mark.asyncio
    async def test_vision_image_too_small_returns_none(self):
        """Image < VISION_MIN_IMAGE_BYTES → ignorée, retourne None sans appel Ollama."""
        if "app.vision" in sys.modules:
            del sys.modules["app.vision"]

        with patch("app.config.settings") as mock_cfg:
            mock_cfg.VISION_ENABLED         = True
            mock_cfg.VISION_MODEL           = "qwen2.5vl"
            mock_cfg.VISION_MIN_IMAGE_BYTES = 5000
            mock_cfg.VISION_TIMEOUT         = 120
            mock_cfg.OLLAMA_BASE_URL        = "http://localhost:11434"

            from app.vision import VisionAnalyzer
            analyzer = VisionAnalyzer()
            # 100 bytes << 5000 bytes minimum
            result = await analyzer.analyze_image(b"x" * 100)

        assert result is None

    # ── VisionAnalyzer — appel Ollama ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_vision_calls_ollama_generate_endpoint(self):
        """analyze_image() appelle bien /api/generate avec le bon modèle."""
        # CORRECTION : supprimer le mock conftest + patcher app.config.settings
        if "app.vision" in sys.modules:
            del sys.modules["app.vision"]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "Histogramme : GPL 46.4 MJ/kg, Gasoil 42.8 MJ/kg"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.config.settings") as mock_cfg, \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_cfg.VISION_ENABLED         = True
            mock_cfg.VISION_MODEL           = "qwen2.5vl"
            mock_cfg.VISION_MIN_IMAGE_BYTES = 5000
            mock_cfg.VISION_TIMEOUT         = 120
            mock_cfg.OLLAMA_BASE_URL        = "http://ollama:11434"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__  = AsyncMock(return_value=False)

            from app.vision import VisionAnalyzer
            analyzer = VisionAnalyzer()
            result   = await analyzer.analyze_image(b"x" * 10000, context="page 2 — rapport.pdf")

        assert result == "Histogramme : GPL 46.4 MJ/kg, Gasoil 42.8 MJ/kg"
        mock_client.post.assert_called_once()
        url_called = mock_client.post.call_args[0][0]
        assert "/api/generate" in url_called
        body_sent = mock_client.post.call_args[1]["json"]
        assert body_sent["model"] == "qwen2.5vl"

    @pytest.mark.asyncio
    async def test_vision_returns_none_on_non_exploitable_response(self):
        """Qwen répond IMAGE_NON_EXPLOITABLE → retourne None."""
        if "app.vision" in sys.modules:
            del sys.modules["app.vision"]

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "IMAGE_NON_EXPLOITABLE"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.config.settings") as mock_cfg, \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_cfg.VISION_ENABLED         = True
            mock_cfg.VISION_MODEL           = "qwen2.5vl"
            mock_cfg.VISION_MIN_IMAGE_BYTES = 5000
            mock_cfg.VISION_TIMEOUT         = 120
            mock_cfg.OLLAMA_BASE_URL        = "http://ollama:11434"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__  = AsyncMock(return_value=False)

            from app.vision import VisionAnalyzer
            analyzer = VisionAnalyzer()
            result   = await analyzer.analyze_image(b"x" * 10000)

        assert result is None

    @pytest.mark.asyncio
    async def test_vision_returns_none_on_ollama_timeout(self):
        """Timeout Ollama → retourne None sans planter le pipeline."""
        import httpx
        if "app.vision" in sys.modules:
            del sys.modules["app.vision"]

        with patch("app.config.settings") as mock_cfg, \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_cfg.VISION_ENABLED         = True
            mock_cfg.VISION_MODEL           = "qwen2.5vl"
            mock_cfg.VISION_MIN_IMAGE_BYTES = 5000
            mock_cfg.VISION_TIMEOUT         = 120
            mock_cfg.OLLAMA_BASE_URL        = "http://ollama:11434"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__  = AsyncMock(return_value=False)

            from app.vision import VisionAnalyzer
            analyzer = VisionAnalyzer()
            result   = await analyzer.analyze_image(b"x" * 10000)

        assert result is None

    @pytest.mark.asyncio
    async def test_vision_batch_respects_order(self):
        """analyze_images_batch() retourne les résultats dans le même ordre que l'entrée."""
        # CORRECTION : supprimer le mock conftest + patcher app.config.settings
        if "app.vision" in sys.modules:
            del sys.modules["app.vision"]

        with patch("app.config.settings") as mock_cfg:
            mock_cfg.VISION_ENABLED         = True
            mock_cfg.VISION_MODEL           = "qwen2.5vl"
            mock_cfg.VISION_MIN_IMAGE_BYTES = 5000
            mock_cfg.VISION_TIMEOUT         = 120
            mock_cfg.OLLAMA_BASE_URL        = "http://ollama:11434"

            from app.vision import VisionAnalyzer
            analyzer = VisionAnalyzer()

            descriptions = ["Description image A", None, "Description image C"]
            with patch.object(analyzer, "analyze_image", side_effect=descriptions):
                images  = [(b"x" * 10000, f"ctx {i}") for i in range(3)]
                results = await analyzer.analyze_images_batch(images)

        assert results[0] == "Description image A"
        assert results[1] is None
        assert results[2] == "Description image C"

    # ── Ingestion — intégration visuelle dans PDF ─────────────────────────────

    @pytest.mark.asyncio
    async def test_ingest_pdf_without_images_zero_visual_chunks(self):
        """PDF sans images → visual_chunks = 0, pipeline texte inchangé."""
        from app.ingestion import DocumentIngestion
        from langchain.schema import Document

        ing = DocumentIngestion()

        with patch.object(ing, "_load_pdf", return_value=[
                Document(page_content="Texte fiche technique GPL.",
                         metadata={"filename": "fiche.pdf", "content_type": "text"})
             ]), \
             patch.object(ing, "_extract_visual_chunks_from_pdf", return_value=[]), \
             patch("app.qdrant_store.qdrant_store") as mock_qs:  # CORRECTION

            mock_qs.add_documents.return_value = 1

            result = await ing.ingest_file(
                file_bytes=b"fake pdf",
                filename="fiche.pdf",
                doc_type="fiche_technique",
                collection="akwa_knowledge",
            )

        assert result["status"]        == "success"
        assert result["visual_chunks"] == 0
        assert result["text_chunks"]   >= 1

    @pytest.mark.asyncio
    async def test_ingest_pdf_with_images_adds_visual_chunks(self):
        """PDF avec graphiques → visual_chunks > 0, text_chunks conservés."""
        from app.ingestion import DocumentIngestion
        from langchain.schema import Document

        ing = DocumentIngestion()

        visual_doc = Document(
            page_content=(
                "[Figure page 3 — source: rapport_gpl.pdf]\n"
                "Histogramme : GPL 46.4 MJ/kg | Gasoil 42.8 MJ/kg | Axe Y : MJ/kg"
            ),
            metadata={
                "filename":     "rapport_gpl.pdf",
                "content_type": "visual",
                "page":         3,
                "vision_model": "qwen2.5vl",
            },
        )

        with patch.object(ing, "_load_pdf", return_value=[
                Document(page_content="Texte page 1 rapport GPL.",
                         metadata={"filename": "rapport_gpl.pdf", "content_type": "text"})
             ]), \
             patch.object(ing, "_extract_visual_chunks_from_pdf", return_value=[visual_doc]), \
             patch("app.qdrant_store.qdrant_store") as mock_qs:  # CORRECTION

            mock_qs.add_documents.return_value = 2

            result = await ing.ingest_file(
                file_bytes=b"fake pdf",
                filename="rapport_gpl.pdf",
                doc_type="fiche_technique",
                collection="akwa_knowledge",
            )

        assert result["visual_chunks"] == 1
        assert result["text_chunks"]   >= 1
        assert result["chunks_indexed"] == 2

    @pytest.mark.asyncio
    async def test_ingest_docx_with_images_adds_visual_chunks(self):
        """DOCX avec schéma technique → visual_chunks > 0."""
        from app.ingestion import DocumentIngestion
        from langchain.schema import Document

        ing = DocumentIngestion()

        visual_doc = Document(
            page_content=(
                "[Figure 1 — source: schema_cuve.docx]\n"
                "Schéma technique d'une cuve GPL cylindrique horizontale. "
                "Composants : soupape de sécurité, jauge de niveau, vanne d'arrêt."
            ),
            metadata={
                "filename":     "schema_cuve.docx",
                "content_type": "visual",
                "page":         1,
                "vision_model": "qwen2.5vl",
            },
        )

        with patch.object(ing, "_load_docx", return_value=[
                Document(page_content="Procédure installation cuve GPL.",
                         metadata={"filename": "schema_cuve.docx", "content_type": "text"})
             ]), \
             patch.object(ing, "_extract_visual_chunks_from_docx", return_value=[visual_doc]), \
             patch("app.qdrant_store.qdrant_store") as mock_qs:  # CORRECTION

            mock_qs.add_documents.return_value = 2

            result = await ing.ingest_file(
                file_bytes=b"fake docx",
                filename="schema_cuve.docx",
                doc_type="procedure",
                collection="akwa_knowledge",
            )

        assert result["visual_chunks"] == 1
        assert result["text_chunks"]   >= 1

    @pytest.mark.asyncio
    async def test_ingest_csv_never_extracts_visuals(self):
        """CSV → _extract_visual_chunks jamais appelé (pas d'images possibles)."""
        from app.ingestion import DocumentIngestion
        from langchain.schema import Document

        ing = DocumentIngestion()

        with patch.object(ing, "_load_csv", return_value=[
                Document(page_content="gazoil | 11.80 | Casablanca",
                         metadata={"filename": "prix.csv", "content_type": "text"})
             ]), \
             patch.object(ing, "_extract_visual_chunks_from_pdf") as mock_vis_pdf, \
             patch.object(ing, "_extract_visual_chunks_from_docx") as mock_vis_docx, \
             patch("app.qdrant_store.qdrant_store") as mock_qs:  # CORRECTION

            mock_qs.add_documents.return_value = 1

            result = await ing.ingest_file(
                file_bytes=b"type,prix\ngazoil,11.80\n",
                filename="prix.csv",
                doc_type="fiche_technique",
                collection="akwa_knowledge",
            )

        mock_vis_pdf.assert_not_called()
        mock_vis_docx.assert_not_called()
        assert result["visual_chunks"] == 0

    @pytest.mark.asyncio
    async def test_visual_chunks_not_resplit(self):
        """Les chunks visuels ne doivent PAS être re-splittés par le text splitter."""
        from app.ingestion import DocumentIngestion
        from langchain.schema import Document

        ing = DocumentIngestion()

        long_description = "Données graphique. " * 50  # ~900 chars
        visual_doc = Document(
            page_content=f"[Figure page 1 — source: test.pdf]\n{long_description}",
            metadata={
                "filename":     "test.pdf",
                "content_type": "visual",
                "page":         1,
                "vision_model": "qwen2.5vl",
            },
        )

        with patch.object(ing, "_load_pdf", return_value=[
                Document(page_content="Texte court.",
                         metadata={"filename": "test.pdf", "content_type": "text"})
             ]), \
             patch.object(ing, "_extract_visual_chunks_from_pdf", return_value=[visual_doc]), \
             patch("app.qdrant_store.qdrant_store") as mock_qs:  # CORRECTION

            captured_docs = []
            mock_qs.add_documents.side_effect = lambda col, docs: (
                captured_docs.extend(docs) or len(docs)
            )

            await ing.ingest_file(
                file_bytes=b"fake",
                filename="test.pdf",
                doc_type="general",
                collection="akwa_knowledge",
            )

        visual_chunks = [d for d in captured_docs if d.metadata.get("content_type") == "visual"]
        assert len(visual_chunks) == 1

    # ── Modèles Pydantic — champs vision ─────────────────────────────────────

    def test_ingest_response_has_visual_chunks_field(self):
        """IngestResponse contient visual_chunks et text_chunks."""
        from app.models import IngestResponse
        r = IngestResponse(
            status="success",
            filename="rapport.pdf",
            chunks_indexed=12,
            collection="akwa_knowledge",
            doc_type="fiche_technique",
            text_chunks=10,
            visual_chunks=2,
        )
        assert r.text_chunks   == 10
        assert r.visual_chunks == 2

    def test_ingest_response_visual_chunks_default_zero(self):
        """visual_chunks et text_chunks valent 0 par défaut (rétrocompatibilité)."""
        from app.models import IngestResponse
        r = IngestResponse(
            status="success",
            filename="doc.pdf",
            chunks_indexed=5,
            collection="akwa_knowledge",
            doc_type="general",
        )
        assert r.text_chunks   == 0
        assert r.visual_chunks == 0

    def test_health_response_has_vision_fields(self):
        """HealthResponse expose vision_enabled et vision_model."""
        from app.models import HealthResponse
        r = HealthResponse(
            status="healthy",
            model="qwen3:8b",
            qdrant_connected=True,
            redis_connected=True,
            vision_enabled=True,
            vision_model="qwen2.5vl",
        )
        assert r.vision_enabled is True
        assert r.vision_model  == "qwen2.5vl"

    # ── Endpoint /health — champs vision ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_exposes_vision_status(self, client):
        """GET /health retourne vision_enabled et vision_model."""
        with patch("app.main.qdrant_store") as mock_qs, \
             patch("app.main.cache_service") as mock_cs:
            mock_qs.is_healthy.return_value = True
            mock_cs.is_healthy.return_value = True

            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "vision_enabled" in data
        assert "vision_model"   in data

    # ── Endpoint /admin/upload — réponse avec vision ──────────────────────────

    @pytest.mark.asyncio
    async def test_upload_pdf_response_includes_visual_chunks(self, client, admin_headers):
        """Upload PDF → réponse contient text_chunks et visual_chunks."""
        mock_result = {
            "status":         "success",
            "filename":       "rapport_gpl.pdf",
            "doc_type":       "fiche_technique",
            "chunks_indexed": 12,
            "collection":     "akwa_knowledge",
            "text_chunks":    10,
            "visual_chunks":  2,
        }
        with patch("app.main.ingestion") as mock_ing:
            mock_ing.ingest_file = AsyncMock(return_value=mock_result)
            response = await client.post(
                "/admin/upload",
                files={"file": ("rapport_gpl.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"doc_type": "fiche_technique"},
                headers=admin_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["text_chunks"]    == 10
        assert data["visual_chunks"]  == 2
        assert data["chunks_indexed"] == 12

    @pytest.mark.asyncio
    async def test_upload_txt_response_zero_visual_chunks(self, client, admin_headers):
        """Upload TXT → visual_chunks = 0 (pas d'images dans un fichier texte)."""
        mock_result = {
            "status":         "success",
            "filename":       "faq.txt",
            "doc_type":       "faq",
            "chunks_indexed": 4,
            "collection":     "akwa_knowledge",
            "text_chunks":    4,
            "visual_chunks":  0,
        }
        with patch("app.main.ingestion") as mock_ing:
            mock_ing.ingest_file = AsyncMock(return_value=mock_result)
            response = await client.post(
                "/admin/upload",
                files={"file": ("faq.txt", b"FAQ contenu texte", "text/plain")},
                data={"doc_type": "faq"},
                headers=admin_headers,
            )

        assert response.status_code == 200
        assert response.json()["visual_chunks"] == 0