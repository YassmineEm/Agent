import re
from typing import TypedDict


class ParsedIntent(TypedDict):
    intent: str  # "current" | "forecast" | "alert"
    days: int


_FORECAST_KEYWORDS_FR = [
    "demain", "après-demain", "semaine", "weekend", "week-end",
    "prochains jours", "prévision", "prévisions",
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
    "cette semaine", "la semaine prochaine",
]

_FORECAST_KEYWORDS_EN = [
    "tomorrow", "day after tomorrow", "next week", "weekend",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "forecast", "next few days", "this week", "coming days",
]

_FORECAST_KEYWORDS_AR = [
    "غداً", "غدا", "الأسبوع", "التوقعات",
    "الأيام القادمة", "نهاية الأسبوع", "الأسبوع القادم",
]

_ALERT_KEYWORDS_FR = [
    "alerte", "danger", "tempête", "cyclone", "inondation",
    "canicule", "vigilance", "avertissement", "orage violent", "risque",
]

_ALERT_KEYWORDS_AR = [
    "تحذير", "إنذار", "عاصفة", "فيضان", "خطر", "إنذار مبكر",
]

_ALERT_KEYWORDS_EN = [
    "alert", "storm", "cyclone", "flood", "heatwave",
    "warning", "danger", "severe", "risk",
]


_ALL_FORECAST = _FORECAST_KEYWORDS_FR + _FORECAST_KEYWORDS_AR + _FORECAST_KEYWORDS_EN
_ALL_ALERT    = _ALERT_KEYWORDS_FR    + _ALERT_KEYWORDS_AR + _ALERT_KEYWORDS_EN


def parse_intent(question: str) -> ParsedIntent:
    q = question.lower().strip()

    # Extraire un nombre de jours explicite si présent ("dans 3 jours")
    days_match = re.search(r"(\d+)\s*jours?", q)
    explicit_days = int(days_match.group(1)) if days_match else None

    # Alerte en priorité absolue
    if any(k in q for k in _ALL_ALERT):
        return {"intent": "alert", "days": 1}

    # Prévision
    if any(k in q for k in _ALL_FORECAST):
        days = min(explicit_days or 5, 7)
        return {"intent": "forecast", "days": days}

    # Défaut : météo actuelle
    return {"intent": "current", "days": 1}