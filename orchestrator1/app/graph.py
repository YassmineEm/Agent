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
    get_turn_count, save_turn_count,          # ← AJOUT
)
from app.services.summarizer import update_summary
from app.services.ollama_client import generate
from app.utils.logger import get_logger
import structlog

log = get_logger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# NŒUDS DU GRAPHE
# ══════════════════════════════════════════════════════════════════════════════

async def node_cache_check(state: OrchestratorState) -> OrchestratorState:
    """Vérifie le cache avant tout traitement."""
    structlog.contextvars.bind_contextvars(trace_id=state["trace_id"])
    cached = get_cache(state["question"], state["chatbot_id"])
    if cached:
        log.info("Cache HIT", question=state["question"][:40])
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
    """
    session_id = state.get("session_id")
    question   = state["question"]

    if not session_id:
        return {**state, "rewritten_question": question}

    # ── Lire résumé ET tours récents ─────────────────────────────────────────
    summary      = get_session_summary(session_id)
    recent_turns = get_recent_turns(session_id)

    # Rien à injecter → retour immédiat
    if not summary and not recent_turns:
        return {**state, "rewritten_question": question}

    # ── Construire le bloc contexte ───────────────────────────────────────────
    context_parts = []
    if summary:
        context_parts.append(f"Résumé de session :\n{summary}")
    if recent_turns:
        turns_text = "\n".join(
            f"- User: {t['q']}\n  Assistant: {t['a'][:120]}"
            for t in recent_turns[-3:]          # 3 derniers tours suffisent
        )
        context_parts.append(f"Échanges récents :\n{turns_text}")

    context = "\n\n".join(context_parts)

    prompt = f"""[CONTEXTE DE SESSION]
{context}

[QUESTION UTILISATEUR]
{question}

[INSTRUCTION]
Réécris la question utilisateur pour qu'elle soit COMPLÈTE et compréhensible seule.
- Si la question est déjà complète et explicite, retourne-la TELLE QUELLE sans modification.
- Complète uniquement si elle fait référence implicite au contexte (ex : "et là-bas ?", "à Marrakech ?").
- Garde la langue : {state.get('language', 'fr')}.
- NE RÉPONDS PAS à la question. Donne UNIQUEMENT la question réécrite.

QUESTION RÉÉCRITE :"""

    try:
        rewritten = await generate(LLM_SUPERVISOR, prompt)
        rewritten = rewritten.strip()
        log.info("Query Rewriting", original=question, rewritten=rewritten)
        return {**state, "rewritten_question": rewritten}
    except Exception as e:
        log.warning("Rewrite failed — fallback question originale", error=str(e))
        return {**state, "rewritten_question": question}


async def node_router(state: OrchestratorState) -> OrchestratorState:
    """LLM choisit les agents en utilisant la question réécrite."""
    q_to_process = state.get("rewritten_question") or state["question"]

    session_summary = None
    if state.get("session_id"):
        session_summary = get_session_summary(state["session_id"])

    agents, confidence, method, strategy = await route(
        question   = q_to_process,
        session_id = state.get("session_id"),
        tried      = state.get("tried_agents", []),
        session_summary = session_summary,
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
        question        = state["question"],    # validation sur la question originale
        answers         = state["agents_results"],
        language        = state.get("language", "fr"),
        session_summary = session_summary,
        recent_turns    = recent_turns,
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
    return {**state, "retry_count": count}


async def node_save_and_return(state: OrchestratorState) -> OrchestratorState:
    """Sauvegarde le cache, la mémoire de session, et le turn_count persistant."""
    agents_used = [r["agent"] for r in state.get("agents_results", []) if r.get("_success")]
    if not agents_used:
        agents_used = state.get("agents_to_call", [])

    final_answer = state.get("final_answer", "")
    session_id   = state.get("session_id")

    if final_answer and not state.get("from_cache"):
        # ── Cache de réponse (clé = hash de la question originale) ───────────
        save_cache(
            state["question"],
            {"answer": final_answer, "agents_used": agents_used},
            state["chatbot_id"],
        )

        if session_id and not state.get("needs_clarification"):
            # ── Lire le turn_count PERSISTANT depuis Redis ────────────────────
            turn_count = get_turn_count(session_id) + 1
            save_turn_count(session_id, turn_count)  # ← persister pour la prochaine requête

            log.info(
                "Session turn saved",
                session_id = session_id[:8],
                turn_count = turn_count,
            )

            if turn_count % 4 == 0:
                # ── Tous les 4 tours : générer/mettre à jour le résumé ────────
                new_sum = await update_summary(
                    get_session_summary(session_id),
                    state["question"],
                    final_answer,
                    state.get("language", "fr"),
                )
                save_session_summary(session_id, new_sum)
                log.info("Session summary updated", session_id=session_id[:8])
            else:
                # ── Sinon : stocker le tour brut (accessible par node_rewrite) ─
                _save_raw_turn(session_id, state["question"], final_answer)

    return {
        **state,
        "agents_used": agents_used,
        # turn_count dans le state = valeur Redis courante (pour info)
        "turn_count": get_turn_count(session_id) if session_id else 0,
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
    workflow.add_node("planner",       node_planner)
    workflow.add_node("executor",      node_executor)
    workflow.add_node("validator",     node_validator)
    workflow.add_node("clarification", node_clarification)
    workflow.add_node("retry",         node_retry)
    workflow.add_node("save",          node_save_and_return)

    workflow.set_entry_point("cache_check")

    workflow.add_conditional_edges(
        "cache_check",
        lambda s: "end" if s.get("from_cache") else "rewrite",
        {"end": END, "rewrite": "rewrite"},
    )

    workflow.add_edge("rewrite", "router")

    workflow.add_conditional_edges(
        "router",
        lambda s: "direct_answer" if not s.get("agents_to_call") else "planner",
        {"direct_answer": "direct_answer", "planner": "planner"},
    )

    workflow.add_edge("direct_answer", "save")
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
    question:   str,
    chatbot_id: str,
    session_id: str  = None,
    geo:        dict = None,
    language:   str  = "fr",
) -> dict:
    initial_state: OrchestratorState = {
        "question":           question,
        "rewritten_question": None,
        "chatbot_id":         chatbot_id,
        "session_id":         session_id,
        "geo":                geo,
        "trace_id":           str(uuid.uuid4())[:8],
        "language":           language,
        "agents_to_call":     [],
        "execution_plan":     {},
        "routing_confidence": 0.0,
        "agents_results":     [],
        "tried_agents":       [],
        "retry_count":        0,
        "final_answer":       "",
        "turn_count":         0,    # sera écrasé par la valeur Redis dans node_save
    }
    return await orchestrator_graph.ainvoke(initial_state)