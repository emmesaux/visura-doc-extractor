"""
Script per verificare che tutte le dipendenze siano installate correttamente.
"""

import os
import sys
from pathlib import Path


def check_python_version():
    """Verifica versione Python."""
    print("=" * 70)
    print("1. VERIFICA PYTHON")
    print("=" * 70)

    version = sys.version_info
    print(f"Versione Python: {version.major}.{version.minor}.{version.micro}")

    if version.major >= 3 and version.minor >= 8:
        print("[OK] Versione Python compatibile (>= 3.8)")
        return True

    print("[ERRORE] Python 3.8 o superiore richiesto")
    return False


def check_python_packages():
    """Verifica pacchetti Python."""
    print("\n" + "=" * 70)
    print("2. VERIFICA PACCHETTI PYTHON")
    print("=" * 70)

    required_packages = {
        'openpyxl': 'Gestione file Excel',
        'pandas': 'Manipolazione dati',
        'PyPDF2': 'Lettura PDF',
        'requests': 'Chiamate HTTP per Google Vision',
        'dotenv': 'Caricamento file .env',
        'pdf2image': 'Conversione PDF in immagini',
        'PIL': 'Gestione immagini (Pillow)',
    }

    all_ok = True

    for package, description in required_packages.items():
        try:
            if package == 'PIL':
                __import__('PIL')
            elif package == 'dotenv':
                from dotenv import load_dotenv  # noqa: F401
            else:
                __import__(package)
            print(f"[OK] {package:20} - {description}")
        except ImportError:
            print(f"[MANCANTE] {package:20} - {description}")
            all_ok = False

    if not all_ok:
        print("\nPer installare i pacchetti mancanti:")
        print("pip install openpyxl pandas PyPDF2 requests python-dotenv pdf2image pillow")

    return all_ok


def check_google_vision():
    """Verifica Google Vision OCR via API key."""
    print("\n" + "=" * 70)
    print("3. VERIFICA GOOGLE VISION OCR")
    print("=" * 70)

    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets and str(secrets.get("GOOGLE_VISION_API_KEY", "")).strip():
            print("[OK] GOOGLE_VISION_API_KEY trovata in st.secrets")
            return True
    except Exception:
        pass

    api_key = os.getenv("GOOGLE_VISION_API_KEY", "").strip()
    if api_key:
        print("[OK] GOOGLE_VISION_API_KEY impostata nell'ambiente")
        return True

    print("[ATTENZIONE] Variabile GOOGLE_VISION_API_KEY non impostata")
    print("    Usa .env in locale oppure st.secrets su Streamlit Cloud")
    return False


def check_poppler():
    """Verifica Poppler."""
    print("\n" + "=" * 70)
    print("4. VERIFICA POPPLER (Opzionale)")
    print("=" * 70)

    try:
        from pdf2image import convert_from_path  # noqa: F401

        print("[INFO] Poppler e' necessario solo per OCR su PDF scansionati")
        print("    Lo script funzionera' anche senza per PDF con testo")
        print("    Vedi: INSTALLAZIONE_OCR.md per installare Poppler")
        return True
    except Exception as e:
        print(f"[INFO] {e}")
        print("    Poppler potrebbe non essere installato")
        print("    Non e' un problema se usi solo PDF con testo selezionabile")
        return True


def check_template():
    """Verifica presenza template."""
    print("\n" + "=" * 70)
    print("5. VERIFICA TEMPLATE EXCEL")
    print("=" * 70)

    template_path = Path(__file__).parent / "format import.xlsx"

    if template_path.exists():
        print(f"[OK] Template trovato: {template_path.name}")
        try:
            import pandas as pd

            df = pd.read_excel(template_path)
            print(f"[OK] Template leggibile - {len(df.columns)} colonne")
            return True
        except Exception as e:
            print(f"[ERRORE] Impossibile leggere il template: {e}")
            return False

    print(f"[ERRORE] Template non trovato: {template_path}")
    return False


def check_folders():
    """Verifica cartelle da processare."""
    print("\n" + "=" * 70)
    print("6. VERIFICA CARTELLE DA PROCESSARE")
    print("=" * 70)

    base_dir = Path(__file__).parent
    folders = [f for f in base_dir.iterdir() if f.is_dir() and not f.name.startswith('.')]

    if folders:
        print(f"[OK] Trovate {len(folders)} cartelle da processare:")
        for i, folder in enumerate(folders[:5], 1):
            print(f"    {i}. {folder.name}")
        if len(folders) > 5:
            print(f"    ... e altre {len(folders) - 5} cartelle")
        return True

    print("[ATTENZIONE] Nessuna cartella trovata da processare")
    print("    Assicurati di avere cartelle con visure e documenti")
    return False


def main():
    """Funzione principale."""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  VERIFICA INSTALLAZIONE - ESTRATTORE VISURE CAMERALI".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print("\n")

    results = []
    results.append(("Python", check_python_version()))
    results.append(("Pacchetti Python", check_python_packages()))
    results.append(("Google Vision OCR", check_google_vision()))
    results.append(("Poppler", check_poppler()))
    results.append(("Template Excel", check_template()))
    results.append(("Cartelle", check_folders()))

    print("\n" + "=" * 70)
    print("RIEPILOGO")
    print("=" * 70)

    for name, result in results:
        status = "[OK]" if result else "[PROBLEMA]"
        print(f"{status:12} {name}")

    print("\n" + "=" * 70)

    essential_ok = results[0][1] and results[1][1] and results[4][1]

    if essential_ok:
        print("STATO: Pronto per l'uso!")
        print("\nLo script funzionera' per PDF con testo selezionabile.")

        if not results[2][1] or not results[3][1]:
            print("\nNOTA: Per usare OCR su immagini e PDF scansionati,")
            print("      configura Google Cloud Vision e installa Poppler (vedi INSTALLAZIONE_OCR.md)")

        print("\nPer estrarre i dati, esegui:")
        print("    python visura_extractor.py")
    else:
        print("STATO: Problemi rilevati")
        print("\nRisolvi i problemi segnalati prima di usare lo script.")
        print("Consulta il file README.md per le istruzioni.")

    print("=" * 70)
    print("\n")


if __name__ == "__main__":
    main()
