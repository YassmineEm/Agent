"""
vision.py — Module Vision : analyse des éléments visuels dans les documents AKWA

Utilise Qwen2.5-VL via Ollama pour extraire le contenu sémantique des :
  - Graphiques (histogrammes, courbes, camemberts, scatter plots)
  - Schémas techniques (cuves, vannes, circuits, équipements GPL)
  - Tableaux sous forme d'image (non sélectionnables)
  - Figures et infographies

Ce module est appelé par ingestion.py — il ne modifie rien d'autre dans le pipeline.
Le texte produit est traité exactement comme du texte normal :
    chunk → bge-m3 embedding → Qdrant (Dense + BM25)

Architecture :
    VisionAnalyzer           ← singleton, lazy-init
    └── analyze_image()      ← appelé pour chaque image extraite d'un doc
"""

import base64
import asyncio
from typing import Optional

import httpx

from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)

# ── Prompt optimisé pour les documents AKWA Gaz & Carburant ──────────────────
# Objectif : extraire des données précises (valeurs chiffrées, légendes, axes)
# et pas juste une description vague du visuel.
_VISION_PROMPT = """Analyse cette image extraite d'un document technique AKWA (gaz, carburant, GPL, lubrifiants).

Réponds en français. Sois exhaustif et précis.

1. TYPE DE CONTENU : identifie ce que montre l'image (histogramme, courbe, camembert, schéma technique, tableau, photo produit, autre).

2. DONNÉES CHIFFRÉES : si l'image contient des valeurs numériques, des axes, des légendes ou un tableau, retranscris-les fidèlement avec leurs unités. Exemple : "GPL : 46.4 MJ/kg | Gasoil : 42.8 MJ/kg".

3. STRUCTURE / SCHÉMA : si c'est un schéma ou diagramme, décris les composants, leurs relations et les flux (flèches, connexions).

4. TITRE ET LÉGENDES : reproduis exactement le titre du graphique et toutes les légendes visibles.

5. SYNTHÈSE : en 2-3 phrases, explique ce que montre ce visuel et sa conclusion principale.

Si l'image est trop floue, trop petite ou purement décorative, réponds uniquement : "IMAGE_NON_EXPLOITABLE"."""


class VisionAnalyzer:
    """
    Analyseur vision basé sur Qwen2.5-VL via Ollama.
    Singleton chargé à la première utilisation (lazy init).
    """

    def __init__(self):
        self._model = settings.VISION_MODEL
        self._base_url = settings.OLLAMA_BASE_URL
        self._timeout = settings.VISION_TIMEOUT
        self._enabled = settings.VISION_ENABLED
        log.info(
            "VisionAnalyzer initialisé",
            model=self._model,
            enabled=self._enabled,
            timeout=self._timeout,
        )

    async def analyze_image(
        self,
        image_bytes: bytes,
        context: str = "",
    ) -> Optional[str]:
        """
        Analyse une image avec Qwen2.5-VL.

        Args:
            image_bytes : bytes bruts de l'image (PNG, JPG, WEBP…)
            context     : contexte optionnel (ex: "page 3 du fichier fiche_gpl.pdf")

        Returns:
            str  : description structurée extraite par le modèle vision
            None : si vision désactivée, image trop petite, ou erreur Ollama
        """
        if not self._enabled:
            return None

        if len(image_bytes) < settings.VISION_MIN_IMAGE_BYTES:
            log.debug(
                "Image ignorée (trop petite — probablement décorative)",
                size_bytes=len(image_bytes),
                min_bytes=settings.VISION_MIN_IMAGE_BYTES,
            )
            return None

        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        prompt = _VISION_PROMPT
        if context:
            prompt = f"[Contexte : {context}]\n\n{_VISION_PROMPT}"

        payload = {
            "model": self._model,
            "prompt": prompt,
            "images": [b64_image],
            "stream": False,
            "options": {
                "temperature": 0.05,   
                "num_predict": 1024,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                description = response.json().get("response", "").strip()

            if not description or description == "IMAGE_NON_EXPLOITABLE":
                log.debug("Vision : image non exploitable ou réponse vide")
                return None

            log.info(
                "Vision : image analysée",
                model=self._model,
                context=context[:60] if context else "",
                output_chars=len(description),
            )
            return description

        except httpx.TimeoutException:
            log.warning(
                "Vision : timeout Ollama",
                model=self._model,
                timeout=self._timeout,
            )
            return None
        except httpx.HTTPStatusError as e:
            log.warning(
                "Vision : erreur HTTP Ollama",
                status=e.response.status_code,
                model=self._model,
            )
            return None
        except Exception as e:
            log.warning("Vision : erreur inattendue", error=str(e))
            return None

    async def analyze_images_batch(
        self,
        images: list[tuple[bytes, str]],
        max_concurrent: int = 2,
    ) -> list[Optional[str]]:
        """
        Analyse plusieurs images en parallèle (concurrence limitée).

        Args:
            images         : liste de (image_bytes, context_string)
            max_concurrent : nombre d'appels Ollama simultanés (défaut 2 pour ne pas saturer)

        Returns:
            liste de descriptions dans le même ordre que l'entrée
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded(img_bytes: bytes, ctx: str) -> Optional[str]:
            async with semaphore:
                return await self.analyze_image(img_bytes, ctx)

        tasks = [_bounded(img, ctx) for img, ctx in images]
        return await asyncio.gather(*tasks)


# ── Singleton ─────────────────────────────────────────────────────────────────
vision_analyzer = VisionAnalyzer()