"""
ingestion.py — Pipeline d'ingestion des documents AKWA

Formats supportés (INCHANGÉS) :
    PDF, DOCX/DOC, CSV, XLSX/XLS, TXT, JSON, Markdown

NOUVEAU — Analyse vision (Qwen2.5-VL) :
    Quand un PDF ou un DOCX contient des images embarquées (graphiques, schémas,
    figures, tableaux sous forme d'image), chaque image est extraite puis analysée
    par Qwen2.5-VL. La description produite est ajoutée comme chunk supplémentaire
    dans Qdrant — en plus des chunks texte, jamais à la place.

    Le pipeline textuel existant est conservé à l'identique :
        - Mêmes loaders LangChain (PyPDFLoader, Docx2txtLoader, TextLoader…)
        - Même splitter RecursiveCharacterTextSplitter (512 tokens, overlap 64)
        - Même interface ingest_file() appelée par main.py

    Les chunks visuels passent par le même pipeline d'embedding :
        bge-m3 (dense 1024d) + BM25 (sparse) → Qdrant akwa_knowledge

    Formats avec extraction visuelle :
        PDF  → PyMuPDF extrait les images page par page
        DOCX → extraction ZIP depuis word/media/

    Formats sans extraction visuelle (pas d'images embarquées possibles) :
        CSV, XLSX, TXT, JSON, Markdown → pipeline texte seul, inchangé
"""

import io
import os
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

# ── Extensions supportées (INCHANGÉES) ───────────────────────────────────────
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
    """
    Retourne le FileType correspondant à l'extension.
    Lève ValueError si le format n'est pas supporté.
    """
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


# ── Splitter partagé (INCHANGÉ) ───────────────────────────────────────────────
def _make_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
    )


