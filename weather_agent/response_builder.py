"""
response_builder.py — Weather Agent AKWA
Génère une réponse naturelle à partir des données météo OWM.
Supporte FR / EN / AR nativement.
"""
import httpx
import os

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "https://displayed-pin-least-preview.trycloudflare.com")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")


def _format_data_block(weather_data: dict, city: str) -> str:
    """Convertit les données brutes en bloc texte lisible pour le prompt."""
    if weather_data["type"] == "current":
        return (
            f"City: {city}\n"
            f"Temperature: {weather_data['temp']}°C "
            f"(feels like {weather_data['feels_like']}°C)\n"
            f"Min / Max: {weather_data['temp_min']}°C / {weather_data['temp_max']}°C\n"
            f"Conditions: {weather_data['description']}\n"
            f"Wind: {weather_data['wind_speed_kmh']} km/h "
            f"direction {weather_data['wind_direction']}\n"
            f"Humidity: {weather_data['humidity']}%\n"
            f"Visibility: {weather_data['visibility_km']} km\n"
            f"Sunrise: {weather_data['sunrise']} — Sunset: {weather_data['sunset']}"
        )

    if weather_data["type"] == "forecast":
        lines = [f"Forecast for {city}:"]
        for d in weather_data.get("days", []):
            lines.append(
                f"  {d['date']}: {d['temp_min']}°C – {d['temp_max']}°C, "
                f"{d['description']}, "
                f"wind {d['wind_speed_kmh']} km/h, "
                f"humidity {d['humidity_avg']}%"
            )
        return "\n".join(lines)

    return str(weather_data)


async def build_natural_response(
    weather_data:      dict,
    original_question: str,
    city:              str,
    language:          str = "fr",          # ← NOUVEAU PARAMÈTRE
) -> str:
    """
    Génère une réponse naturelle via LLM.

    Args:
        weather_data:      données brutes OWM
        original_question: question originale de l'utilisateur
        city:              nom de la ville
        language:          "fr" | "en" | "ar"
    """
    data_block = _format_data_block(weather_data, city)

    # Instruction de langue explicite et non ambiguë
    lang_instruction = {
        "fr": "Réponds UNIQUEMENT en français.",
        "en": "Respond ONLY in English.",
        "ar": "أجب فقط باللغة العربية.",
    }.get(language, "Respond in the same language as the user's question.")

    prompt = f"""You are the weather assistant for the AKWA fuel company customer service (Morocco).

User question: "{original_question}"

Official weather data:
{data_block}

STRICT INSTRUCTIONS:
- {lang_instruction}
- Be concise: 2 to 3 sentences maximum.
- If conditions may affect car travel (heavy rain, dense fog, wind > 60 km/h,
  extreme heat > 40°C), mention it in one short sentence.
- Do NOT invent any data — use ONLY the data provided above.
- Respond DIRECTLY without any introduction phrase ("Sure", "Here is", "Bien sûr", etc.).

Response:"""

    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 250,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        r.raise_for_status()
        return r.json().get("response", "").strip()

    except Exception:
        # Fallback sans LLM si Ollama est indisponible
        return _fallback_response(weather_data, city, language)


def _fallback_response(
    weather_data: dict,
    city:         str,
    language:     str = "fr",          # ← NOUVEAU PARAMÈTRE
) -> str:
    """Réponse formatée directement sans LLM — multilingue."""
    if weather_data["type"] == "current":
        temp = weather_data["temp"]
        desc = weather_data.get("description", "")
        wind = weather_data["wind_speed_kmh"]
        hum  = weather_data["humidity"]

        if language == "ar":
            return (
                f"في {city}، درجة الحرارة الحالية {temp}°C ({desc}). "
                f"سرعة الريح: {wind} كم/س، الرطوبة: {hum}%."
            )
        if language == "en":
            return (
                f"In {city}, the current temperature is {temp}°C ({desc}). "
                f"Wind: {wind} km/h, humidity: {hum}%."
            )
        # Défaut français
        return (
            f"À {city}, il fait actuellement {temp}°C ({desc}). "
            f"Vent : {wind} km/h, humidité : {hum}%."
        )

    days = weather_data.get("days", [])
    if days:
        d = days[0]
        t_min = d["temp_min"]
        t_max = d["temp_max"]
        desc  = d["description"]
        date  = d["date"]

        if language == "ar":
            return (
                f"توقعات الطقس في {city} يوم {date}: "
                f"{t_min}°C إلى {t_max}°C، {desc}."
            )
        if language == "en":
            return (
                f"Forecast for {city} on {date}: "
                f"{t_min}°C to {t_max}°C, {desc}."
            )
        return (
            f"Prévisions pour {city} le {date} : "
            f"{t_min}°C à {t_max}°C, {desc}."
        )

    return city