"""
ingestion.py — Pipeline d'ingestion des documents AKWA

Formats supportés :
    PDF, DOCX/DOC, CSV, XLSX/XLS, TXT, JSON, Markdown

CHUNKING INTELLIGENT (nouveau) :
    Le splitter détecte automatiquement si un fichier texte contient des blocs
    structurés séparés par des lignes répétitives (====, ----, ***...).
    Si oui → chaque bloc est traité comme unité sémantique autonome.
    Si un bloc dépasse CHUNK_SIZE → il est découpé EN CONSERVANT le titre du
    bloc en tête de chaque sous-chunk (préfixe contexte).
    Cela garantit que "Prix : 183.33 MAD" reste associé à "Qualix 10W40 5L"
    même si le bloc fait 1335 chars et CHUNK_SIZE = 512.

    Ce mécanisme est générique : il fonctionne pour n'importe quel fichier
    structuré (fiches produits, FAQ, documentation technique, etc.)
    sans nécessiter de reformatage manuel.

    Pour les fichiers non structurés (prose continue) → fallback sur
    RecursiveCharacterTextSplitter standard.

ANALYSE VISION (Qwen2.5-VL) :
    PDF et DOCX avec images embarquées → description ajoutée comme chunk visuel.
"""

import io
import os
import re
import json
import asyncio
import tempfile
from enum import Enum
from typing import List, Optional

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import settings
from app.logger import get_logger
from app.vision import vision_analyzer

log = get_logger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".csv", ".xlsx", ".xls",
    ".txt", ".json", ".md",
}


class FileType(str, Enum):
    PDF      = "pdf"
    DOCX     = "docx"
    CSV      = "csv"
    EXCEL    = "excel"
    TXT      = "txt"
    JSON     = "json"
    MARKDOWN = "markdown"


