import uuid
import asyncio
from typing import Literal
from app.config import LLM_SUPERVISOR, LLM_VALIDATOR

from langgraph.graph import StateGraph, END

from app.state import OrchestratorState
from app.core.router    import route
from app.core.planner   import build_plan
from app.core.executor  import execute
from app.core.validator import validate, ask_clarification
from app.services.memory import (
    get_cache, save_cache,
    get_session_last_agent, save_session_agent,
    get_session_summary, save_session_summary,
    _save_raw_turn, get_recent_turns,
    get_turn_count, save_turn_count,
)
from app.services.summarizer import update_summary
from app.services.ollama_client import generate
from app.utils.logger import get_logger
import structlog

log = get_logger(__name__)

REWRITE_INSTRUCTIONS = {
    "fr": "Réécris la question pour qu'elle soit COMPLÈTE et autonome. Si déjà complète, retourne-la TELLE QUELLE. NE RÉPONDS PAS à la question.",
    "ar": "أعد صياغة السؤال ليكون مكتملاً ومفهوماً وحده. إذا كان مكتملاً أعده كما هو. لا تجب على السؤال.",
    "en": "Rewrite the question to be COMPLETE and self-contained. If already complete, return it AS IS. DO NOT answer the question.",
}

# ══════════════════════════════════════════════════════════════════════════════
# NŒUDS DU GRAPHE
# ══════════════════════════════════════════════════════════════════════════════

async def node_cache_check(state: OrchestratorState) -> OrchestratorState:
    """Vérifie le cache avant tout traitement."""
    structlog.contextvars.bind_contextvars(trace_id=state["trace_id"])

    # FIX: passer geo pour que les questions géolocalisées aient une clé unique
    cached = get_cache(state["question"], state["chatbot_id"], geo=state.get("geo"))
    if cached:
        log.info("Cache HIT", question=state["question"][:40])

        # FIX: même sur cache HIT, mettre à jour le compteur de tours et les
        # tours bruts pour que la session reste cohérente
        session_id = state.get("session_id")
        if session_id:
            turn_count = get_turn_count(session_id) + 1
            save_turn_count(session_id, turn_count)
            _save_raw_turn(session_id, state["question"], cached.get("answer", ""))
            log.info("Session turn saved (cache HIT)", session_id=session_id[:8], turn_count=turn_count)

        return {
            **state,
            "final_answer": cached.get("answer", ""),
            "agents_used":  cached.get("agents_used", []),
            "confidence":   cached.get("confidence", 1.0),
            "from_cache":   True,
        }
    return {**state, "from_cache": False}


async def node_rewrite(state: OrchestratorState) -> OrchestratorState:
    """
    Réécrit la question pour inclure le contexte de la session.
    Utilise le résumé de session ET les tours bruts récents.
    Support multilingue (FR, AR, EN).
    """
    session_id = state.get("session_id")
    question   = state["question"]
    language   = state.get("language", "fr")

    if not session_id:
        return {**state, "rewritten_question": question}

    summary      = get_session_summary(session_id)
    recent_turns = get_recent_turns(session_id)

    if not summary and not recent_turns:
        return {**state, "rewritten_question": question}

    context_parts = []
    if summary:
        context_parts.append(f"Résumé de session :\n{summary}")
    if recent_turns:
        turns_text = "\n".join(
            f"- User: {t['q']}\n  Assistant: {t['a'][:120]}"
            for t in recent_turns[-3:]
        )
        context_parts.append(f"Échanges récents :\n{turns_text}")

    context = "\n\n".join(context_parts)

    # ── Instructions multilingues ──────────────────────────────────────────────
    instruction = REWRITE_INSTRUCTIONS.get(language, REWRITE_INSTRUCTIONS["fr"])

    prompt = f"""[SESSION CONTEXT]
{context}

[USER QUESTION]
{question}

[INSTRUCTION]
{instruction}
Keep the language: {language}.

REWRITTEN QUESTION:"""

    try:
        rewritten = await generate(LLM_SUPERVISOR, prompt)
        rewritten = rewritten.strip()
        log.info("Query Rewriting", original=question, rewritten=rewritten, language=language)
        return {**state, "rewritten_question": rewritten}
    except Exception as e:
        log.warning("Rewrite failed — fallback question originale", error=str(e))
        return {**state, "rewritten_question": question}


