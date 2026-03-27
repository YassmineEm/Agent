# tests/conftest.py
"""
Mock des singletons au démarrage pour éviter les connexions réelles
à Ollama, Qdrant et Redis pendant les tests.
"""
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# ── Mock qdrant_store AVANT tout import de app ────────────────────────────────
mock_qdrant_store = MagicMock()
mock_qdrant_store.is_healthy.return_value = True
mock_qdrant_store.add_documents.return_value = 5
mock_qdrant_store.list_documents.return_value = []
mock_qdrant_store.delete_document.return_value = 3
mock_qdrant_store.setup_collection = MagicMock()
mock_qdrant_store.hybrid_search = AsyncMock(return_value=[])

# ── Mock vision_analyzer AVANT tout import de app ────────────────────────────
mock_vision_analyzer = MagicMock()
mock_vision_analyzer.analyze_image = AsyncMock(return_value=None)
mock_vision_analyzer.analyze_images_batch = AsyncMock(return_value=[])

# ── Mock cache_service AVANT tout import de app ──────────────────────────────
mock_cache_service = MagicMock()
mock_cache_service.is_healthy.return_value = True
mock_cache_service.connect = AsyncMock()
mock_cache_service.disconnect = AsyncMock()
mock_cache_service.get_cached_response = AsyncMock(return_value=None)
mock_cache_service.set_cached_response = AsyncMock()
mock_cache_service.increment_counter = AsyncMock()
mock_cache_service.get_session = AsyncMock(return_value=[])
mock_cache_service.update_session = AsyncMock()
mock_cache_service.check_rate_limit = AsyncMock(return_value=(True, 9))
mock_cache_service._make_key = lambda self, q, c, d: f"rag:response:{hash(q)}"

# ── Injection dans sys.modules avant les imports ──────────────────────────────
qdrant_module = MagicMock()
qdrant_module.qdrant_store = mock_qdrant_store
qdrant_module.QdrantStore = MagicMock(return_value=mock_qdrant_store)
sys.modules["app.qdrant_store"] = qdrant_module

vision_module = MagicMock()
vision_module.vision_analyzer = mock_vision_analyzer
vision_module.VisionAnalyzer = MagicMock(return_value=mock_vision_analyzer)
sys.modules["app.vision"] = vision_module