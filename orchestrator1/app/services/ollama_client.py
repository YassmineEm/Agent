import httpx
import json
from app.config import (
    OLLAMA_URL,
    CF_ACCESS_CLIENT_ID,
    CF_ACCESS_CLIENT_SECRET
)
from app.utils.logger import get_logger

log = get_logger(__name__)


def _get_headers():
    """Headers pour Cloudflare Access"""
    return {
        "Content-Type": "application/json",
        "CF-Access-Client-Id": CF_ACCESS_CLIENT_ID,
        "CF-Access-Client-Secret": CF_ACCESS_CLIENT_SECRET,
    }


async def generate(model: str, prompt: str, timeout: int = 60) -> str:
    """Génération simple — retourne le texte brut."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            headers=_get_headers()   # ✅ AJOUT IMPORTANT
        )
        res.raise_for_status()
        return res.json()["response"]


async def chat_with_tools(
    model: str,
    messages: list[dict],
    tools: list[dict],
    timeout: int = 60,
) -> dict:
    """
    Appel LLM avec function calling via l'API /api/chat d'Ollama.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "tools": tools,
                "stream": False,
            },
            headers=_get_headers() 
        )
        res.raise_for_status()
        data = res.json()
        return data.get("message", {})


async def generate_json(model: str, prompt: str, timeout: int = 60) -> dict:
    """
    Génère une réponse et parse le JSON.
    """
    response_text = await generate(model, prompt, timeout)

    start = response_text.find("{")
    end   = response_text.rfind("}") + 1

    if start == -1 or end <= start:
        raise ValueError(f"Pas de JSON dans la réponse: {response_text[:200]}")

    return json.loads(response_text[start:end])