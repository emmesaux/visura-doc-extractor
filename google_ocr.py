"""Helper OCR basato su Google Vision REST API con API key."""

from __future__ import annotations

import base64
import json
import io
import os
import re
from pathlib import Path

from PIL import Image
import requests
from dotenv import load_dotenv

load_dotenv()


def _get_secret(name: str) -> str:
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets:
            value = str(secrets.get(name, "")).strip()
            if value:
                return value
    except Exception:
        pass

    return os.getenv(name, "").strip()


def _get_vision_api_key() -> str:
    """Chiave per Cloud Vision (vision.googleapis.com): richiede un progetto GCP
    con Vision API abilitata e fatturazione attiva. Le chiavi generate su
    Google AI Studio per Gemini NON funzionano qui (rispondono 401)."""
    api_key = _get_secret("GOOGLE_VISION_API_KEY")
    if api_key:
        return api_key

    raise RuntimeError(
        "Chiave mancante: imposta GOOGLE_VISION_API_KEY (chiave Cloud Vision, non Gemini) "
        "nel file .env locale o in st.secrets per il deploy."
    )


def _get_gemini_api_key() -> str:
    """Chiave per Generative Language API (generativelanguage.googleapis.com),
    tipicamente creata su Google AI Studio. Se GEMINI_API_KEY non è impostata,
    ripiega su GOOGLE_VISION_API_KEY per compatibilità con configurazioni esistenti."""
    api_key = _get_secret("GEMINI_API_KEY")
    if api_key:
        return api_key

    api_key = _get_secret("GOOGLE_VISION_API_KEY")
    if api_key:
        return api_key

    raise RuntimeError(
        "Chiave mancante: imposta GEMINI_API_KEY nel file .env locale o in st.secrets per il deploy."
    )


def _call_vision_api(image_bytes: bytes) -> dict:
    api_key = _get_vision_api_key()
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


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _set_if_present(target: dict, key: str, value) -> None:
    if value is None:
        return
    value_text = str(value).strip()
    if value_text:
        target[key] = value_text


def _normalize_visura_payload(payload: dict) -> dict:
    data: dict = {}
    company = payload.get("azienda") if isinstance(payload.get("azienda"), dict) else payload

    company_field_map = {
        "Denominazione": ["Denominazione", "denominazione", "ragione_sociale", "ragione sociale"],
        "Partita_IVA": ["Partita_IVA", "partita_iva", "partita iva"],
        "Codice_Fiscale": ["Codice_Fiscale", "codice_fiscale", "codice fiscale"],
        "Numero_REA": ["Numero_REA", "numero_rea", "rea"],
        "Forma_Giuridica": ["Forma_Giuridica", "forma_giuridica", "forma giuridica"],
        "Sede_Legale": ["Sede_Legale", "sede_legale", "indirizzo_sede", "indirizzo sede"],
        "Comune": ["Comune", "comune", "comune_sede", "comune sede"],
        "Provincia": ["Provincia", "provincia", "prov_sede", "prov sede"],
        "CAP": ["CAP", "cap"],
        "Data_Costituzione": ["Data_Costituzione", "data_costituzione", "data costituzione"],
        "Data_Inizio_Attivita": ["Data_Inizio_Attivita", "data_inizio_attivita", "data inizio attivita"],
        "Codice_ATECO": ["Codice_ATECO", "codice_ateco", "ateco"],
        "Attivita_Prevalente": ["Attivita_Prevalente", "attivita_prevalente", "attivita prevalente"],
        "Stato_Attivita": ["Stato_Attivita", "stato_attivita", "stato attivita"],
    }

    for target_key, source_keys in company_field_map.items():
        for source_key in source_keys:
            if source_key in company:
                _set_if_present(data, target_key, company.get(source_key))
                break

    aliases = {
        "Ragionesociale": data.get("Denominazione", ""),
        "Natura Giuridica": data.get("Forma_Giuridica", ""),
        "Codfisc Azienda": data.get("Codice_Fiscale", ""),
        "Partita Iva Azienda": data.get("Partita_IVA", ""),
        "Cciaa": data.get("Numero_REA", ""),
        "Comune Sede": data.get("Comune", ""),
        "Prov Sede": data.get("Provincia", ""),
        "Indirizzo Sede": data.get("Sede_Legale", ""),
        "Cap Sede": data.get("CAP", ""),
        "Stato Sede": "ITALIA" if data.get("Sede_Legale") else "",
        "Data Ini Rapporto": data.get("Data_Costituzione", "") or data.get("Data_Inizio_Attivita", ""),
        "Cod Ateco": data.get("Codice_ATECO", ""),
        "Attivita": data.get("Attivita_Prevalente", ""),
    }
    for key, value in aliases.items():
        _set_if_present(data, key, value)

    people = payload.get("persone") if isinstance(payload.get("persone"), list) else []
    for index, person in enumerate(people[:5], start=1):
        if not isinstance(person, dict):
            continue

        _set_if_present(data, f"Carica {index}", person.get("ruolo") or person.get("carica") or person.get("role"))
        _set_if_present(data, f"Nome {index}", person.get("nome") or person.get("name"))
        _set_if_present(data, f"Cognome {index}", person.get("cognome") or person.get("surname"))
        _set_if_present(data, f"Ambiguita Nome {index}", person.get("ambiguita_nome") or "NO")
        _set_if_present(data, f"Quota {index}", person.get("quota"))
        _set_if_present(data, f"Sesso {index}", person.get("sesso"))
        _set_if_present(data, f"Data Nas {index}", person.get("data_nascita"))
        _set_if_present(data, f"Comune Nas {index}", person.get("comune_nascita"))
        _set_if_present(data, f"Provincia Nas {index}", person.get("provincia_nascita"))
        _set_if_present(data, f"Stato Nas {index}", person.get("stato_nascita") or "ITALIA")
        _set_if_present(data, f"Codfisc {index}", person.get("cf") or person.get("codice_fiscale"))
        _set_if_present(data, f"Indirizzo Res {index}", person.get("indirizzo_res"))
        _set_if_present(data, f"Comune Res {index}", person.get("comune_res"))
        _set_if_present(data, f"Cap Res {index}", person.get("cap_res"))
        _set_if_present(data, f"Prov Res {index}", person.get("provincia_res"))
        _set_if_present(data, f"Stato Res {index}", person.get("stato_res") or "ITALIA")

    return data


