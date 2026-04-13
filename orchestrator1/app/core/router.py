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
                "Utilise pour les données structurées des stations-service et produits.\n\n"
                "Pour AlloCarburant : stations, prix carburants (gasoil, essence), codes produits, "
                "points de vente lubrifiants, coordonnées GPS.\n\n"
                "Pour AlloGaz : stations GPL, prix du butane/propane, bouteilles de gaz, "
                "points de vente de gaz, livraisons à domicile."
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
                "Utilise pour la documentation technique et produits.\n\n"
                "Pour AlloCarburant : caractéristiques des huiles (Qualix, Mega, Havoline, Delo), "
                "viscosité, spécifications API/ACEA, prix des lubrifiants.\n\n"
                "Pour AlloGaz : sécurité gaz, consignes d'utilisation, stockage bouteilles, "
                "normes de sécurité, précautions d'emploi."
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
                "Utilise pour la géolocalisation.\n\n"
                "Pour AlloCarburant : station la plus proche, calcul de distance, itinéraire.\n\n"
                "Pour AlloGaz : point de vente GPL le plus proche, dépôt de gaz, "
                "distance du client.\n\n"
                "IMPORTANT : nécessite TOUJOURS route_multi avec strategy=sequential "
                "car les données doivent d'abord être récupérées via sql."
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
                "Utilise uniquement pour les questions météorologiques : "
                "température, pluie, vent, prévisions. "
                "Non prioritaire pour AlloCarburant et AlloGaz."
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
            "name": "route_multi",
            "description": (
                "Utilise quand la question nécessite PLUSIEURS agents.\n\n"
                "EXEMPLES POUR ALLOCARBURANT :\n"
                "- SEQUENTIAL : 'Quelle est la station la plus proche et son prix ?' "
                "→ sql (stations) → location (plus proche) → sql (prix)\n"
                "- PARALLEL : 'Liste stations à Casablanca et prix du gasoil' → sql + sql\n\n"
                "EXEMPLES POUR ALLOGAZ :\n"
                "- SEQUENTIAL : 'Où acheter du gaz près de chez moi ?' → sql (points vente) → location\n"
                "- SEQUENTIAL : 'Prix du gaz et sécurité' → sql (prix) → rag (sécurité)\n\n"
                "RÈGLES :\n"
                "- PARALLEL : agents indépendants (ex: stations ET prix)\n"
                "- SEQUENTIAL : résultat du 1er nécessaire au 2ème (ex: trouver point vente → distance)"
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
                            "parallel: agents indépendants (appel simultané). "
                            "sequential: l'ordre d'exécution est important."
                        )
                    },
                    "confidence": {"type": "number"},
                    "reason":     {"type": "string"}
                },
                "required": ["agents", "strategy", "confidence", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_direct",
            "description": (
                "Utilise pour les conversations générales : "
                "salutations, remerciements, présentations, "
                "questions sur l'assistant, ou toute question ne nécessitant "
                "⚠️ Si la question contient des mots comme : carburant, diesel, essence, GPL, "
                "station, prix, lubrifiant, huile, compatible, norme, sécurité → "
                "N'UTILISE JAMAIS route_direct. Utilise route_rag ou route_sql à la place."
            ),
            "parameters": {"type": "object", "properties": {
                "confidence": {"type": "number"},
                "reason": {"type": "string"}
            }, "required": ["confidence", "reason"]}
        }
    },
]

TOOL_TO_AGENTS = {
    "route_sql":      ["sql"],
    "route_rag":      ["rag"],
    "route_location": ["location"],
    "route_weather":  ["weather"],
    "route_multi":    None,
    "route_direct":   [],
}


async def route(
    question:   str,
    session_id: str | None = None,
    tried:      list[str]  = None,
    session_summary: str | None = None,
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

    # ← NOUVEAU : injecter le contexte de session
    memory_context = ""
    if session_summary:
        memory_context = f"""
CONTEXTE DE LA CONVERSATION EN COURS :
{session_summary}

Si la question contient des références comme "cette station", "ce produit", 
"son prix", "celle-là" — résous la référence depuis le contexte ci-dessus 
avant de router.
"""

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es le router d'un orchestrateur multi-agents AKWA (carburant Maroc). "
                "Analyse la question et appelle le tool approprié.\n"
                "RÈGLE ABSOLUE pour les questions de localisation (station proche, carte) :\n"
                "→ Utilise TOUJOURS route_multi avec agents=[sql, location] et strategy=sequential.\n"
                "→ Ne jamais appeler route_location seul : le location agent a besoin des stations SQL.\n"
                "IMPORTANT : Si la question est une simple conversation (salutation, remerciement, présentation, question sur ton identité, etc.), utilise route_direct."
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
            elif tool_name == "route_direct":
                agents = []
                strategy = "parallel"
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

Agents: sql, rag, location, weather, direct (pour réponse directe sans agent)
Question: {question}

Si direct: {{"agent": "direct", "confidence": 0.9, "reason": "conversation simple"}}

Si 1 agent:
{{"agent": "sql|rag|location|weather", "confidence": 0.0-1.0, "reason": "..."}}

Si multi-agents parallèles (indépendants):
{{"agents": ["sql","rag"], "strategy": "parallel", "confidence": 0.0-1.0, "reason": "..."}}

Si multi-agents séquentiels (l'un dépend de l'autre):
{{"agents": ["sql","rag"], "strategy": "sequential", "confidence": 0.0-1.0, "reason": "..."}}"""

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