class DocumentIngestion:
    """
    Pipeline d'ingestion complet.

    Méthodes publiques :
        ingest_file()              ← appelé par main.py (signature inchangée)

    Méthodes privées texte (ORIGINALES — loaders LangChain conservés) :
        _load_pdf()
        _load_docx()
        _load_txt()
        _load_markdown()
        _load_csv()
        _load_excel_openpyxl()
        _load_json()

    Méthodes privées vision (NOUVELLES) :
        _extract_visual_chunks_from_pdf()
        _extract_visual_chunks_from_docx()
    """

    # ══════════════════════════════════════════════════════════════════════════
    # LOADERS TEXTE — ORIGINAUX (loaders LangChain conservés à l'identique)
    # ══════════════════════════════════════════════════════════════════════════

    def _load_pdf(self, tmp_path: str, filename: str) -> List[Document]:
        """Extrait le texte sélectionnable via PyPDFLoader (LangChain)."""
        from langchain_community.document_loaders import PyPDFLoader
        docs = PyPDFLoader(tmp_path).load()
        for doc in docs:
            doc.metadata["filename"]     = filename
            doc.metadata["content_type"] = "text"
        return docs

    def _load_docx(self, tmp_path: str, filename: str) -> List[Document]:
        """Extrait le texte via Docx2txtLoader (LangChain)."""
        from langchain_community.document_loaders import Docx2txtLoader
        docs = Docx2txtLoader(tmp_path).load()
        for doc in docs:
            doc.metadata["filename"]     = filename
            doc.metadata["content_type"] = "text"
        return docs

    def _load_txt(self, tmp_path: str, filename: str) -> List[Document]:
        """Charge un fichier texte brut via TextLoader (LangChain)."""
        from langchain_community.document_loaders import TextLoader
        docs = TextLoader(tmp_path, encoding="utf-8").load()
        for doc in docs:
            doc.metadata["filename"]     = filename
            doc.metadata["content_type"] = "text"
        return docs

    def _load_markdown(self, tmp_path: str, filename: str) -> List[Document]:
        """Charge un fichier Markdown via TextLoader (LangChain)."""
        from langchain_community.document_loaders import TextLoader
        docs = TextLoader(tmp_path, encoding="utf-8").load()
        for doc in docs:
            doc.metadata["filename"]     = filename
            doc.metadata["content_type"] = "text"
        return docs

    def _load_csv(self, tmp_path: str, filename: str) -> List[Document]:
        """Chaque ligne CSV → 1 Document (une ligne = une entrée exploitable)."""
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
        """Chaque ligne Excel → 1 Document via openpyxl."""
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
        """Charge un JSON : liste → 1 Document par item, dict → 1 Document."""
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

    # ══════════════════════════════════════════════════════════════════════════
    # EXTRACTION VISUELLE — NOUVEAU
    # Appelé en COMPLÉMENT des loaders texte, jamais à la place.
    # Retourne [] si vision désactivée, PyMuPDF absent, ou aucune image trouvée.
    # ══════════════════════════════════════════════════════════════════════════

    async def _extract_visual_chunks_from_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
    ) -> List[Document]:
        """
        Extrait toutes les images embarquées dans un PDF (via PyMuPDF)
        et les analyse avec Qwen2.5-VL.

        Chaque image exploitable devient un Document avec :
            page_content = "[Figure page N — source: fichier.pdf]\\n<description Qwen>"
            metadata.content_type = "visual"

        Les images < VISION_MIN_IMAGE_BYTES sont ignorées (logos, puces déco).
        """
        if not settings.VISION_ENABLED:
            return []

        try:
            import fitz  # PyMuPDF
        except ImportError:
            log.warning(
                "PyMuPDF non installé — extraction visuelle PDF désactivée. "
                "Ajouter 'pymupdf' dans requirements.txt"
            )
            return []

        # ── Collecter toutes les images du PDF ────────────────────────────────
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
                        log.debug(
                            "Image PDF non extractible",
                            page=page_num + 1,
                            error=str(e),
                        )
            pdf.close()
        except Exception as e:
            log.warning(
                "Erreur ouverture PDF pour extraction visuelle",
                filename=filename,
                error=str(e),
            )
            return []

        if not images_to_analyze:
            return []

        log.info(
            "Vision PDF : images détectées",
            filename=filename,
            count=len(images_to_analyze),
        )

        # ── Analyse en parallèle (concurrence limitée dans vision_analyzer) ──
        descriptions = await vision_analyzer.analyze_images_batch(images_to_analyze)

        # ── Construire les Documents visuels ──────────────────────────────────
        visual_docs = []
        for (_, context), description in zip(images_to_analyze, descriptions):
            if not description:
                continue
            # context = "page 3 — fiche_gpl.pdf"
            page_num_str = context.split("—")[0].strip()   # "page 3"
            try:
                page_num = int(page_num_str.replace("page", "").strip())
            except ValueError:
                page_num = 0

            visual_docs.append(Document(
                page_content=(
                    f"[Figure {page_num_str} — source: {filename}]\n{description}"
                ),
                metadata={
                    "source":       filename,
                    "filename":     filename,
                    "doc_type":     doc_type,
                    "content_type": "visual",
                    "page":         page_num,
                    "vision_model": settings.VISION_MODEL,
                },
            ))

        log.info(
            "Vision PDF : chunks visuels créés",
            filename=filename,
            images_analyzed=len(images_to_analyze),
            chunks_created=len(visual_docs),
        )
        return visual_docs

    async def _extract_visual_chunks_from_docx(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
    ) -> List[Document]:
        """
        Extrait toutes les images d'un DOCX (format ZIP → word/media/)
        et les analyse avec Qwen2.5-VL.

        Chaque image exploitable devient un Document avec :
            page_content = "[Figure N — source: fichier.docx]\\n<description Qwen>"
            metadata.content_type = "visual"
        """
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
            log.warning(
                "Erreur extraction images DOCX",
                filename=filename,
                error=str(e),
            )
            return []

        if not images_to_analyze:
            return []

        log.info(
            "Vision DOCX : images détectées",
            filename=filename,
            count=len(images_to_analyze),
        )

        descriptions = await vision_analyzer.analyze_images_batch(images_to_analyze)

        visual_docs = []
        for (_, context), description in zip(images_to_analyze, descriptions):
            if not description:
                continue
            visual_docs.append(Document(
                page_content=(
                    f"[{context.capitalize()} — source: {filename}]\n{description}"
                ),
                metadata={
                    "source":       filename,
                    "filename":     filename,
                    "doc_type":     doc_type,
                    "content_type": "visual",
                    "page":         1,
                    "vision_model": settings.VISION_MODEL,
                },
            ))

        log.info(
            "Vision DOCX : chunks visuels créés",
            filename=filename,
            images_analyzed=len(images_to_analyze),
            chunks_created=len(visual_docs),
        )
        return visual_docs

    # ══════════════════════════════════════════════════════════════════════════
    # PIPELINE PRINCIPAL — ingest_file (interface inchangée)
    # ══════════════════════════════════════════════════════════════════════════

    async def ingest_file(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
        collection: str,
        description: str = "",
    ) -> dict:
        """
        Point d'entrée unique — appelé par main.py (signature inchangée).

        Étapes :
            1. Détection du type de fichier
            2. Écriture fichier temporaire
            3. Extraction texte — loaders LangChain originaux (INCHANGÉ)
            4. Extraction visuelle si PDF ou DOCX — Qwen2.5-VL (NOUVEAU)
            5. Fusion texte + visuels
            6. Chunking texte (splitter original) + enrichissement métadonnées
            7. Indexation Qdrant (INCHANGÉ)
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

        # ── 1. Fichier temporaire (les loaders LangChain nécessitent un path) ─
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            # ── 2. Extraction texte — ORIGINALE ──────────────────────────────
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

            # ── 3. Extraction visuelle — NOUVEAU (PDF et DOCX uniquement) ────
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
            # Nettoyage du fichier temporaire dans tous les cas
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # ── 4. Fusion texte + visuels ─────────────────────────────────────────
        all_docs = text_docs + visual_docs

        if not all_docs:
            raise ValueError(
                f"Aucun contenu extrait de '{filename}'. "
                "Vérifiez que le fichier n'est pas vide ou corrompu."
            )

        # ── 5. Chunking + enrichissement métadonnées ──────────────────────────
        splitter = _make_splitter()
        chunked_docs: List[Document] = []

        for doc in all_docs:
            if doc.metadata.get("content_type") == "visual":
                # Les chunks visuels ne sont PAS re-splittés :
                # Qwen2.5-VL produit déjà un texte structuré et cohérent.
                doc.metadata.update({
                    "doc_type":    doc_type,
                    "filename":    filename,
                    "description": description,
                })
                chunked_docs.append(doc)
            else:
                # Chunks texte : splitter original (512 tokens, overlap 64)
                splits = splitter.split_documents([doc])
                for chunk in splits:
                    chunk.metadata.update({
                        "doc_type":     doc_type,
                        "filename":     filename,
                        "description":  description,
                        "content_type": chunk.metadata.get("content_type", "text"),
                    })
                    chunked_docs.append(chunk)

        if not chunked_docs:
            raise ValueError(f"Aucun chunk produit pour '{filename}'.")

        # ── 6. Indexation Qdrant — INCHANGÉE ─────────────────────────────────
        indexed_count = qdrant_store.add_documents(collection, chunked_docs)

        text_count   = sum(
            1 for d in chunked_docs
            if d.metadata.get("content_type") != "visual"
        )
        visual_count = sum(
            1 for d in chunked_docs
            if d.metadata.get("content_type") == "visual"
        )

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


# ── Singleton ─────────────────────────────────────────────────────────────────
ingestion = DocumentIngestion()