from typing import TypedDict, Optional, Any

class OrchestratorState(TypedDict):
    # ── Entrée ───────────────────────────────────────────────────────
    question:   str
    rewritten_question: Optional[str]  # ← NOUVEAU : Question avec contexte
    chatbot_id: str
    session_id: Optional[str]
    trace_id:   str
    language:   str


    system_prompt: str
    agent_descriptions: dict[str, str]

    # ── Routing ──────────────────────────────────────────────────────
    agents_to_call:      list[str]       # ex: ["sql", "location"]
    execution_plan:      dict            # ex: {"sql": "prix gazoil ?", "location": "..."}
    routing_confidence:  float
    routing_method:      str             # "fast_rule" | "llm" | "session_sticky"
    execution_strategy:  str
    
    # ── Exécution ────────────────────────────────────────────────────
    agents_results:  list[dict]          # réponses brutes des agents
    tried_agents:    list[str]
    retry_count:     int

    # ── Validation ───────────────────────────────────────────────────
    validation_status:  str               # "PASS" | "RETRY" | "CLARIFY"
    validation_reason:  str

    # ── Sortie ───────────────────────────────────────────────────────
    final_answer:        str
    agents_used:         list[str]
    confidence:          float
    from_cache:          bool
    needs_clarification: bool
    clarification_question: Optional[str]
    geo: Optional[dict]

    turn_count: int