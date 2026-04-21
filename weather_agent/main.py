"""
main.py — Weather Agent AKWA
Supporte FR / EN / AR via le paramètre `language`.
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

_REQUIRED = ["OPENWEATHER_API_KEY", "OLLAMA_URL", "REDIS_WEATHER_URL"]
for _var in _REQUIRED:
    if not os.getenv(_var):
        raise RuntimeError(
            f"[WeatherAgent] Variable d'environnement manquante : {_var}\n"
            f"Vérifiez votre fichier .env"
        )

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from intent_parser import parse_intent
from geo_extractor import extract_location
from api_caller import fetch_weather
from response_builder import build_natural_response
import cache


app = FastAPI(
    title="Weather Agent — AKWA",
    description="Microservice météo : OpenWeatherMap + Ollama + Redis — FR/EN/AR",
    version="2.0.0",
)


class WeatherRequest(BaseModel):
    question:   str
    session_id: Optional[str] = None
    language:   Optional[str] = "fr"
    chatbot_id: Optional[str] = ""


class WeatherResponse(BaseModel):
    answer:          str
    weather_data:    dict
    city:            str
    intent:          str
    confidence:      float
    from_cache:      bool
    location_source: str
    agents_used:     list[str]


@app.post("/query", response_model=WeatherResponse)
async def weather_query(req: WeatherRequest):
    language = req.language or "fr"

    try:
        # ── 1. Détecter l'intention et la durée
        parsed = await parse_intent(req.question)  # ✅ CORRECTION
        intent = parsed["intent"]
        days   = parsed["days"]

        # ── 2. Extraire la localisation depuis le texte
        location = await extract_location(req.question)
        lat  = location["lat"]
        lng  = location["lng"]
        city = location["city"]

        # ── 3. Vérifier le cache Redis
        cached = await cache.get(lat, lng, intent, days)
        if cached:
            cached_lang = cached.get("language", "fr")
            if cached_lang == language:
                return WeatherResponse(**{**cached, "from_cache": True})
            else:
                answer = await build_natural_response(
                    weather_data=cached["weather_data"],
                    original_question=req.question,
                    city=city,
                    language=language,
                )
                return WeatherResponse(
                    answer=answer,
                    weather_data=cached["weather_data"],
                    city=city,
                    intent=intent,
                    confidence=0.92,
                    from_cache=True,
                    location_source=location["source"],
                    agents_used=["weather"],
                )

        # ── 4. Appeler l'API OpenWeatherMap
        weather_data = await fetch_weather(lat, lng, intent, days, language=language)

        # ── 5. Générer la réponse naturelle via Ollama
        answer = await build_natural_response(
            weather_data=weather_data,
            original_question=req.question,
            city=city,
            language=language,
        )

        # ── 6. Construire le résultat complet
        result = {
            "answer":          answer,
            "weather_data":    weather_data,
            "city":            city,
            "intent":          intent,
            "confidence":      0.92,
            "from_cache":      False,
            "location_source": location["source"],
            "agents_used":     ["weather"],
            "language":        language,
        }

        # ── 7. Mettre en cache
        await cache.set(lat, lng, intent, days, result)

        return WeatherResponse(**{k: v for k, v in result.items() if k != "language"})

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur OpenWeatherMap : {e.response.status_code} — {e.response.text}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Impossible de joindre OpenWeatherMap : {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status":  "ok",
        "agent":   "weather",
        "version": "2.0.0",
    }