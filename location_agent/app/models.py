from pydantic import BaseModel, validator
from typing import List, Optional


class Station(BaseModel):
    name: str
    lat: float
    lng: float
    address: Optional[str] = ""
    fuel_type: Optional[str] = ""


class LocationRequest(BaseModel):
    lat: float
    lng: float
    stations: List[Station] = []
    question: Optional[str] = ""        # ← question libre depuis orchestrateur
    chatbot_id: Optional[str] = ""
    language:   Optional[str] = "fr"

    @validator("lat")
    def validate_lat(cls, v):
        if not (-90 <= v <= 90):
            raise ValueError(f"Latitude invalide: {v}. Doit être entre -90 et 90.")
        return v

    @validator("lng")
    def validate_lng(cls, v):
        if not (-180 <= v <= 180):
            raise ValueError(f"Longitude invalide: {v}. Doit être entre -180 et 180.")
        return v


class LocationResponse(BaseModel):
    answer: str                         # ← texte lisible pour l'orchestrateur
    confidence: float
    station: Optional[Station] = None
    distance_km: Optional[float] = None
    all_stations: Optional[List[dict]] = []
    error: Optional[str] = None