"""Ingest attachments: base64 PDF (pypdf), docx text; images and text-less PDFs go to Gemini OCR."""

import base64
import io
import tempfile
import os
from pathlib import Path
from typing import Optional

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None


def extract_pdf_text(content_base64: str) -> Optional[str]:
    raw = base64.b64decode(content_base64)
    if PdfReader is None:
        return None
    try:
        reader = PdfReader(io.BytesIO(raw))
        text = "".join(page.extract_text() or "" for page in reader.pages)
        text = text.strip()
        return text if text else None
    except Exception:
        return None


def extract_docx_text(content_base64: str) -> Optional[str]:
    raw = base64.b64decode(content_base64)
    if Document is None:
        return None
    try:
        doc = Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs)
        text = text.strip()
        return text if text else None
    except Exception:
        return None


def is_image(content_type: str) -> bool:
    return content_type.startswith("image/")


def save_to_temp(content_base64: str, suffix: str) -> str:
    raw = base64.b64decode(content_base64)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw)
    tmp.close()
    return tmp.name


def ingest_attachment(att: dict) -> dict:
    ct = att.get("content_type", "")
    fn = att.get("file_name", "unknown")
    cb = att.get("content_base64", "")

    result = {"file_name": fn, "content_type": ct, "text": None, "image_path": None, "needs_gemini": False}

    if ct == "application/pdf":
        text = extract_pdf_text(cb)
        if text:
            result["text"] = text
        else:
            result["image_path"] = save_to_temp(cb, ".pdf")
            result["needs_gemini"] = True
    elif ct in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",):
        text = extract_docx_text(cb)
        result["text"] = text or ""
    elif is_image(ct):
        ext = Path(fn).suffix or ".jpg"
        result["image_path"] = save_to_temp(cb, ext)
        result["needs_gemini"] = True
    else:
        result["text"] = ""

    return result


def ingest_attachments(attachments: list) -> list:
    return [ingest_attachment(a) for a in attachments]