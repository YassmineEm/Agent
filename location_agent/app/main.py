from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import LocationRequest, LocationResponse
from app.service import build_response

app = FastAPI(
    title="AKWA Location Agent",
    description="Service de calcul de proximité géographique",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/query", response_model=LocationResponse)
def query(req: LocationRequest):
    """
    Endpoint principal — compatible avec l'orchestrateur AKWA.

    Reçoit :
    - lat / lng     : position GPS du client (depuis navigator.geolocation)
    - stations      : liste des stations (depuis SQL agent)
    - question      : question originale (optionnel, pour logging)
    - chatbot_id    : identifiant du chatbot (optionnel)

    Cas gérés :
    - stations vide         → message explicite
    - coordonnées (0,0)     → message d'erreur GPS
    - station trop loin     → avertissement distance
    - cas normal            → station la plus proche + classement
    """
    result = build_response(req.lat, req.lng, req.stations, language=req.language or "fr",)
    return LocationResponse(**result)



@app.get("/health")
def health():
    return {
        "status":  "healthy",
        "agent":   "location",
        "version": "1.0.0",
    }