def extract_visura_structured_data(text: str) -> dict:
    """Estrae una visura in JSON strutturato usando Gemini e ritorna un dizionario normalizzato."""
    api_key = _get_gemini_api_key()
    # "gemini-flash-latest" punta sempre al modello flash correntemente raccomandato
    # da Google. Modelli fissati per nome (es. "gemini-2.0-flash") possono restare
    # senza quota gratuita sui progetti nuovi una volta superati da versioni più recenti.
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    prompt = f"""
Sei un motore di estrazione dati da visure camerali italiane.
Leggi il testo OCR e restituisci SOLO JSON valido, senza markdown e senza testo extra.

Schema richiesto:
{{
  "azienda": {{
    "Denominazione": "",
    "Partita_IVA": "",
    "Codice_Fiscale": "",
    "Numero_REA": "",
    "Forma_Giuridica": "",
    "Sede_Legale": "",
    "Comune": "",
    "Provincia": "",
    "CAP": "",
    "Data_Costituzione": "",
    "Data_Inizio_Attivita": "",
    "Codice_ATECO": "",
    "Attivita_Prevalente": "",
    "Stato_Attivita": ""
  }},
  "persone": [
    {{
      "ruolo": "",
      "nome": "",
      "cognome": "",
      "ambiguita_nome": "NO",
      "cf": "",
      "quota": "",
      "sesso": "",
      "data_nascita": "",
      "comune_nascita": "",
      "provincia_nascita": "",
      "stato_nascita": "",
      "indirizzo_res": "",
      "comune_res": "",
      "cap_res": "",
      "provincia_res": "",
      "stato_res": ""
    }}
  ]
}}

Regole:
- Non inventare dati. Se un campo non è presente esplicitamente nel testo, usa stringa vuota.
- Restituisci al massimo 5 persone.
- Se trovi società tra i soci, valorizza il ruolo coerentemente.

Regole sulle persone (sezione "Titolari di cariche o qualifiche" / "Soci e titolari di
cariche o qualifiche"):
- Estrai TUTTE le persone elencate in quella sezione, non solo la prima: includi Titolare,
  Titolare Firmatario, Amministratore (Unico/Delegato), Legale Rappresentante, Socio
  (anche "Socio di società in nome collettivo", accomandatario/accomandante), Liquidatore,
  Rappresentante dell'impresa, Direttore Tecnico. Ogni persona distinta va in un elemento
  separato dell'array "persone".
- I nominativi nelle visure sono scritti in ordine COGNOME NOME (tutto maiuscolo). Dividi
  correttamente cognome e nome; non includere MAI nei campi nome/cognome parole che sono
  etichette di ruolo (es. "Titolare", "Firmatario", "Rappresentante", "Liquidatore").
- Molte visure ripetono lo stesso ruolo+nominativo due volte (una volta in un riquadro di
  sintesi, una volta nel paragrafo di dettaglio) prima dei dati anagrafici: non incollare
  il testo ripetuto dentro nome/cognome, usa solo il nominativo pulito.
- Per ciascuna persona, cerca i dati anagrafici associati: rigo "Nato a COMUNE (PROV) il
  GG/MM/AAAA" per data/comune/provincia di nascita, e rigo "residenza COMUNE (PROV)
  INDIRIZZO CAP NNNNN" per l'indirizzo di residenza (in alcune visure compare come
  "domicilio" invece di "residenza": trattali allo stesso modo).

Regole su attività e ATECO:
- "Attivita_Prevalente" va presa SOLO da un campo esplicitamente etichettato "Attività
  prevalente" (o "attività prevalente esercitata dall'impresa"). NON usare mai il testo di
  "Oggetto sociale" come Attività_Prevalente: sono campi diversi. Se non c'è un'attività
  prevalente esplicita, lascia stringa vuota.
- "Codice_ATECO" va preso SOLO da un campo etichettato "Codice ATECO" o "Classificazione
  ATECO ... Codice: NN.NN.N". Non estrarre MAI un codice ATECO da importi in euro, capitale
  sociale, conferimenti o altri numeri non etichettati come ATECO.

Testo OCR:
{text[:20000]}
""".strip()

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    response = requests.post(
        f"{endpoint}?key={api_key}",
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    body = response.json()

    candidates = body.get("candidates", [])
    if not candidates:
        return {}

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return {}

    raw_text = parts[0].get("text", "")
    if not raw_text:
        return {}

    cleaned = _strip_code_fences(raw_text)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        return {}

    return _normalize_visura_payload(payload)