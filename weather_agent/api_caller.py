import httpx
import os
from datetime import datetime, timezone


OWM_KEY  = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"


ICON_LABELS: dict[str, str] = {
    "01d": "ensoleillé",       "01n": "ciel dégagé",
    "02d": "peu nuageux",      "02n": "peu nuageux",
    "03d": "nuageux",          "03n": "nuageux",
    "04d": "très nuageux",     "04n": "très nuageux",
    "09d": "averses",          "09n": "averses",
    "10d": "pluie",            "10n": "pluie",
    "11d": "orage",            "11n": "orage",
    "13d": "neige",            "13n": "neige",
    "50d": "brouillard",       "50n": "brouillard",
}


async def fetch_weather(
    lat: float,
    lng: float,
    intent: str,
    days: int,
    language: str = "fr"          # ← NOUVEAU PARAMÈTRE
) -> dict:
    if intent == "current":
        return await _fetch_current(lat, lng, language)
    else:
        return await _fetch_forecast(lat, lng, days, language)


async def _fetch_current(lat: float, lng: float, language: str = "fr") -> dict:
    # OWM supporte nativement "fr", "en", "ar"
    owm_lang = language if language in ("fr", "en", "ar") else "fr"
    params = {
        "lat":   lat,
        "lon":   lng,
        "appid": OWM_KEY,
        "units": "metric",
        "lang":  owm_lang,        # ← était "fr" en dur
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{BASE_URL}/weather", params=params)
    r.raise_for_status()
    d = r.json()

    icon_code = d["weather"][0]["icon"]

    return {
        "type":          "current",
        "city":          d.get("name", ""),
        "country":       d.get("sys", {}).get("country", "MA"),
        "temp":          round(d["main"]["temp"],       1),
        "feels_like":    round(d["main"]["feels_like"], 1),
        "temp_min":      round(d["main"]["temp_min"],   1),
        "temp_max":      round(d["main"]["temp_max"],   1),
        "humidity":      d["main"]["humidity"],
        "pressure":      d["main"]["pressure"],
        "description":   d["weather"][0]["description"],
        "icon":          icon_code,
        "icon_label":    ICON_LABELS.get(icon_code, d["weather"][0]["description"]),
        "wind_speed_kmh": round(d["wind"]["speed"] * 3.6, 1),
        "wind_direction": _deg_to_direction(d["wind"].get("deg", 0)),
        "visibility_km": round(d.get("visibility", 10000) / 1000, 1),
        "clouds_pct":    d.get("clouds", {}).get("all", 0),
        "sunrise":       _ts_to_hhmm(d["sys"]["sunrise"]),
        "sunset":        _ts_to_hhmm(d["sys"]["sunset"]),
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


async def _fetch_forecast(
    lat: float,
    lng: float,
    days: int,
    language: str = "fr"          # ← NOUVEAU PARAMÈTRE
) -> dict:
    owm_lang = language if language in ("fr", "en", "ar") else "fr"
    params = {
        "lat":   lat,
        "lon":   lng,
        "appid": OWM_KEY,
        "units": "metric",
        "lang":  owm_lang,        # ← était "fr" en dur
        "cnt":   min(days * 8, 40),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{BASE_URL}/forecast", params=params)
    r.raise_for_status()
    d = r.json()

    # Agréger les créneaux de 3h par jour calendaire
    days_map: dict[str, dict] = {}
    for item in d.get("list", []):
        date = item["dt_txt"][:10]
        if date not in days_map:
            days_map[date] = {
                "temps":       [],
                "descriptions": [],
                "icons":       [],
                "wind_speeds": [],
                "humidities":  [],
            }
        days_map[date]["temps"].append(item["main"]["temp"])
        days_map[date]["descriptions"].append(item["weather"][0]["description"])
        days_map[date]["icons"].append(item["weather"][0]["icon"])
        days_map[date]["wind_speeds"].append(item["wind"]["speed"])
        days_map[date]["humidities"].append(item["main"]["humidity"])

    forecast_days = []
    for date, vals in list(days_map.items())[:days]:
        dominant_desc = max(set(vals["descriptions"]), key=vals["descriptions"].count)
        dominant_icon = max(set(vals["icons"]),        key=vals["icons"].count)
        forecast_days.append({
            "date":           date,
            "temp_min":       round(min(vals["temps"]), 1),
            "temp_max":       round(max(vals["temps"]), 1),
            "description":    dominant_desc,
            "icon":           dominant_icon,
            "icon_label":     ICON_LABELS.get(dominant_icon, dominant_desc),
            "wind_speed_kmh": round(max(vals["wind_speeds"]) * 3.6, 1),
            "humidity_avg":   round(sum(vals["humidities"]) / len(vals["humidities"])),
        })

    return {
        "type":      "forecast",
        "city":      d.get("city", {}).get("name", ""),
        "days":      forecast_days,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _deg_to_direction(deg: float) -> str:
    directions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    return directions[round(deg / 45) % 8]


def _ts_to_hhmm(ts: int) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%H:%M")