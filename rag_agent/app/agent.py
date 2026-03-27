import time
import json
import re
import asyncio
from typing import List, Optional
import math

from langchain_ollama import ChatOllama
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

log = get_logger(__name__)


RAG_PROMPT = PromptTemplate.from_template("""
Tu es l'assistant AKWA, expert en gaz et carburant au Maroc.
Tu réponds de façon précise, professionnelle et concise.

RÈGLES STRICTES :
1. Base-toi UNIQUEMENT sur le contexte fourni ci-dessous.
2. Le contexte peut être dans une langue différente de la question — c'est normal.
   Tu dois TRADUIRE et SYNTHÉTISER les informations du contexte pour répondre.
3. Si après lecture attentive du contexte l'information est vraiment absente, réponds :
   - En français  : "Je n'ai pas cette information dans ma base de connaissances AKWA."
   - En anglais   : "I don't have this information in the AKWA knowledge base."
   - En arabe     : "ليست لدي هذه المعلومات في قاعدة معرفة أكوا."
4. Réponds OBLIGATOIREMENT en {language}. Ne change pas de langue.
5. Sois concis : maximum 3-4 phrases sauf si une explication technique est nécessaire.
6. Si la confiance est faible (score < 0.4), commence ta réponse par :
   - En français  : "D'après les informations disponibles : "
   - En anglais   : "Based on available information: "
   - En arabe     : "بناءً على المعلومات المتاحة: "

{history_section}

CONTEXTE (extraits des documents AKWA — peut être en arabe, français ou anglais) :
─────────────────────────────────────────
{context}
─────────────────────────────────────────

QUESTION : {question}

RÉPONSE en {language} (traduis depuis le contexte si nécessaire) :
""")