def detect_file_type(filename: str) -> FileType:
    ext = os.path.splitext(filename.lower())[1]
    mapping = {
        ".pdf":  FileType.PDF,
        ".docx": FileType.DOCX,
        ".doc":  FileType.DOCX,
        ".csv":  FileType.CSV,
        ".xlsx": FileType.EXCEL,
        ".xls":  FileType.EXCEL,
        ".txt":  FileType.TXT,
        ".json": FileType.JSON,
        ".md":   FileType.MARKDOWN,
    }
    if ext not in mapping:
        raise ValueError(
            f"Format non supporté : '{filename}'. "
            f"Acceptés : {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return mapping[ext]


# ══════════════════════════════════════════════════════════════════════════════
# CHUNKING INTELLIGENT — générique, sans reformatage manuel
# ══════════════════════════════════════════════════════════════════════════════

def _detect_block_separator(text: str) -> Optional[str]:
    """
    Détecte si le texte contient des séparateurs de blocs structurels
    (lignes composées d'un seul caractère répété : ====, ----, ****, etc.)

    Retourne le pattern regex du séparateur si trouvé avec ≥ 3 occurrences,
    sinon None (→ fallback sur splitter standard).

    Exemples détectés :
        "================" → pattern r'\n=====+\n'
        "----------------" → pattern r'\n-----+\n'
        "****************" → pattern r'\n\*\*\*\*\*+\n'
    """
    lines = text.split('\n')
    counts: dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        # Ligne structurelle : ≥ 10 chars, un seul caractère unique
        if len(stripped) >= 10 and len(set(stripped)) == 1:
            char = re.escape(stripped[0])
            pattern = rf'\n{char}{{5,}}\n'
            counts[pattern] = counts.get(pattern, 0) + 1

    if not counts:
        return None

    best_pattern = max(counts, key=counts.get)
    if counts[best_pattern] >= 3:
        log.debug(
            "Séparateur structurel détecté",
            pattern=best_pattern,
            occurrences=counts[best_pattern],
        )
        return best_pattern

    return None


def _extract_block_title(block: str) -> str:
    """
    Extrait la première ligne significative d'un bloc comme titre de contexte.
    Ignore les séparateurs (----) et les lignes vides.

    Exemple : "PRODUIT : Afriquia Qualix 10W40 5L               "
          → "PRODUIT : Afriquia Qualix 10W40 5L"
    """
    for line in block.strip().split('\n'):
        stripped = line.strip()
        # Ignorer lignes vides, séparateurs, et lignes trop courtes
        if stripped and len(set(stripped)) > 1 and len(stripped) > 3:
            return stripped[:120]
    return ""


def _smart_chunk_block(
    block: str,
    title: str,
    chunk_size: int,
    overlap: int,
) -> List[str]:
    """
    Découpe un bloc en chunks en CONSERVANT le titre (contexte) en tête
    de chaque sous-chunk.

    Logique :
    - Si le bloc tient dans chunk_size → 1 seul chunk (cas idéal)
    - Sinon → découpe ligne par ligne avec :
        * Préfixe "[Contexte: <titre>]" sur chaque sous-chunk
        * Overlap sur le texte précédent pour la continuité sémantique

    Garantit que le nom du produit/section reste toujours présent dans
    chaque chunk même si le prix est sur la dernière ligne du bloc.
    """
    block = block.strip()

    if len(block) <= chunk_size:
        return [block]

    # Le bloc est trop grand → découpage avec répétition du contexte
    title_prefix = f"[Contexte: {title}]\n" if title else ""
    lines = block.split('\n')
    chunks: List[str] = []
    current = title_prefix

    for line in lines:
        candidate = current + line + '\n'
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            # Sauvegarder le chunk courant s'il a du contenu réel
            content_only = current[len(title_prefix):].strip()
            if content_only:
                chunks.append(current.strip())

            # Nouveau chunk : titre + overlap du chunk précédent
            if overlap > 0 and len(current) > len(title_prefix):
                overlap_text = current[len(title_prefix):][-overlap:]
            else:
                overlap_text = ""

            current = title_prefix + overlap_text + line + '\n'

    # Dernier chunk
    content_only = current[len(title_prefix):].strip()
    if content_only:
        chunks.append(current.strip())

    return chunks if chunks else [block[:chunk_size]]


def _smart_split_text(
    text: str,
    filename: str,
    chunk_size: int,
    overlap: int,
) -> List[str]:
    """
    Splitter intelligent en 2 niveaux :

    Niveau 1 — Détection de structure :
        Si le texte contient des séparateurs répétitifs (====, ----...)
        → découper par ces séparateurs naturels (1 bloc = 1 entité sémantique)

    Niveau 2 — Découpage des blocs trop grands :
        Si un bloc > chunk_size → _smart_chunk_block() avec répétition du titre

    Fallback — Pas de structure détectée :
        → RecursiveCharacterTextSplitter standard (comportement original)
    """
    separator = _detect_block_separator(text)

    if separator:
        # ── Chemin structuré : blocs autonomes ───────────────────────────────
        raw_blocks = re.split(separator, text)
        blocks = [b.strip() for b in raw_blocks if b.strip()]

        log.info(
            "Chunking structuré activé",
            filename=filename,
            nb_blocks=len(blocks),
            separator=separator,
        )

        all_chunks: List[str] = []
        for block in blocks:
            title = _extract_block_title(block)
            chunks = _smart_chunk_block(block, title, chunk_size, overlap)
            all_chunks.extend(chunks)
            log.debug(
                "Bloc découpé",
                title=title[:60],
                nb_chunks=len(chunks),
                block_size=len(block),
            )

        log.info(
            "Chunking structuré terminé",
            filename=filename,
            total_chunks=len(all_chunks),
        )
        return all_chunks

    else:
        # ── Fallback : splitter standard RecursiveCharacterTextSplitter ──────
        log.info(
            "Chunking standard activé (pas de structure détectée)",
            filename=filename,
        )
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
        )
        return splitter.split_text(text)


def _split_documents_smart(
    docs: List[Document],
    filename: str,
    chunk_size: int,
    overlap: int,
) -> List[Document]:
    """
    Applique _smart_split_text sur chaque Document et retourne
    une liste de Documents avec métadonnées préservées.
    """
    result: List[Document] = []
    for doc in docs:
        text_chunks = _smart_split_text(
            doc.page_content, filename, chunk_size, overlap
        )
        for chunk_text in text_chunks:
            result.append(Document(
                page_content=chunk_text,
                metadata=dict(doc.metadata),
            ))
    return result


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE D'INGESTION
# ══════════════════════════════════════════════════════════════════════════════

