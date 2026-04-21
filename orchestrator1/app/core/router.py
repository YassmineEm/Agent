import json
from app.services.ollama_client import chat_with_tools, generate_json
from app.services.memory import get_session_last_agent
from app.config import LLM_SUPERVISOR, ROUTING_CONFIDENCE_MIN
from app.utils.logger import get_logger

log = get_logger(__name__)


# ── Descriptions par défaut (si l'admin n'a rien configuré) ──────────────────

DEFAULT_DESCRIPTIONS = {
    "sql": (
        "Use for structured data: stations, fuel prices (gasoline, diesel), "
        "product codes, GPS coordinates, station lists by city."
    ),
    "rag": (
        "Use for technical documentation: lubricant specs (Qualix, Havoline, Delo, Mega), "
        "viscosity, API/ACEA standards, product prices from documents."
    ),
    "location": (
        "Use for geolocation: find nearest station, calculate distance, map directions. "
        "ALWAYS requires sql first (sequential) to get station coordinates."
    ),
    "weather": (
        "Use only for weather questions: temperature, rain, wind, forecasts."
    ),
}

# ── Texte fixe pour route_multi et route_direct ───────────────────────────────

_DIRECT_DESCRIPTION = (
    "Use for simple conversation only: greetings, thanks, identity questions, small talk. "
    "WARNING: if the question mentions fuel, price, station, oil, lubricant, GPS, "
    "distance — NEVER use route_direct. Use the appropriate domain agent instead."
)


def _build_multi_description(agent_descriptions: dict) -> str:
    """
    Construit la description de route_multi en injectant les vraies descriptions
    des agents AdminUI dans les exemples séquentiels et parallèles.

    AVANT (bug) : MULTI_DESCRIPTION était hardcodée avec des exemples génériques
    qui ne reflétaient pas le contenu réel de chaque agent.

    APRÈS (fix) : les exemples utilisent les descriptions AdminUI pour que
    le LLM comprenne concrètement quand orchestrer SQL→Location, SQL→RAG, etc.
    """
    sql_desc  = agent_descriptions.get("sql")  or DEFAULT_DESCRIPTIONS["sql"]
    rag_desc  = agent_descriptions.get("rag")  or DEFAULT_DESCRIPTIONS["rag"]
    loc_desc  = agent_descriptions.get("location") or DEFAULT_DESCRIPTIONS["location"]

    # Résumer les descriptions pour les exemples (ne pas les dupliquer en entier)
    sql_short = sql_desc[:80].rstrip() + ("..." if len(sql_desc) > 80 else "")
    rag_short = rag_desc[:80].rstrip() + ("..." if len(rag_desc) > 80 else "")
    loc_short = loc_desc[:80].rstrip() + ("..." if len(loc_desc) > 80 else "")

    return (
        "Use when the question requires MULTIPLE agents working together.\n\n"
        "STRATEGY RULES:\n"
        "- PARALLEL: agents are independent (run simultaneously). "
        "Use when each agent answers a different part of the question independently.\n"
        "- SEQUENTIAL: output of agent 1 is needed as input for agent 2. "
        "Use when step 2 depends on step 1's result.\n\n"
        "AGENT CAPABILITIES (from admin configuration):\n"
        f"  sql      → {sql_short}\n"
        f"  rag      → {rag_short}\n"
        f"  location → {loc_short}\n\n"
        "ORCHESTRATION EXAMPLES:\n"
        "SEQUENTIAL — 'nearest station to my position':\n"
        "  Step 1: sql (get all stations with coordinates)\n"
        "  Step 2: location (find closest from step 1 results)\n\n"
        "SEQUENTIAL — 'recommended oil for top 3 vehicles':\n"
        "  Step 1: sql (get top 3 vehicles)\n"
        "  Step 2: rag (find recommended oil for step 1 results)\n\n"
        "PARALLEL — 'list stations in Casablanca AND price of diesel':\n"
        "  sql (stations list) + sql (diesel prices) → simultaneous\n\n"
        "PARALLEL — 'price of diesel AND recommended oil for my car':\n"
        "  sql (fuel prices) + rag (lubricant specs) → simultaneous\n\n"
        "CRITICAL RULE: location agent ALWAYS needs sql first (sequential). "
        "Never call location alone."
    )


