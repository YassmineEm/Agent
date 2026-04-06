"""
summarizer.py — Gestion du résumé conversationnel AKWA.

Principe : après chaque échange, on génère un résumé court (max 4 phrases)
qui capture les faits utiles pour les échanges futurs. C'est bien plus
efficace que stocker tout l'historique brut.

Stockage : Redis via memory.py
  clé : orch:session:{session_id}:summary
  TTL : 1800s (30 min)
"""
import os
import httpx
from app.utils.logger import get_logger

log = get_logger(__name__)

OLLAMA_URL    = os.getenv("OLLAMA_URL", "http://ollama:11434")
SUMMARY_MODEL = os.getenv("LLM_SUPERVISOR", "qwen3:8b")


async def update_summary(
    existing_summary: str | None,
    user_question:    str,
    assistant_answer: str,
    language:         str = "fr",
) -> str:
    """
    Met à jour le résumé de session après un échange.

    - Si résumé existant = None → crée un premier résumé
    - Si résumé existant présent → l'enrichit avec le nouvel échange
    - Le résumé est TOUJOURS stocké en français (langue interne stable)
    - TTL géré par Redis (30 min d'inactivité = oubli)

    Args:
        existing_summary: résumé précédent ou None
        user_question:    question de l'utilisateur
        assistant_answer: réponse de l'assistant (tronquée à 300 chars)
        language:         langue détectée (pour info seulement)

    Returns:
        Nouveau résumé en français, max 4 phrases
    """
    existing_text = existing_summary or "(no prior context)"

    prompt = f"""Tu es le gestionnaire de mémoire d'un assistant conversationnel AKWA (carburant et gaz, Maroc).
Ton rôle est de maintenir un RÉSUMÉ COURT (maximum 4 phrases) des faits utiles pour les prochaines questions.

CONTEXTE MÉTIER : l'utilisateur interagit avec un chatbot sur les stations-service, les prix du carburant,
la météo, les normes fuel, la géolocalisation des stations AKWA au Maroc.

RÉSUMÉ EXISTANT :
{existing_text}

NOUVEL ÉCHANGE :
Utilisateur : {user_question}
Assistant : {assistant_answer[:400]}

Mets à jour le résumé en intégrant les informations pertinentes.

RÈGLES STRICTES :
- Écris le résumé TOUJOURS en français (langue interne stable)
- Maximum 4 phrases — sois très concis
- Conserve UNIQUEMENT les faits utiles pour de futures questions :
  * Nom de l'utilisateur s'il l'a mentionné
  * Ville / région de l'utilisateur
  * Type de véhicule ou carburant préféré
  * Requêtes récurrentes ou préférences détectées
- N'inclus JAMAIS : prix, températures, données volatiles, formules de politesse
- Si rien de nouveau n'est utile, retourne le résumé existant tel quel
- S'il n'y a aucun contexte antérieur et rien à retenir, retourne une chaîne vide

Résumé mis à jour (en français, max 4 phrases) :"""

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model":  SUMMARY_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 150,
                    },
                },
            )
        r.raise_for_status()
        summary = r.json().get("response", "").strip()

        # Sanity check — ne pas sauvegarder un résumé trop long
        if len(summary) > 500:
            summary = summary[:500]

        log.info(
            "Summary updated",
            length=len(summary),
            has_existing=bool(existing_summary),
        )
        return summary

    except Exception as e:
        log.warning("Summary update failed — keeping existing", error=str(e))
        return existing_summary or ""