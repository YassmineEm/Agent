"""
service.py — Location Agent AKWA
Calcule la station la plus proche et génère une réponse multilingue (FR/EN/AR).
"""
from typing import Optional, List
from app.utils import haversine
from app.models import Station

# ── Messages multilingues ─────────────────────────────────────────────────────
_MESSAGES = {
    "invalid_coords": {
        "fr": "Impossible de déterminer votre position. Veuillez activer la géolocalisation ou préciser une adresse.",
        "en": "Unable to determine your position. Please enable geolocation or specify an address.",
        "ar": "تعذّر تحديد موقعك. يرجى تفعيل خدمة تحديد الموقع أو تحديد عنوان.",
    },
    "empty": {
        "fr": "Aucune station n'a été transmise. Vérifiez que l'agent SQL a bien retourné des stations.",
        "en": "No station was provided. Please check that the SQL agent returned stations correctly.",
        "ar": "لم يتم تمرير أي محطة . يرجى التحقق من أن وكيل SQL قد أعاد المحطات بشكل صحيح.",
    },
    "too_far": {
        "fr": "La station la plus proche est '{name}' mais elle se trouve à {dist} km — trop éloignée de votre position ({lat}, {lng}).",
        "en": "The nearest station is '{name}' but it is {dist} km away — too far from your position ({lat}, {lng}).",
        "ar": "أقرب محطة هي '{name}' لكنها تبعد {dist} كم — بعيدة جداً عن موقعك ({lat}, {lng}).",
    },
    "ok": {
        "fr": "La station la plus proche est '{name}'{address_part}, à {dist} km de votre position{fuel_part}. {total} station(s) disponible(s) au total.",
        "en": "The nearest station is '{name}'{address_part}, {dist} km from your position{fuel_part}. {total} station(s) available in total.",
        "ar": "أقرب محطة هي '{name}'{address_part}، على بُعد {dist} كم من موقعك{fuel_part}. إجمالي المحطات المتاحة: {total}.",
    },
}

_FUEL_LABEL = {
    "fr": "carburant",
    "en": "fuel",
    "ar": "الوقود",
}

_ADDRESS_SEP = {
    "fr": ", ",
    "en": ", ",
    "ar": "، ",
}

MAX_DISTANCE_KM = 100


def _get_message(key: str, language: str, **kwargs) -> str:
    """Retourne le message dans la bonne langue avec substitution des variables."""
    lang = language.lower()[:2]
    if lang not in ("fr", "en", "ar"):
        lang = "fr"
    template = _MESSAGES.get(key, {}).get(lang, _MESSAGES[key]["fr"])
    return template.format(**kwargs)


def find_nearest(
    user_lat: float,
    user_lng: float,
    stations: List[Station],
) -> tuple[Optional[Station], Optional[float], str]:
    """
    Trouve la station la plus proche.
    Retourne (station, distance_km, status) avec status = "ok" | "empty" | "too_far" | "invalid_coords".
    """
    if user_lat == 0.0 and user_lng == 0.0:
        return None, None, "invalid_coords"
    if not stations:
        return None, None, "empty"

    nearest = None
    min_dist = float("inf")
    for s in stations:
        dist = haversine(user_lat, user_lng, s.lat, s.lng)
        if dist < min_dist:
            min_dist = dist
            nearest = s

    if min_dist > MAX_DISTANCE_KM:
        return nearest, round(min_dist, 2), "too_far"
    return nearest, round(min_dist, 2), "ok"


def rank_all_stations(
    user_lat: float,
    user_lng: float,
    stations: List[Station],
) -> List[dict]:
    """Retourne toutes les stations triées par distance croissante."""
    ranked = []
    for s in stations:
        dist = haversine(user_lat, user_lng, s.lat, s.lng)
        ranked.append({
            "name": s.name,
            "lat": s.lat,
            "lng": s.lng,
            "address": s.address or "",
            "fuel_type": s.fuel_type or "",
            "distance_km": round(dist, 2),
        })
    ranked.sort(key=lambda x: x["distance_km"])
    return ranked


def build_response(
    user_lat: float,
    user_lng: float,
    stations: List[Station],
    language: str = "fr",
) -> dict:
    """
    Point d'entrée principal.
    Construit la réponse complète du location agent.
    """
    nearest, dist, status = find_nearest(user_lat, user_lng, stations)
    all_ranked = rank_all_stations(user_lat, user_lng, stations) if stations else []

    # Cas 1 : coordonnées invalides
    if status == "invalid_coords":
        return {
            "answer": _get_message("invalid_coords", language),
            "confidence": 0.1,
            "station": None,
            "distance_km": None,
            "all_stations": [],
            "error": "invalid_coords",
        }

    # Cas 2 : aucune station
    if status == "empty":
        return {
            "answer": _get_message("empty", language),
            "confidence": 0.2,
            "station": None,
            "distance_km": None,
            "all_stations": [],
            "error": "no_stations_provided",
        }

    # Cas 3 : station trop loin
    if status == "too_far":
        answer = _get_message("too_far", language,
                              name=nearest.name,
                              dist=dist,
                              lat=user_lat,
                              lng=user_lng)
        return {
            "answer": answer,
            "confidence": 0.4,
            "station": nearest,
            "distance_km": dist,
            "all_stations": all_ranked,
            "error": "station_too_far",
        }

    # Cas normal : station trouvée dans le rayon acceptable
    sep = _ADDRESS_SEP.get(language[:2], ", ")
    fuel_label = _FUEL_LABEL.get(language[:2], "fuel")
    address_part = f"{sep}{nearest.address}" if nearest.address else ""
    fuel_part = f" ({fuel_label}: {nearest.fuel_type})" if nearest.fuel_type else ""

    answer = _get_message("ok", language,
                        name=nearest.name,
                        address_part=address_part,
                        dist=dist,
                        fuel_part=fuel_part,
                        total=len(all_ranked))

    return {
        "answer": answer,
        "confidence": 0.95,
        "station": nearest,
        "distance_km": dist,
        "all_stations": all_ranked,
        "error": None,
    }