def _build_routing_tools(agent_descriptions: dict) -> list[dict]:
    """
    Construit dynamiquement les outils de routing.

    FIX route_multi : la description est maintenant construite avec
    _build_multi_description() qui injecte les vraies descriptions AdminUI
    dans les exemples d'orchestration. Avant, route_multi avait des exemples
    hardcodés qui ne reflétaient pas le contenu réel des agents.
    """
    tools = []

    # ── route_sql ─────────────────────────────────────────────────────────────
    sql_desc = agent_descriptions.get("sql") or DEFAULT_DESCRIPTIONS["sql"]
    tools.append({
        "type": "function",
        "function": {
            "name": "route_sql",
            "description": sql_desc,
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"},
            }, "required": ["confidence", "reason"]},
        }
    })

    # ── route_rag ─────────────────────────────────────────────────────────────
    rag_desc = agent_descriptions.get("rag") or DEFAULT_DESCRIPTIONS["rag"]
    tools.append({
        "type": "function",
        "function": {
            "name": "route_rag",
            "description": rag_desc,
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"},
            }, "required": ["confidence", "reason"]},
        }
    })

    # ── route_location ────────────────────────────────────────────────────────
    loc_desc = agent_descriptions.get("location") or DEFAULT_DESCRIPTIONS["location"]
    tools.append({
        "type": "function",
        "function": {
            "name": "route_location",
            "description": loc_desc,
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"},
            }, "required": ["confidence", "reason"]},
        }
    })

    # ── route_weather ─────────────────────────────────────────────────────────
    weather_desc = agent_descriptions.get("weather") or DEFAULT_DESCRIPTIONS["weather"]
    tools.append({
        "type": "function",
        "function": {
            "name": "route_weather",
            "description": weather_desc,
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"},
            }, "required": ["confidence", "reason"]},
        }
    })

    # ── route_multi ───────────────────────────────────────────────────────────
    # FIX: description construite dynamiquement avec les descriptions AdminUI
    multi_desc = _build_multi_description(agent_descriptions)
    tools.append({
        "type": "function",
        "function": {
            "name": "route_multi",
            "description": multi_desc,
            "parameters": {
                "type": "object",
                "properties": {
                    "agents": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["sql", "rag", "location", "weather", "dynamic"],
                        },
                        "description": "Ordered list of agents to call",
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["parallel", "sequential"],
                        "description": (
                            "parallel: agents run simultaneously and independently. "
                            "sequential: agent 2 needs agent 1's output."
                        ),
                    },
                    "confidence": {"type": "number"},
                    "reason":     {"type": "string"},
                },
                "required": ["agents", "strategy", "confidence", "reason"],
            },
        }
    })

    # ── route_direct ──────────────────────────────────────────────────────────
    tools.append({
        "type": "function",
        "function": {
            "name": "route_direct",
            "description": _DIRECT_DESCRIPTION,
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"},
            }, "required": ["confidence", "reason"]},
        }
    })

    return tools


TOOL_TO_AGENTS = {
    "route_sql":      ["sql"],
    "route_rag":      ["rag"],
    "route_location": ["location"],
    "route_weather":  ["weather"],
    "route_multi":    None,
    "route_direct":   [],
}

# ── Prompts système selon la langue ──────────────────────────────────────────

_SYSTEM_ROUTER = {
    "fr": (
        "You are a multi-agent routing engine. "
        "Your role is to select the right agent(s) for each user question.\n"
    ),
    "ar": (
        "You are a multi-agent routing engine. "
        "Your role is to select the right agent(s) for each user question.\n"
    ),
    "en": (
        "You are a multi-agent routing engine. "
        "Your role is to select the right agent(s) for each user question.\n"
    ),
}

_ROUTING_RULES = (
    "ABSOLUTE RULE for location questions (nearest station, map, distance):\n"
    "→ ALWAYS use route_multi with agents=[sql, location] and strategy=sequential.\n"
    "→ NEVER call route_location alone: location agent needs SQL station data first.\n\n"
    "IMPORTANT: Simple conversation (greeting, thanks, identity question) → route_direct.\n\n"
    "IMPORTANT for route_multi:\n"
    "- PARALLEL: agents are independent (simultaneous execution).\n"
    "- SEQUENTIAL: agent 2 needs agent 1's result as input.\n"
    "  Example: 'top vehicles and their recommended oil' → sql THEN rag with those names."
)