class RAGAgent:
    """
    Agent RAG avec pipeline en 7 étapes :
    1. Cache check (Redis)
    2. Détection automatique de la langue
    3. Récupération historique session
    4. Hybrid search multilingue (Dense + BM25 + RRF)
    5. Cross-encoder reranking (bge-reranker-base multilingue)
    6. LLM generation (qwen3:8b) — réponse dans la langue détectée
    7. Cache + session update
    
    Support multi-chatbot : chaque chatbot a sa propre collection Qdrant.
    """

    def __init__(self):
        self.llm = ChatOllama(
            model=settings.RAG_LLM_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,
            num_predict=512,
        )

        self._reranker = None
        log.info("RAGAgent prêt", llm=settings.RAG_LLM_MODEL)

    @property
    def reranker(self) -> CrossEncoder:
        """Charge bge-reranker-base en RAM uniquement à la première utilisation."""
        if self._reranker is None:
            log.info("Chargement cross-encoder...", model="BAAI/bge-reranker-base")
            self._reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
            log.info("Cross-encoder prêt")
        return self._reranker


    async def _detect_language(self, question: str) -> str:
        """
        Détecte automatiquement la langue de la question via le LLM.
        Supprime les balises <think> de qwen3 avant de parser la réponse.
        Fallback sur "français" si la détection échoue.
        """
        prompt = (
            "Détecte la langue de cette question. "
            "Réponds UNIQUEMENT avec le nom complet de la langue en français, "
            "sans ponctuation ni explication. "
            "Exemples de réponses valides : français, anglais, arabe\n\n"
            f"Question : {question}"
        )
        try:
            response = await self.llm.ainvoke(prompt)
            raw = response.content.strip()

            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            detected = raw.lower()
            detected = re.sub(r'[^a-zàâäéèêëîïôùûüç]', '', detected)
            log.info("Langue détectée", language=detected, question=question[:50])
            return detected if detected else "français"
        except Exception as e:
            log.warning("Détection langue échouée, fallback français", error=str(e))
            return "français"



    async def _translate_query(self, question: str) -> list[str]:
        """
        Traduit la question en FR, EN et AR pour chercher dans tous les documents
        quelle que soit leur langue d'indexation.
        Supprime les balises <think> de qwen3 avant de parser le JSON.
        """
        prompt = (
            "Traduis cette question en français, anglais et arabe. "
            "Réponds UNIQUEMENT en JSON valide, sans explication ni balises markdown.\n"
            "Format exact : {\"fr\": \"...\", \"en\": \"...\", \"ar\": \"...\"}\n\n"
            f"Question : {question}"
        )
        try:
            response = await self.llm.ainvoke(prompt)
            raw = response.content.strip()

            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            match = re.search(r'\{.*?\}', raw, re.DOTALL)
            if match:
                translations = json.loads(match.group())
                queries = [question]
                for translated in translations.values():
                    if translated and translated.strip() != question.strip():
                        queries.append(translated.strip())
                log.info("Traduction réussie", nb_queries=len(queries))
                return queries
        except Exception as e:
            log.warning("Traduction échouée, recherche langue originale uniquement", error=str(e))

        return [question]



    async def _multi_language_search(
        self,
        question: str,
        chatbot_id: str,
        doc_type_filter: Optional[str] = None,
    ) -> List[Document]:
        """
        Traduit la question dans toutes les langues et lance les recherches en parallèle.
        Fusionne et déduplique les résultats.
        Cherche dans la collection du chatbot spécifié.
        """
        queries = await self._translate_query(question)
        log.info("Recherche multilingue", nb_queries=len(queries),
                chatbot_id=chatbot_id,
                collection=chatbot_id)

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
        if len(docs) <= top_n:
            pairs = [(query, doc.page_content) for doc in docs]
            scores = self.reranker.predict(pairs)
            return docs, list(scores)

        pairs = [(query, doc.page_content) for doc in docs]
        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        top_docs = [doc for _, doc in ranked[:top_n]]
        top_scores = [float(s) for s, _ in ranked[:top_n]]

        log.info("Reranking effectué", candidates=len(docs), selected=len(top_docs),
                top_score=top_scores[0] if top_scores else 0)
        return top_docs, top_scores



    def _compute_confidence(self, docs: List[Document], rerank_scores: List[float]) -> float:
        if not docs or not rerank_scores:
            return 0.0
        top_score = rerank_scores[0]
        normalized = 1 / (1 + math.exp(-top_score / 3))
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
        response = await self.llm.ainvoke(prompt)
        raw = response.content

        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        return raw



    async def query(
        self,
        question: str,
        chatbot_id: str,                  
        doc_type_filter: Optional[str] = None,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        language: str = None,
    ) -> QueryResponse:
        """
        Pipeline RAG complet avec isolation par chatbot.
        
        Args:
            question: Question de l'utilisateur
            chatbot_id: Identifiant unique du chatbot (utilisé comme nom de collection Qdrant)
            doc_type_filter: Filtrer par type de document (optionnel)
            session_id: ID de session pour la mémoire conversationnelle
            trace_id: ID de traçage pour les logs
            language: Langue forcée (auto-détection si non spécifiée)
        """
        start_time = time.time()
        log.info("RAG query démarrée", 
                question=question[:80],
                chatbot_id=chatbot_id,
                filter=doc_type_filter, 
                trace_id=trace_id)


        await cache_service.increment_counter(f"rag_queries:{chatbot_id}")
        cached = await cache_service.get_cached_response(
            question=question,
            chatbot_id=chatbot_id,
            doc_type=doc_type_filter
        )
        if cached:
            await cache_service.increment_counter(f"rag_cache_hits:{chatbot_id}")
            log.info("Réponse servie depuis cache", trace_id=trace_id)
            return QueryResponse(**cached)

        if not language or language.strip().lower() in ("auto", ""):
                detected_language = await self._detect_language(question)
        else:
                detected_language = language.strip().lower()
        log.info("Langue utilisée", language=detected_language, trace_id=trace_id)


        history = []
        if session_id:
            history = await cache_service.get_session(chatbot_id, session_id)
        history_section = ""
        if history:
            last = history[-2:]
            lines = [f"Q: {h['q']}\nA: {h['a']}" for h in last]
            history_section = "HISTORIQUE DE CONVERSATION RÉCENT :\n" + "\n\n".join(lines) + "\n"

       
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
            log.warning("Aucun document trouvé", 
                       question=question[:80], 
                       chatbot_id=chatbot_id,
                       trace_id=trace_id)
            return QueryResponse(
                answer="Je n'ai pas trouvé d'information pertinente dans la base de connaissances de ce chatbot.",
                sources=[],
                chunks_used=0,
                confidence=0.0,
                agent="rag_agent",
                model_used=settings.RAG_LLM_MODEL,
                session_id=session_id,
            )


        best_docs, rerank_scores = self._rerank(question, candidates, settings.TOP_K_FINAL)


        context = self._build_context(best_docs)
        prompt = RAG_PROMPT.format(
            language=detected_language,
            history_section=history_section,
            context=context,
            question=question,
        )

        try:
            answer = await self._call_llm(prompt)
        except Exception as e:
            log.error("LLM génération échouée", error=str(e), trace_id=trace_id)
            answer = "Désolé, le service de génération est temporairement indisponible."


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


        await cache_service.set_cached_response(
            question=question,
            chatbot_id=chatbot_id,        
            doc_type=doc_type_filter,
            response=response.model_dump()
        )
        if session_id:
            await cache_service.update_session(
                chatbot_id=chatbot_id,   
                session_id=session_id,
                question=question,
                answer=answer
            )

        elapsed = round(time.time() - start_time, 3)
        log.info("RAG query terminée", 
                elapsed_s=elapsed, 
                chunks_used=len(best_docs),
                confidence=response.confidence, 
                language=detected_language, 
                trace_id=trace_id)

        return response


# Singleton
rag_agent = RAGAgent()