"""Helper OCR basato su Google Vision REST API con API key."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

from PIL import Image
import requests
from dotenv import load_dotenv

load_dotenv()


def _get_api_key() -> str:
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets:
            api_key = str(secrets.get("GOOGLE_VISION_API_KEY", "")).strip()
            if api_key:
                return api_key
    except Exception:
        pass

    api_key = os.getenv("GOOGLE_VISION_API_KEY", "").strip()
    if api_key:
        return api_key

    raise RuntimeError(
        "Chiave mancante: imposta GOOGLE_VISION_API_KEY nel file .env locale o in st.secrets per il deploy."
    )


def _call_vision_api(image_bytes: bytes) -> dict:
    api_key = _get_api_key()
    endpoint = "https://vision.googleapis.com/v1/images:annotate"
    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                "imageContext": {"languageHints": ["it"]},
            }
        ]
    }

    response = requests.post(endpoint, params={"key": api_key}, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    if data.get("error"):
        message = data["error"].get("message", "Errore sconosciuto di Google Vision")
        raise RuntimeError(message)

    return data


def extract_text_from_image(image: Image.Image) -> str:
    """Estrae testo da un'immagine usando Google Vision REST API."""
    if image.mode != "RGB":
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    data = _call_vision_api(buffer.getvalue())
    response = data.get("responses", [{}])[0]

    if response.get("error"):
        raise RuntimeError(response["error"].get("message", "Errore Google Vision OCR"))

    if response.get("fullTextAnnotation", {}).get("text"):
        return response["fullTextAnnotation"]["text"]

    text_annotations = response.get("textAnnotations", [])
    if text_annotations:
        return text_annotations[0].get("description", "")

    return ""


def extract_text_from_pdf(pdf_path: str | Path, dpi: int = 300) -> str:
    """Estrae testo da un PDF convertendo le pagine in immagini e usando Google Vision."""
    from pdf2image import convert_from_path

    images = convert_from_path(str(pdf_path), dpi=dpi)
    extracted_pages: list[str] = []

    for page_image in images:
        page_text = extract_text_from_image(page_image)
        if page_text:
            extracted_pages.append(page_text)

    return "\n".join(extracted_pages)