async def route(
    question:           str,
    session_id:         str | None = None,
    tried:              list[str]  = None,
    session_summary:    str | None = None,
    agent_descriptions: dict[str, str] | None = None,
    language:           str = "fr",
) -> tuple[list[str], float, str, str]:
    """
    Retourne (agents_to_call, confidence, method, strategy).

    FIX language : le paramètre language est maintenant accepté et utilisé
    pour adapter légèrement le système de routing (futur usage).

    FIX route_multi : _build_multi_description() injecte les vraies descriptions
    AdminUI dans les exemples d'orchestration de route_multi, permettant au LLM
    de comprendre concrètement quand orchestrer sql→location, sql→rag, etc.
    """
    tried = tried or []
    agent_descriptions = agent_descriptions or {}

    # ── Session sticky ────────────────────────────────────────────────────────
    if session_id and len(question.split()) <= 4:
        last = get_session_last_agent(session_id)
        if last and last not in tried:
            log.info("Session sticky routing", agent=last)
            return [last], 0.82, "session_sticky", "parallel"

    context = ""
    if tried:
        context = f"\n(Agents already tried — do not retry them: {tried})"

    # ── Bloc mémoire conversationnelle ─────────────────────────────────────────
    memory_context = ""
    if session_summary:
        memory_context = (
            f"\nCONVERSATION CONTEXT:\n{session_summary}\n\n"
            "If the question contains references like 'this station', 'that product', "
            "'its price', 'the same one' — resolve the reference from the context above "
            "before routing.\n"
        )

    # ── Bloc descriptions AdminUI pour le system prompt ───────────────────────
    descriptions_block = ""
    if agent_descriptions:
        lines = []
        for agent, desc in agent_descriptions.items():
            if desc:
                lines.append(f"  {agent.upper()}: {desc[:120]}{'...' if len(desc)>120 else ''}")
        if lines:
            descriptions_block = (
                "\nAGENT CAPABILITIES (configured by admin):\n"
                + "\n".join(lines)
                + "\nUse these descriptions to choose the most relevant agent.\n"
            )

    # ── Construction des tools (route_multi inclut les descriptions) ──────────
    routing_tools = _build_routing_tools(agent_descriptions)

    # ── Message système ────────────────────────────────────────────────────────
    base = _SYSTEM_ROUTER.get(language, _SYSTEM_ROUTER["en"])
    system_content = base + descriptions_block + memory_context + _ROUTING_RULES

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user",   "content": f"Question: {question}{context}"},
    ]

    # ── Appel LLM avec function calling ───────────────────────────────────────
    try:
        message    = await chat_with_tools(LLM_SUPERVISOR, messages, routing_tools)
        tool_calls = message.get("tool_calls", [])

        if tool_calls:
            tc        = tool_calls[0]
            tool_name = tc["function"]["name"]
            args      = tc["function"].get("arguments", {})

            if isinstance(args, str):
                args = json.loads(args)

            confidence = float(args.get("confidence", 0.70))
            reason     = args.get("reason", "")

            if tool_name == "route_multi":
                agents_raw = [a for a in args.get("agents", ["rag"]) if a not in tried]
                seen   = set()
                agents = []
                for a in agents_raw:
                    if a not in seen:
                        seen.add(a)
                        agents.append(a)
                strategy = args.get("strategy", "parallel")
                log.info("Dédoublonnage agents", avant=agents_raw, apres=agents)

            elif tool_name == "route_direct":
                agents   = []
                strategy = "parallel"

            else:
                agents   = [a for a in TOOL_TO_AGENTS.get(tool_name, ["rag"]) if a not in tried]
                strategy = "parallel"

            log.info(
                "LLM routing",
                tool=tool_name,
                agents=agents,
                strategy=strategy,
                confidence=round(confidence, 2),
                reason=reason[:60],
            )
            return agents, confidence, "llm_function_call", strategy

    except Exception as e:
        log.warning("Function calling échoué, fallback JSON", error=str(e))

    # ── Fallback JSON ─────────────────────────────────────────────────────────
    try:
        agents_desc_text = "\n".join(
            f"- {a}: {d[:80]}"
            for a, d in (agent_descriptions or {}).items()
            if d
        ) or "sql, rag, location, weather"

        prompt = f"""You are an agent router. Respond ONLY in valid JSON.

Available agents:
{agents_desc_text}

Question: {question}

If simple conversation: {{"agent": "direct", "confidence": 0.9, "reason": "..."}}
If 1 agent: {{"agent": "sql|rag|location|weather", "confidence": 0.0-1.0, "reason": "..."}}
If multi parallel: {{"agents": ["sql","rag"], "strategy": "parallel", "confidence": 0.0-1.0, "reason": "..."}}
If multi sequential: {{"agents": ["sql","location"], "strategy": "sequential", "confidence": 0.0-1.0, "reason": "..."}}"""

        data = await generate_json(LLM_SUPERVISOR, prompt)

        if data.get("agent") == "direct":
            return [], float(data.get("confidence", 0.9)), "json_direct", "parallel"
        if "agents" in data:
            agents   = [a for a in data["agents"] if a not in tried]
            strategy = data.get("strategy", "parallel")
        else:
            agents   = [data.get("agent", "rag")]
            strategy = "parallel"

        confidence = float(data.get("confidence", 0.60))
        log.info("JSON fallback routing", agents=agents, strategy=strategy)
        return agents, confidence, "llm_json_fallback", strategy

    except Exception as e:
        log.error("Routing total fallback → rag", error=str(e))
        return ["rag"], 0.40, "fallback", "parallel"