class DocumentIngestion:

    # ── Loaders texte (inchangés) ─────────────────────────────────────────────

    def _load_pdf(self, tmp_path: str, filename: str) -> List[Document]:
        from langchain_community.document_loaders import PyPDFLoader
        docs = PyPDFLoader(tmp_path).load()
        for doc in docs:
            doc.metadata["filename"]     = filename
            doc.metadata["content_type"] = "text"
        return docs

    def _load_docx(self, tmp_path: str, filename: str) -> List[Document]:
        from langchain_community.document_loaders import Docx2txtLoader
        docs = Docx2txtLoader(tmp_path).load()
        for doc in docs:
            doc.metadata["filename"]     = filename
            doc.metadata["content_type"] = "text"
        return docs

    def _load_txt(self, tmp_path: str, filename: str) -> List[Document]:
        from langchain_community.document_loaders import TextLoader
        docs = TextLoader(tmp_path, encoding="utf-8").load()
        for doc in docs:
            doc.metadata["filename"]     = filename
            doc.metadata["content_type"] = "text"
        return docs

    def _load_markdown(self, tmp_path: str, filename: str) -> List[Document]:
        from langchain_community.document_loaders import TextLoader
        docs = TextLoader(tmp_path, encoding="utf-8").load()
        for doc in docs:
            doc.metadata["filename"]     = filename
            doc.metadata["content_type"] = "text"
        return docs

    def _load_csv(self, tmp_path: str, filename: str) -> List[Document]:
        import csv
        docs = []
        with open(tmp_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
                if text.strip():
                    docs.append(Document(
                        page_content=text,
                        metadata={
                            "source":       filename,
                            "filename":     filename,
                            "row":          i,
                            "content_type": "text",
                        },
                    ))
        return docs

    def _load_excel_openpyxl(self, tmp_path: str, filename: str) -> List[Document]:
        import openpyxl
        wb = openpyxl.load_workbook(tmp_path, read_only=True, data_only=True)
        docs = []
        for sheet in wb.worksheets:
            headers = None
            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                if i == 0:
                    headers = [
                        str(c) if c is not None else f"col{j}"
                        for j, c in enumerate(row)
                    ]
                    continue
                if all(c is None for c in row):
                    continue
                parts = [
                    f"{headers[j]}: {c}"
                    for j, c in enumerate(row)
                    if c is not None
                ]
                if parts:
                    docs.append(Document(
                        page_content=" | ".join(parts),
                        metadata={
                            "source":       filename,
                            "filename":     filename,
                            "sheet":        sheet.title,
                            "row":          i,
                            "content_type": "text",
                        },
                    ))
        wb.close()
        return docs

    def _load_json(self, tmp_path: str, filename: str) -> List[Document]:
        with open(tmp_path, encoding="utf-8") as f:
            data = json.load(f)
        docs = []
        if isinstance(data, list):
            for i, item in enumerate(data):
                docs.append(Document(
                    page_content=json.dumps(item, ensure_ascii=False),
                    metadata={
                        "source":       filename,
                        "filename":     filename,
                        "index":        i,
                        "content_type": "text",
                    },
                ))
        else:
            docs.append(Document(
                page_content=json.dumps(data, ensure_ascii=False),
                metadata={
                    "source":       filename,
                    "filename":     filename,
                    "content_type": "text",
                },
            ))
        return docs

    # ── Extraction visuelle (inchangée) ───────────────────────────────────────

    async def _extract_visual_chunks_from_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
    ) -> List[Document]:
        if not settings.VISION_ENABLED:
            return []
        try:
            import fitz
        except ImportError:
            log.warning("PyMuPDF non installé — extraction visuelle PDF désactivée.")
            return []

        images_to_analyze: List[tuple] = []
        try:
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                for img_info in page.get_images(full=True):
                    xref = img_info[0]
                    try:
                        base_image = pdf.extract_image(xref)
                        img_bytes  = base_image["image"]
                        if len(img_bytes) < settings.VISION_MIN_IMAGE_BYTES:
                            continue
                        context = f"page {page_num + 1} — {filename}"
                        images_to_analyze.append((img_bytes, context))
                    except Exception as e:
                        log.debug("Image PDF non extractible", page=page_num + 1, error=str(e))
            pdf.close()
        except Exception as e:
            log.warning("Erreur ouverture PDF pour extraction visuelle", filename=filename, error=str(e))
            return []

        if not images_to_analyze:
            return []

        log.info("Vision PDF : images détectées", filename=filename, count=len(images_to_analyze))
        descriptions = await vision_analyzer.analyze_images_batch(images_to_analyze)

        visual_docs = []
        for (_, context), description in zip(images_to_analyze, descriptions):
            if not description:
                continue
            page_num_str = context.split("—")[0].strip()
            try:
                page_num = int(page_num_str.replace("page", "").strip())
            except ValueError:
                page_num = 0
            visual_docs.append(Document(
                page_content=f"[Figure {page_num_str} — source: {filename}]\n{description}",
                metadata={
                    "source":       filename,
                    "filename":     filename,
                    "doc_type":     doc_type,
                    "content_type": "visual",
                    "page":         page_num,
                    "vision_model": settings.VISION_MODEL,
                },
            ))

        log.info("Vision PDF : chunks visuels créés", filename=filename, chunks_created=len(visual_docs))
        return visual_docs

    async def _extract_visual_chunks_from_docx(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
    ) -> List[Document]:
        if not settings.VISION_ENABLED:
            return []
        import zipfile

        images_to_analyze: List[tuple] = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                media_files = [
                    name for name in zf.namelist()
                    if name.startswith("word/media/")
                    and os.path.splitext(name.lower())[1]
                    in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
                ]
                for i, media_path in enumerate(media_files):
                    img_bytes = zf.read(media_path)
                    if len(img_bytes) < settings.VISION_MIN_IMAGE_BYTES:
                        continue
                    context = f"figure {i + 1} — {filename}"
                    images_to_analyze.append((img_bytes, context))
        except Exception as e:
            log.warning("Erreur extraction images DOCX", filename=filename, error=str(e))
            return []

        if not images_to_analyze:
            return []

        log.info("Vision DOCX : images détectées", filename=filename, count=len(images_to_analyze))
        descriptions = await vision_analyzer.analyze_images_batch(images_to_analyze)

        visual_docs = []
        for (_, context), description in zip(images_to_analyze, descriptions):
            if not description:
                continue
            visual_docs.append(Document(
                page_content=f"[{context.capitalize()} — source: {filename}]\n{description}",
                metadata={
                    "source":       filename,
                    "filename":     filename,
                    "doc_type":     doc_type,
                    "content_type": "visual",
                    "page":         1,
                    "vision_model": settings.VISION_MODEL,
                },
            ))

        log.info("Vision DOCX : chunks visuels créés", filename=filename, chunks_created=len(visual_docs))
        return visual_docs

    # ── Pipeline principal ────────────────────────────────────────────────────

    async def ingest_file(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
        collection: str,
        description: str = "",
    ) -> dict:
        """
        Point d'entrée unique — signature inchangée.

        Étapes :
            1. Détection du type de fichier
            2. Extraction texte via loaders LangChain
            3. Extraction visuelle (PDF/DOCX uniquement)
            4. Chunking intelligent (structuré ou standard selon le fichier)
            5. Enrichissement métadonnées
            6. Indexation Qdrant
        """
        from app.qdrant_store import qdrant_store

        file_type = detect_file_type(filename)
        log.info(
            "Ingestion démarrée",
            filename=filename,
            file_type=file_type,
            doc_type=doc_type,
            collection=collection,
        )

        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            # ── Extraction texte ──────────────────────────────────────────────
            text_docs: List[Document] = []

            if file_type == FileType.PDF:
                text_docs = self._load_pdf(tmp_path, filename)
            elif file_type == FileType.DOCX:
                text_docs = self._load_docx(tmp_path, filename)
            elif file_type == FileType.CSV:
                text_docs = self._load_csv(tmp_path, filename)
            elif file_type == FileType.EXCEL:
                text_docs = self._load_excel_openpyxl(tmp_path, filename)
            elif file_type == FileType.TXT:
                text_docs = self._load_txt(tmp_path, filename)
            elif file_type == FileType.JSON:
                text_docs = self._load_json(tmp_path, filename)
            elif file_type == FileType.MARKDOWN:
                text_docs = self._load_markdown(tmp_path, filename)

            # ── Extraction visuelle ───────────────────────────────────────────
            visual_docs: List[Document] = []

            if file_type == FileType.PDF:
                visual_docs = await self._extract_visual_chunks_from_pdf(
                    file_bytes, filename, doc_type
                )
            elif file_type == FileType.DOCX:
                visual_docs = await self._extract_visual_chunks_from_docx(
                    file_bytes, filename, doc_type
                )

        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        all_docs = text_docs + visual_docs

        if not all_docs:
            raise ValueError(
                f"Aucun contenu extrait de '{filename}'. "
                "Vérifiez que le fichier n'est pas vide ou corrompu."
            )

        # ── Chunking ──────────────────────────────────────────────────────────
        chunked_docs: List[Document] = []

        for doc in all_docs:
            if doc.metadata.get("content_type") == "visual":
                # Chunks visuels : pas de re-split, enrichissement métadonnées seul
                doc.metadata.update({
                    "doc_type":    doc_type,
                    "filename":    filename,
                    "description": description,
                })
                chunked_docs.append(doc)
            else:
                # Chunks texte : chunking intelligent (structuré ou standard)
                smart_chunks = _split_documents_smart(
                    [doc],
                    filename=filename,
                    chunk_size=settings.CHUNK_SIZE,
                    overlap=settings.CHUNK_OVERLAP,
                )
                for chunk in smart_chunks:
                    chunk.metadata.update({
                        "doc_type":     doc_type,
                        "filename":     filename,
                        "description":  description,
                        "content_type": chunk.metadata.get("content_type", "text"),
                    })
                    chunked_docs.append(chunk)

        if not chunked_docs:
            raise ValueError(f"Aucun chunk produit pour '{filename}'.")

        # ── Indexation Qdrant ─────────────────────────────────────────────────
        indexed_count = qdrant_store.add_documents(collection, chunked_docs)

        text_count   = sum(1 for d in chunked_docs if d.metadata.get("content_type") != "visual")
        visual_count = sum(1 for d in chunked_docs if d.metadata.get("content_type") == "visual")

        log.info(
            "Ingestion terminée",
            filename=filename,
            collection=collection,
            total_chunks=indexed_count,
            text_chunks=text_count,
            visual_chunks=visual_count,
        )

        return {
            "status":         "success",
            "filename":       filename,
            "doc_type":       doc_type,
            "collection":     collection,
            "chunks_indexed": indexed_count,
            "text_chunks":    text_count,
            "visual_chunks":  visual_count,
        }

    async def ingest_multiple_files(
        self,
        files: List[tuple],
        collection: str,
    ) -> dict:
        """Ingère plusieurs fichiers en parallèle (max 3 simultanés)."""
        log.info("Ingestion batch démarrée", total=len(files), collection=collection)
        semaphore = asyncio.Semaphore(3)

        async def process_file(file_bytes, filename, doc_type, description):
            async with semaphore:
                return await self.ingest_file(
                    file_bytes=file_bytes,
                    filename=filename,
                    doc_type=doc_type,
                    collection=collection,
                    description=description,
                )

        tasks = [
            process_file(fb, fn, dt, desc)
            for fb, fn, dt, desc in files
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        succeeded, failed = [], []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed.append({"filename": files[i][1], "error": str(result)})
            else:
                succeeded.append(result)

        log.info(
            "Ingestion batch terminée",
            total=len(files),
            succeeded=len(succeeded),
            failed=len(failed),
        )

        return {
            "status":      "completed",
            "total_files": len(files),
            "succeeded":   len(succeeded),
            "failed":      len(failed),
            "results":     succeeded,
            "errors":      failed,
        }


# Singleton
ingestion = DocumentIngestion()