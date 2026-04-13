from app.services.ollama_client import generate_json, generate
from app.config import LLM_VALIDATOR, FUSION_CONFIDENCE_MIN
from app.utils.logger import get_logger

log = get_logger(__name__)

MIN_ANSWER_LENGTH = 15

CONFIDENCE_THRESHOLDS = {
    "rag":      0.40,
    "sql":      0.70,
    "location": 0.50,
    "weather":  0.60,
    "dynamic":  0.50,
    "default":  0.50,
}


def _quick_check(answers: list[dict]) -> tuple[str, str]:
    """Validation rapide sans LLM."""
    successful = [a for a in answers if a.get("_success") and a.get("answer")]

    if not successful:
        return "RETRY", "no_successful_answer"

    valid = [
        a for a in successful
        if len(str(a.get("answer", ""))) >= MIN_ANSWER_LENGTH
    ]
    if not valid:
        return "RETRY", "answers_too_short"

    # Au moins 1 agent fort → PASS immédiat
    for ans in valid:
        agent     = ans.get("agent", "default")
        threshold = CONFIDENCE_THRESHOLDS.get(agent, CONFIDENCE_THRESHOLDS["default"])
        conf      = float(ans.get("confidence", 0.5))
        if conf >= threshold:
            return "PASS", f"strong_{agent}_{conf:.2f}"

    # Tous faibles mais réponses présentes → on tente quand même
    confidences = [float(a.get("confidence", 0.5)) for a in valid]
    avg = sum(confidences) / len(confidences)
    if avg >= FUSION_CONFIDENCE_MIN:
        return "PASS", f"avg_{avg:.2f}"

    return "UNCERTAIN", f"low_avg_{avg:.2f}"


