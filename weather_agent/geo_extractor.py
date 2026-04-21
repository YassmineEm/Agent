import httpx
import os
import re
from typing import Optional, TypedDict

OWM_KEY = os.getenv("OPENWEATHER_API_KEY")


class Location(TypedDict):
    city: str
    lat: float
    lng: float
    source: str  



MAROC_CITIES: dict[str, tuple[float, float]] = {
    "casablanca":   (33.5731, -7.5898),
    "rabat":        (34.0209, -6.8416),
    "marrakech":    (31.6295, -7.9811),
    "marrakesh":    (31.6295, -7.9811),
    "fès":          (34.0333, -5.0000),
    "fes":          (34.0333, -5.0000),
    "agadir":       (30.4278, -9.5981),
    "tanger":       (35.7595, -5.8340),
    "meknès":       (33.8935, -5.5473),
    "meknes":       (33.8935, -5.5473),
    "oujda":        (34.6867, -1.9114),
    "kenitra":      (34.2610, -6.5802),
    "tétouan":      (35.5785, -5.3684),
    "tetouan":      (35.5785, -5.3684),
    "safi":         (32.2994, -9.2372),
    "el jadida":    (33.2316, -8.5007),
    "settat":       (33.0007, -7.6164),
    "beni mellal":  (32.3373, -6.3498),
    "nador":        (35.1681, -2.9286),
    "taza":         (34.2100, -4.0100),
    "essaouira":    (31.5084, -9.7595),
    "laayoune":     (27.1418, -13.1800),
    # Arabe
    "الدار البيضاء": (33.5731, -7.5898),
    "الرباط":        (34.0209, -6.8416),
    "مراكش":         (31.6295, -7.9811),
    "فاس":           (34.0333, -5.0000),
    "أكادير":        (30.4278, -9.5981),
    "طنجة":          (35.7595, -5.8340),
    "مكناس":         (33.8935, -5.5473),
    "وجدة":          (34.6867, -1.9114),
}

# Patterns regex pour extraire une ville candidate du texte libre
_CITY_PATTERNS = [
    # "météo à Casablanca" / "température de Rabat"
    r"(?:météo|temps|température|climat|pluie|soleil)\s+(?:à|de|au|sur|dans?)\s+([A-Za-zÀ-ÿ\s\-]+?)(?:\s*\?|$|\s+(?:demain|aujourd|maintenant|ce soir|cette|pour|prévision))",
    # "à Marrakech" en général
    r"\b(?:à|au|de|sur)\s+([A-Z][a-zà-ÿ\-]+(?:\s+[A-Z][a-zà-ÿ\-]+)?)\b",
    # Arabe : "في الدار البيضاء"
    r"(?:في|بـ|ب)\s+([\u0600-\u06FF\s]+?)(?:\s*\?|$)",
]

_GENERIC_WORDS = {
    "maroc", "morocco", "المغرب", "ville", "région", "pays",
    "monde", "france", "europe", "afrique",
}


async def extract_location(question: str) -> Location:
    q_lower = question.lower().strip()

    # 1. Dictionnaire local — O(n) mais n petit, < 1ms
    for city_key, (lat, lng) in MAROC_CITIES.items():
        if city_key in q_lower:
            return {
                "city": _capitalize_city(city_key),
                "lat": lat,
                "lng": lng,
                "source": "local",
            }

    # 2. Extraction regex + géocodage OWM
    candidate = _extract_city_candidate(question)
    if candidate:
        result = await _geocode_with_owm(candidate)
        if result:
            return result

    # 3. Fallback : Casablanca (siège Afriquia)
    return {
        "city": "Casablanca",
        "lat": 33.5731,
        "lng": -7.5898,
        "source": "default",
    }


def _capitalize_city(name: str) -> str:
    return " ".join(w.capitalize() for w in name.split())


def _extract_city_candidate(text: str) -> Optional[str]:
    for pattern in _CITY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
        if match:
            candidate = match.group(1).strip()
            if candidate.lower() not in _GENERIC_WORDS and len(candidate) >= 2:
                return candidate
    return None


async def _geocode_with_owm(city: str) -> Optional[Location]:
    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": f"{city},MA",
        "limit": 1,
        "appid": OWM_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, params=params)
        data = r.json()
        if data and isinstance(data, list) and len(data) > 0:
            item = data[0]
            local_names = item.get("local_names", {})
            city_name = (
                local_names.get("fr")
                or local_names.get("ar")
                or item.get("name", city)
            )
            return {
                "city": city_name,
                "lat": item["lat"],
                "lng": item["lon"],
                "source": "owm_geocoding",
            }
    except Exception:
        pass
    return None