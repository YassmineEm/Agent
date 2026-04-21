import time
import json
import re
import asyncio
from typing import List, Optional
import math

from langchain.prompts import PromptTemplate
from langchain.schema import Document
from sentence_transformers import CrossEncoder
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
import httpx
import logging

from app.config import settings
from app.qdrant_store import qdrant_store
from app.cache import cache_service
from app.models import QueryResponse, SourceDoc
from app.logger import get_logger
from app.ollama_client import generate, generate_fast

log = get_logger(__name__)


RAG_PROMPT = PromptTemplate.from_template("""
Tu es l'assistant AKWA, expert en gaz et carburant au Maroc.

IMPORTANT : Tu DISPOSES d'informations dans le CONTEXTE ci-dessous.
Tu DOIS les utiliser pour répondre.

RÈGLES :
1. EXTRAIS les informations du contexte pour répondre à la question.
2. Si le contexte contient un prix, donne-le directement et sans hésitation.
3. Ne dis JAMAIS "je n'ai pas cette information" si le contexte contient des données.
4. Réponds en {language}.

{history_section}
CONTEXTE (extraits des documents AKWA) :
{context}

QUESTION : {question}

RÉPONSE en {language} (utilise UNIQUEMENT les données du contexte) :
""")


class RAGAgent:
    """
    Agent RAG avec pipeline en 7 étapes :
    1. Cache check (Redis)
    2. Détection automatique de la langue  ← mistral via generate_fast()
    3. Récupération historique session
    4. Hybrid search multilingue            ← traduction via generate_fast()
    5. Cross-encoder reranking
    6. LLM generation                       ← qwen3:8b via generate()
    7. Cache + session update
    """

    def __init__(self):
        self._reranker = None
        log.info(
            "RAGAgent prêt avec client HTTP personnalisé",
            llm=settings.RAG_LLM_MODEL,
            fast_model="mistral",
            ollama_url=settings.OLLAMA_BASE_URL,
        )

    @property
    def reranker(self) -> CrossEncoder:
        if self._reranker is None:
            log.info(
                "Chargement cross-encoder multilingue (léger)...",
                model="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
            )
            self._reranker = CrossEncoder(
                "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
                max_length=512,
            )
            log.info("Cross-encoder multilingue prêt")
        return self._reranker

    async def _detect_language(self, question: str) -> str:
        """
        Détecte la langue via mistral (generate_fast) — pas de <think>, réponse immédiate.
        Fallback sur "français" si échec.
        """
        prompt = (
            "Detect the language of this question. "
            "Reply with ONLY the full language name in French, no punctuation, no explanation.\n"
            "Valid examples: français, anglais, arabe\n\n"
            f"Question: {question}"
        )
        try:
            # mistral via generate_fast — max 10 tokens suffisent pour un nom de langue
            raw = await generate_fast(prompt, temperature=0.0, max_tokens=10, timeout=15)
            detected = raw.lower().strip()
            detected = re.sub(r'[^a-zàâäéèêëîïôùûüç]', '', detected)
            log.info("Langue détectée", language=detected, question=question[:50])
            return detected if detected else "français"
        except Exception as e:
            log.warning("Détection langue échouée, fallback français", error=str(e))
            return "français"

    async def _translate_query(self, question: str) -> list[str]:
        """
        Traduit la question en FR, EN et AR via mistral (generate_fast).
        mistral répond directement en JSON sans <think>.
        Retourne toujours au moins [question] en cas d'échec.
        """
        prompt = (
            'Translate this question to French, English and Arabic.\n'
            'Reply with ONLY this exact JSON, nothing else:\n'
            '{"fr": "...", "en": "...", "ar": "..."}\n\n'
            f'Question: {question}'
        )

        try:
            response_text = await generate_fast(
                prompt, temperature=0.0, max_tokens=200, timeout=20
            )

            # Nettoyage des fences markdown résiduelles
            response_text = re.sub(r'```[a-z]*\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)
            response_text = response_text.strip()

            # Extraction JSON — on cherche d'abord l'objet complet avec les 3 clés
            match = re.search(
                r'\{[^{}]*"fr"[^{}]*"en"[^{}]*"ar"[^{}]*\}',
                response_text,
                re.DOTALL,
            )
            if not match:
                match = re.search(r'\{.*?\}', response_text, re.DOTALL)

            if match:
                data = json.loads(match.group())
                queries = [question]
                for lang in ['fr', 'en', 'ar']:
                    val = data.get(lang, "").strip()
                    if val and val != question.strip():
                        queries.append(val)
                log.info("Traduction réussie", nb_queries=len(queries), translations=data)
                return queries

            log.warning(
                "Aucun JSON trouvé dans la réponse de traduction",
                response_preview=response_text[:300],
            )

        except asyncio.TimeoutError:
            log.warning("Traduction timeout — fallback question originale")
        except json.JSONDecodeError as e:
            log.warning("JSON invalide dans la réponse de traduction", error=str(e))
        except Exception as e:
            log.warning("Traduction échouée", error=str(e))

        return [question]

    async def _multi_language_search(
        self,
        question: str,
        chatbot_id: str,
        doc_type_filter: Optional[str] = None,
    ) -> List[Document]:
        queries = await self._translate_query(question)
        log.info(
            "Recherche multilingue",
            nb_queries=len(queries),
            chatbot_id=chatbot_id,
            collection=chatbot_id,
        )

        search_tasks = [
            qdrant_store.hybrid_search(
                collection_name=chatbot_id,
                query=q,
                top_k=10,
                doc_type_filter=doc_type_filter,
            )
            for q in queries
        ]
        results_per_lang = await asyncio.gather(*search_tasks, return_exceptions=True)

        seen = set()
        merged = []
        for results in results_per_lang:
            if isinstance(results, Exception):
                log.warning("Recherche échouée pour une langue", error=str(results))
                continue
            for doc in results:
                key = doc.page_content[:100]
                if key not in seen:
                    seen.add(key)
                    merged.append(doc)

        log.info("Résultats fusionnés", total_docs=len(merged))
        return merged

    def _rerank(
        self, query: str, docs: List[Document], top_n: int
    ) -> tuple[List[Document], List[float]]:
        if not docs:
            return [], []
        pairs = [(query, doc.page_content) for doc in docs]
        scores = self.reranker.predict(pairs)
        if len(docs) <= top_n:
            return docs, list(scores)
        ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        top_docs = [doc for _, doc in ranked[:top_n]]
        top_scores = [float(s) for s, _ in ranked[:top_n]]
        log.info(
            "Reranking effectué",
            candidates=len(docs),
            selected=len(top_docs),
            top_score=top_scores[0] if top_scores else 0,
        )
        return top_docs, top_scores

    def _compute_confidence(
        self, docs: List[Document], rerank_scores: List[float]
    ) -> float:
        if not docs or not rerank_scores:
            return 0.0
        normalized = 1 / (1 + math.exp(-rerank_scores[0] / 3))
        return round(normalized, 2)

    def _build_context(self, docs: List[Document]) -> str:
        parts = []
        for i, doc in enumerate(docs, 1):
            filename = doc.metadata.get("filename", "Document inconnu")
            doc_type = doc.metadata.get("doc_type", "")
            parts.append(f"[Source {i}: {filename} ({doc_type})]\n{doc.page_content}")
        return "\n\n".join(parts)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    async def _call_llm(self, prompt: str) -> str:
        """
        Génération RAG finale via qwen3:8b avec think:false racine.
        Le nettoyage <think> et le fallback mistral sont gérés dans generate().
        """
        return await generate(prompt, temperature=0.1, max_tokens=512, timeout=90)

    async def query(
        self,
        question: str,
        chatbot_id: str,
        doc_type_filter: Optional[str] = None,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        language: str = None,
    ) -> QueryResponse:
        start_time = time.time()
        log.info(
            "RAG query démarrée",
            question=question[:80],
            chatbot_id=chatbot_id,
            filter=doc_type_filter,
            trace_id=trace_id,
        )

        # ── Cache ──────────────────────────────────────────────────────────────
        await cache_service.increment_counter(f"rag_queries:{chatbot_id}")
        cached = await cache_service.get_cached_response(
            question=question,
            chatbot_id=chatbot_id,
            doc_type=doc_type_filter,
        )
        if cached:
            await cache_service.increment_counter(f"rag_cache_hits:{chatbot_id}")
            log.info("Réponse servie depuis cache", trace_id=trace_id)
            return QueryResponse(**cached)

        # ── Langue ────────────────────────────────────────────────────────────
        if not language or language.strip().lower() in ("auto", ""):
            detected_language = await self._detect_language(question)
        else:
            detected_language = language.strip().lower()
        log.info("Langue utilisée", language=detected_language, trace_id=trace_id)

        # ── Historique session ─────────────────────────────────────────────────
        history = []
        if session_id:
            history = await cache_service.get_session(chatbot_id, session_id)

        history_section = ""
        if history:
            last = history[-2:]
            lines = [f"Q: {h['q']}\nA: {h['a']}" for h in last]
            history_section = (
                "HISTORIQUE DE CONVERSATION RÉCENT :\n"
                + "\n\n".join(lines)
                + "\n\n"
            )

        # ── Recherche hybrid multilingue ──────────────────────────────────────
        try:
            candidates = await self._multi_language_search(
                question=question,
                chatbot_id=chatbot_id,
                doc_type_filter=doc_type_filter,
            )
        except Exception as e:
            log.error("Recherche multilingue échouée", error=str(e), trace_id=trace_id)
            candidates = []

        if not candidates:
            _no_result_messages = {
                "français": "Je n'ai pas trouvé d'information pertinente dans la base de connaissances AKWA.",
                "anglais":  "I couldn't find relevant information in the AKWA knowledge base.",
                "arabe":    "لم أجد معلومات ذات صلة في قاعدة المعرفة AKWA.",
                "english":  "I couldn't find relevant information in the AKWA knowledge base.",
                "arabic":   "لم أجد معلومات ذات صلة في قاعدة المعرفة AKWA.",
            }
            no_result_msg = _no_result_messages.get(
                detected_language, _no_result_messages["français"]
            )
            return QueryResponse(
                answer=no_result_msg,
                sources=[],
                chunks_used=0,
                confidence=0.0,
                agent="rag_agent",
                model_used=settings.RAG_LLM_MODEL,
                session_id=session_id,
            )

        # ── Reranking ──────────────────────────────────────────────────────────
        best_docs, rerank_scores = self._rerank(question, candidates, settings.TOP_K_FINAL)

        # ── Prompt ────────────────────────────────────────────────────────────
        context = self._build_context(best_docs)
        prompt = RAG_PROMPT.format(
            language=detected_language,
            history_section=history_section,   # présent dans le template
            context=context,
            question=question,
        )

        # ── Génération LLM ─────────────────────────────────────────────────────
        try:
            answer = await self._call_llm(prompt)
        except Exception as e:
            log.error("LLM génération échouée", error=str(e), trace_id=trace_id)
            answer = "Désolé, le service de génération est temporairement indisponible."

        # ── Réponse ───────────────────────────────────────────────────────────
        sources = [
            SourceDoc(
                filename=doc.metadata.get("filename", "Inconnu"),
                doc_type=doc.metadata.get("doc_type", "general"),
                chunk_preview=doc.page_content[:80] + "...",
            )
            for doc in best_docs
        ]

        response = QueryResponse(
            answer=answer,
            sources=sources,
            chunks_used=len(best_docs),
            confidence=self._compute_confidence(best_docs, rerank_scores),
            agent="rag_agent",
            model_used=settings.RAG_LLM_MODEL,
            session_id=session_id,
        )

        # ── Cache + session ────────────────────────────────────────────────────
        await cache_service.set_cached_response(
            question=question,
            chatbot_id=chatbot_id,
            doc_type=doc_type_filter,
            response=response.model_dump(),
        )
        if session_id:
            await cache_service.update_session(
                chatbot_id=chatbot_id,
                session_id=session_id,
                question=question,
                answer=answer,
            )

        elapsed = round(time.time() - start_time, 3)
        log.info(
            "RAG query terminée",
            elapsed_s=elapsed,
            chunks_used=len(best_docs),
            confidence=response.confidence,
            language=detected_language,
            trace_id=trace_id,
        )

        return response


# Singleton
rag_agent = RAGAgent()