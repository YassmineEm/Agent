"""
intent_parser.py — Weather Agent AKWA
Détecte l'intention météo via Ollama (qwen3:8b) + fallback règles si LLM vide.
"""
import os
import json
import re
import httpx
from typing import TypedDict

OLLAMA_URL   = os.getenv("OLLAMA_URL", "https://ollama.mydigiapps.com")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")

CF_ACCESS_CLIENT_ID     = os.getenv("CF_ACCESS_CLIENT_ID", "")
CF_ACCESS_CLIENT_SECRET = os.getenv("CF_ACCESS_CLIENT_SECRET", "")


class ParsedIntent(TypedDict):
    intent: str   # "current" | "forecast" | "alert"
    days: int


def _get_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "CF-Access-Client-Id": CF_ACCESS_CLIENT_ID,
        "CF-Access-Client-Secret": CF_ACCESS_CLIENT_SECRET,
    }


_SYSTEM_PROMPT = """You are a weather intent classifier for a Moroccan fuel company assistant.
Your ONLY job is to return a JSON object — nothing else, no explanation, no markdown.

Rules:
- "intent" must be one of: "current", "forecast", "alert"
- "days" must be an integer between 1 and 7
- Use "current" when the user asks about right now / today / الآن / اليوم
- Use "forecast" when the user asks about tomorrow, next days, next week, a specific day
- Use "alert" when the user mentions storm, flood, danger, warning, cyclone, heatwave, canicule, tempête, فيضان, عاصفة, تحذير
- For "current"  → days = 1
- For "alert"    → days = 1
- For "forecast" → infer days from context:
    - tomorrow / demain / غداً / غدا              → days = 2
    - day after tomorrow / après-demain           → days = 3
    - next week / semaine prochaine / الأسبوع القادم → days = 7
    - default forecast                            → days = 5

EXAMPLES:
"ما هي توقعات الطقس غداً في مراكش؟" → {"intent": "forecast", "days": 2}
"كيف الطقس الآن في الدار البيضاء؟"  → {"intent": "current", "days": 1}
"هل ستمطر خلال 3 أيام؟"             → {"intent": "forecast", "days": 3}
"هل هناك تحذير من عاصفة؟"           → {"intent": "alert", "days": 1}
"Quel temps demain à Casablanca ?"   → {"intent": "forecast", "days": 2}
"Météo maintenant à Rabat ?"         → {"intent": "current", "days": 1}
"Weather today in Agadir?"           → {"intent": "current", "days": 1}
"Forecast for next week in Fes?"     → {"intent": "forecast", "days": 7}

Return ONLY valid JSON — no text before or after:
{"intent": "current", "days": 1}"""


def _parse_json_safe(raw: str) -> "ParsedIntent | None":
    """Extrait le JSON même si le LLM ajoute du texte autour."""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    match = re.search(r"\{[^}]+\}", raw)
    if not match:
        return None

    try:
        data   = json.loads(match.group())
        intent = data.get("intent", "")
        days   = int(data.get("days", 1))

        if intent not in ("current", "forecast", "alert"):
            return None

        return {"intent": intent, "days": max(1, min(days, 7))}

    except (json.JSONDecodeError, ValueError):
        return None


def _rule_based_intent(question: str) -> ParsedIntent:
    """
    Fallback par règles simples si le LLM retourne vide.
    Supporte FR / EN / AR.
    """
    q = question.lower()

    # — ALERT —
    alert_kw = [
        "alerte", "tempête", "inondation", "cyclone", "canicule",
        "danger", "vigilance", "avertissement", "risque",
        "warning", "storm", "flood", "heatwave", "severe",
        "تحذير", "إنذار", "عاصفة", "فيضان", "خطر",
    ]
    if any(k in q for k in alert_kw):
        return {"intent": "alert", "days": 1}

    # — FORECAST —
    if "après-demain" in q or "day after tomorrow" in q:
        return {"intent": "forecast", "days": 3}

    if any(k in q for k in ["semaine prochaine", "next week", "الأسبوع القادم", "la semaine"]):
        return {"intent": "forecast", "days": 7}

    if any(k in q for k in ["demain", "tomorrow", "غداً", "غدا"]):
        return {"intent": "forecast", "days": 2}

    forecast_kw = [
        "prévision", "prévisions", "forecast", "prochains jours",
        "next few days", "coming days", "cette semaine", "this week",
        "weekend", "week-end", "توقعات", "الأيام القادمة",
        "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    ]
    if any(k in q for k in forecast_kw):
        # Chercher un nombre de jours explicite
        m = re.search(r"(\d+)\s*(jours?|days?|أيام)", q)
        days = int(m.group(1)) if m else 5
        return {"intent": "forecast", "days": min(days, 7)}

    # — CURRENT (défaut) —
    return {"intent": "current", "days": 1}


async def parse_intent(question: str) -> ParsedIntent:
    """
    Appelle Ollama (qwen3:8b) pour classifier l'intention météo.
    Si le LLM retourne vide ou échoue → fallback règles (_rule_based_intent).
    """
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": f'{_SYSTEM_PROMPT}\n\nUser question: "{question}"\n\nJSON:',
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 100,
            "num_ctx": 2048,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                headers=_get_headers(),
            )
        r.raise_for_status()

        raw = r.json().get("response", "").strip()
        print(f"[DEBUG INTENT RAW] question='{question}' | raw='{raw}'")

        if not raw:
            result = _rule_based_intent(question)
            print(f"[DEBUG INTENT RULES] {result}")
            return result

        result = _parse_json_safe(raw)
        print(f"[DEBUG INTENT RESULT] {result}")
        return result if result else _rule_based_intent(question)

    except httpx.TimeoutException:
        print("[DEBUG INTENT] Timeout → rules fallback")
        return _rule_based_intent(question)

    except httpx.HTTPStatusError:
        print("[DEBUG INTENT] HTTP error → rules fallback")
        return _rule_based_intent(question)

    except Exception as e:
        print(f"[DEBUG INTENT] Exception: {e} → rules fallback")
        return _rule_based_intent(question)