async def node_router(state: OrchestratorState) -> OrchestratorState:
    """LLM choisit les agents en utilisant la question réécrite."""
    q_to_process    = state.get("rewritten_question") or state["question"]
    session_summary = get_session_summary(state["session_id"]) if state.get("session_id") else None

    agents, confidence, method, strategy = await route(
        question           = q_to_process,
        session_id         = state.get("session_id"),
        tried              = state.get("tried_agents", []),
        session_summary    = session_summary,
        agent_descriptions = state.get("agent_descriptions", {}),
        language           = state.get("language", "fr"),
    )
    log.info("Routing", agents=agents, confidence=round(confidence, 2), method=method)
    return {
        **state,
        "agents_to_call":     agents,
        "routing_confidence": confidence,
        "routing_method":     method,
        "execution_strategy": strategy,
    }


async def node_direct_answer(state: OrchestratorState) -> OrchestratorState:
    """Génère une réponse conversationnelle directe sans appeler d'agent."""
    question = state["question"]
    language = state.get("language", "fr")

    prompt = f"""Tu es un assistant conversationnel utile et amical. Réponds naturellement à l'utilisateur.

Question : {question}

Règles :
- Sois concis et chaleureux.
- Ne cherche pas à utiliser des données externes.
- Réponds en {language}.

Réponse :"""

    try:
        answer = await generate(LLM_VALIDATOR, prompt)
        answer = answer.strip()
        log.info("Réponse directe LLM", question=question[:40], answer=answer[:60])
        return {
            **state,
            "final_answer":      answer,
            "agents_used":       [],
            "validation_status": "PASS",
            "from_cache":        False,
        }
    except Exception as e:
        log.error("Erreur réponse directe", error=str(e))
        return {
            **state,
            "final_answer":      "Désolé, je n'arrive pas à répondre pour le moment.",
            "agents_used":       [],
            "validation_status": "PASS",
        }


async def node_planner(state: OrchestratorState) -> OrchestratorState:
    """Décompose la question réécrite si multi-agent."""
    q_to_process = state.get("rewritten_question") or state["question"]

    plan = await build_plan(
        question = q_to_process,
        agents   = state["agents_to_call"],
        strategy = state.get("execution_strategy", "parallel"),
    )
    log.info("Plan", strategy=plan["strategy"], steps=len(plan.get("steps", [])))
    return {**state, "execution_plan": plan}


async def node_executor(state: OrchestratorState) -> OrchestratorState:
    """Appelle les agents."""
    results = await execute(
        state["execution_plan"],
        state["chatbot_id"],
        geo      = state.get("geo"),
        language = state.get("language", "fr"),
        agent_descriptions = state.get("agent_descriptions", {}),
    )
    tried = list(state.get("tried_agents", []))
    for agent in state["agents_to_call"]:
        if agent not in tried:
            tried.append(agent)
    return {**state, "agents_results": results, "tried_agents": tried}


async def node_validator(state: OrchestratorState) -> OrchestratorState:
    """Valide les réponses et synthétise via le LLM."""
    session_summary = None
    recent_turns    = []
    if state.get("session_id"):
        session_summary = get_session_summary(state["session_id"])
        recent_turns    = get_recent_turns(state["session_id"])

    val_status, val_reason, final_answer = await validate(
        question        = state["question"],
        answers         = state["agents_results"],
        language        = state.get("language", "fr"),
        session_summary = session_summary,
        recent_turns    = recent_turns,
        system_prompt   = state.get("system_prompt", ""),
    )
    return {
        **state,
        "validation_status": val_status,
        "validation_reason": val_reason,
        "final_answer":      final_answer,
    }


async def node_clarification(state: OrchestratorState) -> OrchestratorState:
    clarif_q = await ask_clarification(state["question"])
    return {**state, "needs_clarification": True, "final_answer": clarif_q}


async def node_retry(state: OrchestratorState) -> OrchestratorState:
    count = state.get("retry_count", 0) + 1
    tried = state.get("tried_agents", [])
    if count >= 2:
        tried = []
    return {**state, "retry_count": count, "tried_agents": tried}


async def node_no_data(state):
    msgs = {"fr": "Je n'ai pas trouvé cette information.", "ar": "لم أجد هذه المعلومات.", "en": "I couldn't find this information."}
    return {**state, "final_answer": msgs.get(state.get("language","fr"), msgs["fr"]), "validation_status": "PASS"}

def _route_after_router(state):
    if state.get("agents_to_call"):
        return "planner"
    if state.get("retry_count", 0) > 0:
        return "no_data"   
    return "direct_answer"

