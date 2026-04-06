import json
from app.services.ollama_client import chat_with_tools, generate_json
from app.services.memory import get_session_last_agent
from app.config import LLM_SUPERVISOR, ROUTING_CONFIDENCE_MIN
from app.utils.logger import get_logger

log = get_logger(__name__)

ROUTING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "route_sql",
            "description": (
                "Utilise pour données structurées AKWA : prix carburants, "
                "commandes, stocks, vols, aircraft, livraisons, factures, "
                "rapports chiffrés, historique achats."
            ),
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"}
            }, "required": ["confidence", "reason"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_rag",
            "description": (
                "Utilise pour documentation technique AKWA : normes EN590/EN228, "
                "fiches carburant, propriétés chimiques, sécurité du carburant, "
                "risques, dangers, FAQ, fuel recommandé pour véhicules ou aircraft."
            ),
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"}
            }, "required": ["confidence", "reason"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_location",
            "description": (
                "Utilise pour géolocalisation AKWA : station la plus proche, "
                "carte des stations, distances, itinéraire. "
                "IMPORTANT : ce cas nécessite TOUJOURS route_multi avec strategy=sequential "
                "car les stations doivent d'abord être récupérées via sql, "
                "puis le résultat est passé au location agent."
        ),
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"}
            }, "required": ["confidence", "reason"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_weather",                        
            "description": (
                "Utilise pour toute question météorologique : "
                "température, pluie, vent, prévisions météo, "
                "conditions actuelles ou futures pour une ville ou région."
            ),
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason":     {"type": "string"}
            }, "required": ["confidence", "reason"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_dynamic",
            "description": (
                "Utilise pour tout agent configuré dynamiquement par l'admin : "
                "APIs externes, données cloud, prix personnalisés, sources spécifiques "
                "qui ne correspondent pas aux agents standards."
            ),
            "parameters": {"type": "object", "properties": {
                "agent_key":  { "type": "string",
                                "description": "Clé de l'agent dynamique si connue"},
                "confidence": {"type": "number"},
                "reason":     {"type": "string"}
            }, "required": ["confidence", "reason"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_multi",
            "description": (
                "Utilise quand la question nécessite PLUSIEURS agents. "
                "Détermine si les agents sont PARALLEL (indépendants, appel simultané) "
                "ou SEQUENTIAL (l'un dépend du résultat de l'autre).\n"
                "PARALLEL : 'sécuriser gaz ET nb vols' → rag + sql simultanés.\n"
                "SEQUENTIAL : 'top 3 aircraft puis leur fuel' → sql d'abord, "
                "résultat injecté dans rag ensuite."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agents": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["sql", "rag", "location", "weather", "dynamic"]
                        },
                        "description": "Liste ordonnée des agents à appeler"
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["parallel", "sequential"],
                        "description": (
                            "parallel: agents indépendants. "
                            "sequential: le résultat du 1er agent alimente le 2ème."
                        )
                    },
                    "confidence": {"type": "number"},
                    "reason":     {"type": "string"}
                },
                "required": ["agents", "strategy", "confidence", "reason"]
            }
        }
    },
]

TOOL_TO_AGENTS = {
    "route_sql":      ["sql"],
    "route_rag":      ["rag"],
    "route_location": ["location"],
    "route_weather":  ["weather"],
    "route_multi":    None,
}


async def route(
    question:   str,
    session_id: str | None = None,
    tried:      list[str]  = None,
) -> tuple[list[str], float, str, str]:
    """
    Retourne (agents_to_call, confidence, method, strategy).
    strategy = "parallel" | "sequential"
    """
    tried = tried or []

    # ── Session sticky
    if session_id and len(question.split()) <= 4:
        last = get_session_last_agent(session_id)
        if last and last not in tried:
            log.info("Session sticky routing", agent=last)
            return [last], 0.82, "session_sticky", "parallel"

    context = ""
    if tried:
        context = f"\n(Agents déjà tentés : {tried})"

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es le router d'un orchestrateur multi-agents AKWA (carburant Maroc). "
                "Analyse la question et appelle le tool approprié.\n"
                "RÈGLE ABSOLUE pour les questions de localisation (station proche, carte) :\n"
                "→ Utilise TOUJOURS route_multi avec agents=[sql, location] et strategy=sequential.\n"
                "→ Ne jamais appeler route_location seul : le location agent a besoin des stations SQL.\n"
                "IMPORTANT pour route_multi :\n"
                "- PARALLEL si les agents sont indépendants (peuvent s'exécuter en même temps).\n"
                "- SEQUENTIAL si le résultat du 1er agent est nécessaire pour la question du 2ème.\n"
                "  Ex: 'top 3 aircraft et leur fuel recommandé' → sql PUIS rag avec les noms obtenus."
            )
        },
        {"role": "user", "content": f"Question: {question}{context}"}
    ]

    try:
        message    = await chat_with_tools(LLM_SUPERVISOR, messages, ROUTING_TOOLS)
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
                # Dédoublonner en conservant l'ordre
                seen = set()
                agents = []
                for a in agents_raw:
                    if a not in seen:
                        seen.add(a)
                        agents.append(a)
                strategy = args.get("strategy", "parallel")
                log.info("Dédoublonnage agents", avant=agents_raw, apres=agents)  
            elif tool_name == "route_dynamic":           # ← NOUVEAU BLOC
                agents    = ["dynamic"]
                strategy  = "parallel"
                agent_key = args.get("agent_key", "")
                if agent_key:
                    log.info("Dynamic agent key détecté", agent_key=agent_key) # ← récupéré du LLM
            else:
                agents   = [a for a in TOOL_TO_AGENTS.get(tool_name, ["rag"]) if a not in tried]
                strategy = "parallel"   # 1 seul agent → toujours parallel

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

    # ── Fallback JSON
    try:
        prompt = f"""Tu es un router d'agents. Réponds UNIQUEMENT en JSON valide.

Agents: sql, rag, location, weather
Question: {question}

Si 1 agent:
{{"agent": "sql|rag|location|weather", "confidence": 0.0-1.0, "reason": "..."}}

Si multi-agents parallèles (indépendants):
{{"agents": ["sql","rag"], "strategy": "parallel", "confidence": 0.0-1.0, "reason": "..."}}

Si multi-agents séquentiels (l'un dépend de l'autre):
{{"agents": ["sql","rag"], "strategy": "sequential", "confidence": 0.0-1.0, "reason": "..."}}"""

        data = await generate_json(LLM_SUPERVISOR, prompt)

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