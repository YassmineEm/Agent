"""
ollama_client.py — Client HTTP personnalisé pour Ollama avec auth Cloudflare

DIAGNOSTIC DES LOGS :
  Le paramètre "think": False dans options{} est ignoré par cette version d'Ollama.
  qwen3:8b retourne uniquement <think>...</think> sans texte après → réponse vide.

SOLUTION APPLIQUÉE :
  1. "think": false placé à la RACINE du payload (pas dans options{}).
     Syntaxe correcte pour Ollama >= 0.7.0 avec qwen3.
     Ref : https://ollama.com/blog/thinking-models
  2. generate_fast() utilise mistral — modèle léger sans mode thinking,
     utilisé pour la détection de langue et la traduction (tâches structurées).
  3. generate() pour la génération RAG finale : qwen3:8b avec think:false racine,
     et fallback automatique sur mistral si réponse toujours vide.
"""
import httpx
import json
import re
from typing import Optional, List
from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)

# Modèle léger sans thinking pour les tâches structurées courtes
FAST_MODEL = "phi4:latest"


def _get_headers() -> dict:
    """Retourne les headers d'authentification Cloudflare."""
    return {
        "Content-Type": "application/json",
        "CF-Access-Client-Id": settings.CF_ACCESS_CLIENT_ID,
        "CF-Access-Client-Secret": settings.CF_ACCESS_CLIENT_SECRET,
    }


def _clean_think_tags(text: str) -> str:
    """
    Supprime les balises <think>...</think> générées par qwen3.
    Gère les blocs vides, non fermés, et imbriqués.
    """
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<think>.*', '', text, flags=re.DOTALL)
    return text.strip()


async def _post_generate(payload: dict, timeout: int) -> str:
    """Appel HTTP bas niveau vers /api/generate. Retourne la réponse brute."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
            headers=_get_headers(),
        )
        response.raise_for_status()
        return response.json().get("response", "")


async def generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 512,
    timeout: int = 60,
) -> str:
    """
    Génération via Ollama avec gestion du mode thinking de qwen3.

    "think": false est placé à la RACINE du payload — c'est la syntaxe
    correcte pour Ollama >= 0.7.0. Le placer dans options{} est ignoré.

    Si réponse toujours vide (serveur ne supporte pas think:false),
    fallback automatique sur FAST_MODEL (mistral).
    """
    model = model or settings.RAG_LLM_MODEL

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,          # RACINE — pas dans options{}
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    raw = await _post_generate(payload, timeout)
    result = _clean_think_tags(raw)

    if result:
        return result

    # Garde-fou : réponse vide → fallback mistral
    log.warning(
        "Réponse vide après think:false — fallback mistral",
        original_model=model,
        prompt_preview=prompt[:80],
    )
    fallback_payload = {
        "model": FAST_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": max(temperature + 0.1, 0.2),
            "num_predict": max_tokens,
        },
    }
    raw_fallback = await _post_generate(fallback_payload, timeout)
    return _clean_think_tags(raw_fallback)


async def generate_fast(
    prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 200,
    timeout: int = 25,
) -> str:
    """
    Génération rapide avec mistral — sans mode thinking.
    À utiliser pour : détection de langue, traduction, toute tâche
    structurée courte qui doit retourner un mot ou un JSON simple.
    mistral répond directement sans <think>, fiable et rapide.
    """
    payload = {
        "model": FAST_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    raw = await _post_generate(payload, timeout)
    result = _clean_think_tags(raw)

    if not result:
        log.warning(
            "generate_fast : réponse vide",
            model=FAST_MODEL,
            prompt_preview=prompt[:80],
        )
    return result


async def generate_json(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    timeout: int = 60,
) -> dict:
    """
    Génération avec retour JSON garanti.
    Sans modèle spécifié : utilise generate_fast (mistral) — plus fiable pour JSON.
    """
    if model is None:
        response_text = await generate_fast(
            prompt, temperature=temperature, max_tokens=300, timeout=timeout
        )
    else:
        response_text = await generate(
            prompt, model=model, temperature=temperature, timeout=timeout
        )

    response_text = re.sub(r'```[a-z]*\s*', '', response_text)
    response_text = re.sub(r'```\s*', '', response_text)
    response_text = response_text.strip()

    start = response_text.find("{")
    end = response_text.rfind("}") + 1

    if start == -1 or end <= start:
        log.warning(
            "Pas de JSON trouvé dans generate_json",
            response_preview=response_text[:200],
        )
        return {}

    try:
        return json.loads(response_text[start:end])
    except json.JSONDecodeError as e:
        log.error("Erreur parsing JSON dans generate_json", error=str(e))
        return {}


async def chat_with_messages(
    messages: List[dict],
    model: Optional[str] = None,
    temperature: float = 0.1,
    timeout: int = 60,
) -> str:
    """Chat avec historique de messages via /api/chat."""
    model = model or settings.RAG_LLM_MODEL

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json=payload,
            headers=_get_headers(),
        )
        response.raise_for_status()
        data = response.json()

    result = data.get("message", {}).get("content", "")
    return _clean_think_tags(result)