async def validate(question: str, answers: list[dict], language: str = "fr", session_summary: str | None = None, recent_turns: list[dict] = None) -> tuple[str, str, str]:
    """
    Valide et synthétise les réponses des agents.
    Retourne (status, reason, final_answer).
    status = "PASS" | "RETRY" | "CLARIFY"
    """
    status, reason = _quick_check(answers)
    successful = [a for a in answers if a.get("_success") and a.get("answer")]

    # ── Aucune réponse valide → RETRY ─────────────────────────────────────────
    if status == "RETRY":
        log.info("Validation RETRY (quick check)", reason=reason)
        return "RETRY", reason, ""

    # ── 1 seul agent avec bonne confiance → retour direct SANS LLM ───────────
    if len(successful) == 1 and status == "PASS":
        agent_answer = successful[0]["answer"]
        agent_name   = successful[0]["agent"]
        log.info("Validation PASS direct", agent=agent_name)

        # Force le passage par LLM pour traduire les codes produits
        try:
            translated = await generate(
                LLM_VALIDATOR,
                f"""Réécris la réponse suivante en remplaçant TOUS les codes produits par leurs noms.

Règles de traduction OBLIGATOIRES :
- 11011001 → Gazole B7
- 11052001 → SP95
- 11054001 → SP98
- 11191001 → E10
- 15011001 → GPL

Réponse originale :
{agent_answer}

Réponse corrigée (uniquement avec les noms, jamais les codes) :""",
                timeout=30,
            )
            log.info("Traduction codes produits réussie", agent=agent_name)
            return "PASS", reason, translated
        except Exception as e:
            log.warning("Traduction codes échouée, réponse brute", error=str(e))
            return "PASS", reason, agent_answer

    # ── Multi-agent : identifier les agents forts ─────────────────────────────
    strong = [
        a for a in successful
        if float(a.get("confidence", 0)) >= CONFIDENCE_THRESHOLDS.get(
            a.get("agent", "default"), CONFIDENCE_THRESHOLDS["default"]
        )
    ]

    log.info(
        "Validation multi-agent",
        agents=[a.get("agent") for a in successful],
        strong_count=len(strong),
        status=status,
    )

    # Formater les réponses pour la synthèse
    formatted = "\n\n".join(
        f"[{a.get('agent', '?')}]:\n{a.get('answer', '')}"
        for a in successful
        if a.get("answer")
    )

    memory_block = ""
    if session_summary:
        memory_block = f"""CONVERSATION CONTEXT (use this to personalize your answer):
        {session_summary}
        """
    if recent_turns:
        turns_text = "\n".join(
            f"- Utilisateur: {t['q']}\n  Assistant: {t['a']}"
            for t in recent_turns[-3:]   # les 3 derniers suffisent
        )
        memory_block += f"\nÉCHANGES RÉCENTS :\n{turns_text}\n"

    if memory_block:
        memory_block = f"""CONTEXTE DE CONVERSATION (utilise-le pour personnaliser la réponse) :
{memory_block}
"""

    # ── Synthèse directe si au moins 1 agent fort OU status PASS ─────────────
    if strong or status == "PASS":
        try:
            synthesis = await generate(
                LLM_VALIDATOR,
                f"""IMPORTANT: You MUST respond in this language: "{language}"

## RÈGLES IMPORTANTES POUR LES PRODUITS :
- Ne JAMAIS afficher les codes produits (ex: 11011001)
- Utilise TOUJOURS les noms des produits :
  * 11011001 → Gazole B7
  * 11052001 → SP95
  * 11054001 → SP98
  * 11191001 → E10
  * 15011001 → GPL

{memory_block}
You are an AKWA assistant (Morocco fuel company).
Currency is always Moroccan Dirham (DH or MAD), never euros or dollars.

Synthesise the following information to answer the question directly.

Question: {question}

Available information:
{formatted}

INSTRUCTIONS:
- If the conversation context mentions the user's name, use it naturally.
- Combine all information to answer the question directly.
- Do NOT mention "agents" or "sources".
- Your response language MUST be: {language}
- NEVER show product codes, only product names.

Answer:""",
                timeout=90,
            )

            log.info(
                "Synthèse directe réussie",
                answer_length=len(synthesis),
                strong_agents=[a.get("agent") for a in strong],
            )
            return "PASS", "direct_synthesis", synthesis

        except Exception as e:
            log.warning("Synthèse directe échouée — fallback concat", error=str(e))
            fallback = "\n\n".join(
                f"{a.get('agent', '?').upper()}: {a.get('answer', '')}"
                for a in successful
            )
            return "PASS", "fallback_concat", fallback

    # ── UNCERTAIN : tenter une synthèse même avec faible confiance ───────────
    if status == "UNCERTAIN":
        try:
            synthesis = await generate(
                LLM_VALIDATOR,
                f"""IMPORTANT: You MUST respond in this language: "{language}"

## RÈGLES STRICTES POUR ALLOCARBURANT

1. **Pour lister les stations par ville** : Donne les NOMS COMPLETS des stations.
   Exemple: "Les stations à Casablanca sont RAHMA et GHANDI."

2. **Pour le nombre de stations** : Indique le nombre ET liste les noms.
   Exemple: "Il y a 4 stations à Agadir : BAB DOUKKALA, HAY MOHAMMADI, RIAD, YASMINE."

3. **Pour les produits** : Utilise les NOMS, jamais les codes.
   - 11011001 → Gazole B7
   - 11052001 → SP95
   - 11054001 → SP98
   - 11191001 → E10
   - 15011001 → GPL

4. **Pour les prix** : Utilise le format "X.XX MAD/L"
   Exemple: "Le prix du gazole à la station AL AMAL est de 11.01 MAD/L."

5. **Pour la station la plus proche** : Donne le nom ET la distance.
   Exemple: "La station la plus proche est RAHMA à 6.29 km."

{memory_block}
           
Question: {question}

Informations partielles disponibles:
{formatted}

Synthétise ces informations même si incomplètes. Indique ce qui est disponible et ce qui manque si nécessaire.
Réponds dans la langue: {language}
N'utilise JAMAIS de codes produits (11011001, 11052001, etc.). Utilise toujours les noms comme indiqué ci-dessus.""",
                timeout=60,
            )
            log.info("Synthèse UNCERTAIN réussie", answer_length=len(synthesis))
            return "PASS", "uncertain_synthesis", synthesis

        except Exception as e:
            log.warning("Synthèse UNCERTAIN échouée", error=str(e))

    # ── Fallback ultime : meilleure réponse disponible ────────────────────────
    if successful:
        best = max(successful, key=lambda a: float(a.get("confidence", 0)))
        log.info("Fallback best agent", agent=best.get("agent"))
        return "PASS", "fallback_best", best["answer"]

    return "RETRY", "no_valid_answer", ""


async def ask_clarification(question: str) -> str:
    """Génère une question de clarification pour l'utilisateur."""
    try:
        return await generate(
            LLM_VALIDATOR,
            f"""L'utilisateur a posé une question vague à un chatbot AKWA (carburant Maroc).
Génère UNE question de clarification courte et la même langue que la question de l'utilisateur.

Question vague: {question}

Retourne uniquement la question de clarification, sans autre texte.""",
            timeout=30,
        )
    except Exception:
        return "Pouvez-vous préciser votre demande ?"