async def _update_summary_safe(
    session_id:   str,
    question:     str,
    final_answer: str,
    language:     str,
) -> None:
    """
    Mise à jour du résumé en fire-and-forget.
    Les erreurs sont swallowées pour ne jamais bloquer la réponse principale.
    """
    try:
        new_sum = await update_summary(
            get_session_summary(session_id),
            question,
            final_answer,
            language,
        )
        save_session_summary(session_id, new_sum)
        log.info("Session summary updated (async)", session_id=session_id[:8])
    except Exception as e:
        log.warning("Summary async update failed — silently ignored", error=str(e))


async def node_save_and_return(state: OrchestratorState) -> OrchestratorState:
    """Sauvegarde le cache, la mémoire de session, et le turn_count persistant."""
    agents_used = [r["agent"] for r in state.get("agents_results", []) if r.get("_success")]
    if not agents_used:
        agents_used = state.get("agents_to_call", [])

    final_answer = state.get("final_answer", "")
    session_id   = state.get("session_id")

    if final_answer and not state.get("from_cache"):
        # FIX: passer geo pour que la clé de cache soit unique par position
        save_cache(
            state["question"],
            {"answer": final_answer, "agents_used": agents_used},
            state["chatbot_id"],
            geo=state.get("geo"),
        )

        if session_id and not state.get("needs_clarification"):
            turn_count = get_turn_count(session_id) + 1
            save_turn_count(session_id, turn_count)

            log.info(
                "Session turn saved",
                session_id = session_id[:8],
                turn_count = turn_count,
            )

            if turn_count % 4 == 0:
                # FIX: fire-and-forget — ne bloque plus la réponse
                asyncio.create_task(
                    _update_summary_safe(
                        session_id,
                        state["question"],
                        final_answer,
                        state.get("language", "fr"),
                    )
                )
            else:
                _save_raw_turn(session_id, state["question"], final_answer)

    return {
        **state,
        "agents_used": agents_used,
        "turn_count":  get_turn_count(session_id) if session_id else 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CONSTRUCTION DU GRAPHE
# ══════════════════════════════════════════════════════════════════════════════

def build_graph():
    workflow = StateGraph(OrchestratorState)

    workflow.add_node("cache_check",   node_cache_check)
    workflow.add_node("rewrite",       node_rewrite)
    workflow.add_node("router",        node_router)
    workflow.add_node("direct_answer", node_direct_answer)
    workflow.add_node("no_data",       node_no_data) 
    workflow.add_node("planner",       node_planner)
    workflow.add_node("executor",      node_executor)
    workflow.add_node("validator",     node_validator)
    workflow.add_node("clarification", node_clarification)
    workflow.add_node("retry",         node_retry)
    workflow.add_node("save",          node_save_and_return)

    workflow.set_entry_point("cache_check")

    # FIX: cache HIT → END directement (session déjà mise à jour dans node_cache_check)
    workflow.add_conditional_edges(
        "cache_check",
        lambda s: "end" if s.get("from_cache") else "rewrite",
        {"end": END, "rewrite": "rewrite"},
    )

    workflow.add_edge("rewrite", "router")

    workflow.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "direct_answer": "direct_answer",
            "no_data":       "no_data",   
            "planner":       "planner",
        },
    )

    workflow.add_edge("direct_answer", "save")
    workflow.add_edge("no_data", "save")
    workflow.add_edge("planner",       "executor")
    workflow.add_edge("executor",      "validator")

    workflow.add_conditional_edges(
        "validator",
        lambda s: (
            "save"  if s.get("validation_status") == "PASS"
            else "retry" if s.get("retry_count", 0) < 2
            else "save"
        ),
        {"save": "save", "retry": "retry", "clarification": "clarification"},
    )

    workflow.add_edge("retry",         "router")
    workflow.add_edge("clarification", "save")
    workflow.add_edge("save",          END)

    return workflow.compile()


orchestrator_graph = build_graph()


async def run(
    question:           str,
    chatbot_id:         str,
    session_id:         str  = None,
    geo:                dict = None,
    language:           str  = "fr",
    system_prompt:      str  = "",
    agent_descriptions: dict = None,
) -> dict:
    initial_state: OrchestratorState = {
        "question":           question,
        "rewritten_question": None,
        "chatbot_id":         chatbot_id,
        "session_id":         session_id,
        "geo":                geo,
        "trace_id":           str(uuid.uuid4())[:8],
        "language":           language,
        "system_prompt":      system_prompt,
        "agent_descriptions": agent_descriptions or {},
        "agents_to_call":     [],
        "execution_plan":     {},
        "routing_confidence": 0.0,
        "agents_results":     [],
        "tried_agents":       [],
        "retry_count":        0,
        "final_answer":       "",
        "turn_count":         0,
    }
    return await orchestrator_graph.ainvoke(initial_state)