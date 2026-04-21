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

    for ans in valid:
        agent     = ans.get("agent", "default")
        threshold = CONFIDENCE_THRESHOLDS.get(agent, CONFIDENCE_THRESHOLDS["default"])
        conf      = float(ans.get("confidence", 0.5))
        if conf >= threshold:
            return "PASS", f"strong_{agent}_{conf:.2f}"

    confidences = [float(a.get("confidence", 0.5)) for a in valid]
    avg = sum(confidences) / len(confidences)
    if avg >= FUSION_CONFIDENCE_MIN:
        return "PASS", f"avg_{avg:.2f}"

    return "UNCERTAIN", f"low_avg_{avg:.2f}"


def _build_scope_block(system_prompt: str | None) -> str:
    """
    Transforme le system_prompt AdminUI en bloc de contrainte de périmètre.

    AVANT (bug) : bot_identity = system_prompt
        → Le LLM de synthèse adoptait le rôle 'spécialisé en lubrifiants'
          et reformulait les données SQL/location pour coller à ce rôle,
          ignorant les vraies données factuelles des agents.

    APRÈS (fix) : le system_prompt devient une CONTRAINTE de périmètre,
        pas une identité. Le LLM reste un synthétiseur neutre qui présente
        les données factuelles des agents, tout en respectant le scope défini.
    """
    if not system_prompt or not system_prompt.strip():
        return ""

    return f"""CHATBOT SCOPE (respect this domain boundary in your answer):
{system_prompt.strip()}

"""


def _build_memory_block(
    session_summary: str | None,
    recent_turns:    list[dict] | None,
) -> str:
    """Construit le bloc mémoire conversationnelle."""
    if not session_summary and not recent_turns:
        return ""

    parts = []
    if session_summary:
        parts.append(f"Session summary:\n{session_summary}")
    if recent_turns:
        turns_text = "\n".join(
            f"- User: {t['q']}\n  Assistant: {t['a'][:150]}"
            for t in (recent_turns or [])[-3:]
        )
        parts.append(f"Recent exchanges:\n{turns_text}")

    block = "\n\n".join(parts)
    return f"""CONVERSATION CONTEXT (use to personalize, resolve references like 'this station', 'that product'):
{block}

"""


async def _translate_if_needed(
    answer:   str,
    language: str,
    agent:    str,
) -> str:
    """
    Traduit la réponse brute d'un agent si la langue ne correspond pas.

    Utilisé uniquement dans le chemin 'PASS direct' (1 seul agent)
    pour garantir que la réponse est dans la bonne langue même si
    l'agent a répondu dans une autre.
    """
    if not answer or not language or language == "fr":
        return answer

    try:
        translated = await generate(
            LLM_VALIDATOR,
            f"""Translate the following text to "{language}".
Return ONLY the translated text, nothing else. No explanation, no preamble.

Text:
{answer}

Translation in {language}:""",
            timeout=30,
        )
        return translated.strip() if translated.strip() else answer
    except Exception as e:
        log.warning("Translation failed — keeping original", agent=agent, error=str(e))
        return answer


async def validate(
    question:        str,
    answers:         list[dict],
    language:        str = "fr",
    session_summary: str | None = None,
    recent_turns:    list[dict] = None,
    system_prompt:   str | None = None,
) -> tuple[str, str, str]:
    """
    Valide et synthétise les réponses des agents.

    Retourne (status, reason, final_answer).
    status = "PASS" | "RETRY" | "CLARIFY"

    Corrections apportées vs version précédente :
    1. system_prompt injecté comme contrainte de périmètre (scope_block)
       et non plus comme persona du LLM synthétiseur.
    2. Codes produits hardcodés supprimés — chaque chatbot a ses propres
       règles métier dans son system_prompt AdminUI.
    3. Traduction de la réponse brute si langue différente (chemin PASS direct).
    4. Instructions au LLM en anglais (plus fiable pour les modèles multilingues),
       seule la réponse finale est forcée dans la langue cible.
    """
    status, reason = _quick_check(answers)
    successful = [a for a in answers if a.get("_success") and a.get("answer")]

    # ── Aucune réponse valide → RETRY ─────────────────────────────────────────
    if status == "RETRY":
        log.info("Validation RETRY (quick check)", reason=reason)
        return "RETRY", reason, ""

    # ── 1 seul agent avec bonne confiance → retour direct ────────────────────
    # FIX: traduire si la langue de l'agent ≠ langue demandée
    if len(successful) == 1 and status == "PASS":
        agent_answer = successful[0]["answer"]
        agent_name   = successful[0]["agent"]
        agent_lang   = successful[0].get("language", language)

        log.info(
            "Validation PASS direct",
            agent=agent_name,
            answer_preview=agent_answer[:100],
        )

        if agent_lang != language and language not in ("fr", "auto"):
            agent_answer = await _translate_if_needed(agent_answer, language, agent_name)

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

    formatted = "\n\n".join(
        f"[{a.get('agent', '?')}]:\n{a.get('answer', '')}"
        for a in successful
        if a.get("answer")
    )

    # ── Blocs contextuels ────────────────────────────────────────────────────
    scope_block  = _build_scope_block(system_prompt)
    memory_block = _build_memory_block(session_summary, recent_turns)

    # ── Synthèse directe si au moins 1 agent fort OU status PASS ─────────────
    if strong or status == "PASS":
        try:
            synthesis = await generate(
                LLM_VALIDATOR,
                f"""Your task: synthesize factual agent data into a clear, direct answer.
CRITICAL: Your response language MUST be "{language}". No other language is acceptable.

{scope_block}{memory_block}Currency: always Moroccan Dirham (DH or MAD), never euros or dollars.

SYNTHESIS RULES:
- Present the agent data FACTUALLY as-is. Do NOT reframe or override it.
- If the data contains station names, prices, distances — state them exactly.
- If the context mentions the user's name, use it naturally.
- Do NOT mention "agents", "sources", "SQL", "RAG", or any technical term.
- Be concise: 2-5 sentences unless listing items requires more.
- Respond ONLY in: {language}

Question: {question}

Agent data:
{formatted}

Answer in {language}:""",
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

    # ── UNCERTAIN : synthèse avec données partielles ──────────────────────────
    if status == "UNCERTAIN":
        try:
            synthesis = await generate(
                LLM_VALIDATOR,
                f"""Your task: synthesize partial agent data into a useful answer.
CRITICAL: Your response language MUST be "{language}".

{scope_block}{memory_block}Currency: always Moroccan Dirham (DH or MAD).

SYNTHESIS RULES:
- Present what is available. If data is partial, say so clearly.
- For stations: give complete names, not abbreviations.
- For prices: use the format "X.XX MAD/L".
- For distances: give name AND distance (e.g. "RAHMA — 6.29 km").
- Do NOT mention technical terms (agents, SQL, RAG, database).
- Respond ONLY in: {language}

Question: {question}

Partial data available:
{formatted}

Answer in {language}:""",
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
    """Génère une question de clarification dans la même langue que la question."""
    try:
        return await generate(
            LLM_VALIDATOR,
            f"""The user asked a vague question to a chatbot.
Generate ONE short clarification question in the SAME LANGUAGE as the user's question.
Return ONLY the clarification question, no preamble, no explanation.

User question: {question}

Clarification question:""",
            timeout=30,
        )
    except Exception:
        return "Pouvez-vous préciser votre demande ?"