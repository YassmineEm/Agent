import json
from app.services.ollama_client import generate_json
from app.config import LLM_SUPERVISOR, AGENT_URLS
from app.utils.logger import get_logger

log = get_logger(__name__)


async def build_plan(
    question: str,
    agents:   list[str],
    strategy: str = "parallel",
) -> dict:
    """
    Construit le plan d'exécution.

    Retourne toujours ce format :
    {
        "strategy": "parallel" | "sequential",
        "steps": [...]
    }

    Parallel  → steps = [{"sql": "q1", "rag": "q2"}]          1 step avec N agents
    Sequential → steps = [{"sql": "q1"}, {"rag": "q2 {sql_result}"}]  N steps d'1 agent

    Cas 1 agent multi-questions → steps = [{"rag": "q1"}, {"rag": "q2"}]  N steps même agent
    """

    # ── 1 seul agent ──────────────────────────────────────────────────────────
    # Ancien comportement : retour immédiat sans décomposition (court-circuit)
    # Nouveau comportement : on demande au LLM si la question est composée,
    # et on crée autant de steps que de sous-questions détectées.
    if len(agents) == 1:
        agent = agents[0]
        try:
            prompt = f"""Analyse si cette question contient plusieurs sous-questions INDÉPENDANTES.
Si oui, décompose-la en sous-questions séparées, chacune complète et autonome.
Si non (1 seule question), retourne-la telle quelle dans un tableau à 1 élément.
Réponds UNIQUEMENT en JSON valide, sans explication ni markdown.

Question : {question}

Format si 1 question :
{{
  "strategy": "parallel",
  "steps": [{{"{agent}": "question telle quelle"}}]
}}

Format si 2 sous-questions ou plus :
{{
  "strategy": "parallel",
  "steps": [
    {{"{agent}": "première sous-question complète"}},
    {{"{agent}": "deuxième sous-question complète"}}
  ]
}}

RÈGLES STRICTES :
- La clé de chaque step doit être EXACTEMENT : "{agent}"
- Chaque sous-question doit être autonome et compréhensible seule
- Ne combine JAMAIS deux sujets différents dans le même step
- Si la question ne contient qu'un seul sujet, 1 seul step suffit

Question à analyser : {question}"""

            data  = await generate_json(LLM_SUPERVISOR, prompt, timeout=30)
            steps = data.get("steps", [])

            # ── Garde-fou : vérifier que les clés sont bien le bon agent ──────
            if steps:
                validated_steps = []
                for step in steps:
                    clean_step = {}
                    for key, val in step.items():
                        if key == agent:
                            clean_step[key] = val
                        else:
                            log.warning(
                                "Planner single-agent : clé inattendue ignorée",
                                expected=agent,
                                got=key,
                            )
                    if clean_step:
                        validated_steps.append(clean_step)

                if not validated_steps:
                    log.warning(
                        "Planner single-agent : validation échouée — fallback trivial",
                        original_steps=steps,
                    )
                    validated_steps = [{agent: question}]

                steps = validated_steps
            else:
                steps = [{agent: question}]

            nb_steps = len(steps)
            log.info(
                "Plan single-agent construit",
                agent=agent,
                nb_steps=nb_steps,
                sub_questions={
                    list(s.values())[0][:50]: list(s.keys())[0]
                    for s in steps
                },
            )
            return {"strategy": "parallel", "steps": steps}

        except Exception as e:
            log.warning(
                "Plan single-agent fallback — question envoyée telle quelle",
                agent=agent,
                error=str(e),
            )
            return {
                "strategy": "parallel",
                "steps":    [{agent: question}]
            }

    # ── Multi-agents ──────────────────────────────────────────────────────────

    descriptions = {
        "sql":      "données chiffrées (prix, commandes, stocks, vols, aircraft)",
        "rag":      "documentation technique (normes, fiches, fuel recommandé)",
        "location": "géolocalisation (stations, carte, distances)",
        "weather":  "météo (température, pluie, vent, prévisions)",
        "dynamic":  "agent dynamique configuré par l'admin (API externe, données cloud)",
    }
    agents_desc = "\n".join(f"- {a}: {descriptions.get(a, a)}" for a in agents)

    if strategy == "parallel":
        try:
            agents_str     = ", ".join(f'"{a}"' for a in agents)
            agents_example = "\n".join(
                f'      "{a}": "sous-question ciblée et complète pour {a}"'
                for a in agents
            )

            prompt = f"""Décompose cette question en sous-questions INDÉPENDANTES.
Chaque agent travaille en parallèle sans connaître les résultats des autres.
Réponds UNIQUEMENT en JSON valide.

Agents disponibles:
{agents_desc}

Question: {question}

RÈGLE CRITIQUE : les clés du JSON doivent être EXACTEMENT les noms des agents : {agents_str}
N'utilise JAMAIS "agent1", "agent2", "agent3" ou tout autre nom inventé.
Si plusieurs sous-questions concernent le même agent, combine-les en une seule sous-question pour cet agent.

Format attendu (1 seul step avec tous les agents):
{{
  "strategy": "parallel",
  "steps": [
    {{
{agents_example}
    }}
  ]
}}

Agents à inclure obligatoirement: {agents_str}"""

            data  = await generate_json(LLM_SUPERVISOR, prompt)
            log.info("Plan brut LLM", data=data)
            steps = data.get("steps", [])

            # ── Garde-fou : vérifier que les clés sont bien des agents connus ──
            if steps:
                validated_steps = []
                for step in steps:
                    clean_step = {}
                    for key, val in step.items():
                        if key in AGENT_URLS:
                            clean_step[key] = val
                        else:
                            log.warning(
                                "Planner a utilisé un nom d'agent invalide — ignoré",
                                invalid_key=key,
                                valid_agents=list(AGENT_URLS.keys()),
                            )
                    if clean_step:
                        validated_steps.append(clean_step)

                if not validated_steps:
                    log.warning(
                        "Toutes les clés du plan étaient invalides — fallback",
                        original_steps=steps,
                    )
                    steps = [{agent: question for agent in agents}]
                else:
                    steps = validated_steps

            if not steps:
                steps = [{agent: question for agent in agents}]

            log.info(
                "Plan parallel construit",
                agents=agents,
                sub_questions={
                    k: v[:40]
                    for step in steps
                    for k, v in step.items()
                },
            )
            return {"strategy": "parallel", "steps": steps}

        except Exception as e:
            log.warning("Plan parallel fallback", error=str(e))
            return {
                "strategy": "parallel",
                "steps":    [{agent: question for agent in agents}]
            }

    else:
        # strategy == "sequential"
        try:
            prompt = f"""Décompose cette question en étapes SÉQUENTIELLES ordonnées.
Le résultat de chaque étape est injecté dans la suivante via {{agent_result}}.
Réponds UNIQUEMENT en JSON valide.

Agents (dans l'ordre d'exécution):
{agents_desc}

Question: {question}

RÈGLES:
- Chaque step contient UN SEUL agent.
- Les clés doivent être EXACTEMENT les noms des agents (sql, rag, location, weather).
- Si l'étape 2 utilise le résultat de l'étape 1, écris {{sql_result}}, {{rag_result}}, etc.
- L'ordre des steps = ordre d'exécution.

Exemples :

1. Pour "top 3 aircraft et leur fuel recommandé":
{{
  "strategy": "sequential",
  "steps": [
    {{"sql": "List the top 3 aircraft by number of flights"}},
    {{"rag": "What is the recommended fuel for these aircraft: {{sql_result}}"}}
  ]
}}

2. Pour un scénario de localisation :
{{
  "strategy": "sequential",
  "steps": [
    {{"sql": "Liste toutes les stations AKWA avec nom, latitude et longitude"}},
    {{"location": "Station la plus proche du client parmi : {{sql_result}}"}}
  ]
}}

Question à décomposer: {question}
Agents dans l'ordre: {agents}"""

            data  = await generate_json(LLM_SUPERVISOR, prompt)
            log.info("Plan brut LLM", data=data)
            steps = data.get("steps", [])

            if not steps:
                steps = [{agent: question} for agent in agents]

            log.info(
                "Plan sequential construit",
                steps_count=len(steps),
                agents_order=[list(s.keys())[0] for s in steps],
            )
            return {"strategy": "sequential", "steps": steps}

        except Exception as e:
            log.warning("Plan sequential fallback", error=str(e))
            return {
                "strategy": "sequential",
                "steps":    [{agent: question} for agent in agents]
            }