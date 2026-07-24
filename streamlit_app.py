"""
Document Extractor - Streamlit Web App
Applicazione web per l'estrazione di dati da Visure Camerali e Documenti d'Identità
"""

import streamlit as st
import pandas as pd
import PyPDF2
from PIL import Image
import re
from datetime import datetime
import io
import base64
from pathlib import Path
from aml_fields import AML_TEMPLATE_COLUMNS, filter_aml_template_row
from google_ocr import extract_text_from_image as google_extract_text_from_image
from google_ocr import extract_text_from_pdf as google_extract_text_from_pdf
from google_ocr import extract_visura_structured_data

# Configurazione pagina
st.set_page_config(
    page_title="Document Extractor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizzato
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #424242;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #E8F5E9;
        border-left: 5px solid #4CAF50;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #E3F2FD;
        border-left: 5px solid #2196F3;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #FFF3E0;
        border-left: 5px solid #FF9800;
        margin: 1rem 0;
    }
    .data-card {
        background-color: #F5F5F5;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

class DocumentExtractor:
    """Classe per l'estrazione dati da documenti"""
    
    def __init__(self):
        self.data = {}
    
    def extract_text_from_pdf(self, file):
        """Estrae il testo da un file PDF"""
        try:
            text = ""
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            if len(text.strip()) < 100:
                text = google_extract_text_from_pdf(file)
            return text
        except Exception as e:
            st.error(f"Errore nell'estrazione dal PDF: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Estrae il testo da un'immagine usando Google Cloud Vision"""
        try:
            return google_extract_text_from_image(image)
        except Exception as e:
            st.error(f"Errore nell'OCR Google: {str(e)}")
            st.warning("⚠️ Configura GOOGLE_VISION_API_KEY nel file .env o nelle variabili d'ambiente")
            return ""
    
    def extract_pattern(self, text, pattern):
        """Estrae un pattern dal testo usando regex"""
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not match:
            return None
        # Prova tutti i gruppi e ritorna il primo non-None
        for i in range(1, len(match.groups()) + 1):
            if match.group(i):
                return match.group(i).strip()
        return None
    
    def parse_visura_camerale(self, text):
        """Analizza il testo della visura camerale ed estrae i dati"""
        data = {}

        try:
            ai_data = extract_visura_structured_data(text)
        except Exception as e:
            ai_data = None
            st.warning(f"⚠️ Estrazione AI non disponibile, uso il parser a pattern: {e}")

        if ai_data:
            data.update(ai_data)
            if data.get('Denominazione') or data.get('Ragionesociale'):
                return data

        # DENOMINAZIONE / RAGIONE SOCIALE (multipli pattern incluse ditte individuali)
        denominazione_patterns = [
            r"(?:Denominazione|DENOMINAZIONE)[:\s]+([A-Z][^\n]*(?:\n(?!Data\s)[A-Z][^\n]*)*)",
            r"(?:Ragione\s+sociale|RAGIONE\s+SOCIALE)[:\s]*\n?\s*([A-Z][^\n]+)",
            r"VISURA\s+ORDINARIA\s+DELL['\']IMPRESA\s*\n+\s*\n([A-Z][A-Z\s]+?)(?:\n\s*\n|\n\s+\d)",  # Ditte individuali
            r"VISURA\s+ORDINARIA[^\n]*\n+\s*\n([^\n]+(?:\n[^\n]+)*?)\n\s*\n",
            r"^([A-Z][A-Z\s'\.]+(?:S\.R\.L\.|SRL|S\.P\.A\.|SOCIETA')[^\n]{0,100})",  # All'inizio del testo
        ]
        for pattern in denominazione_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match and not data.get('Denominazione'):
                denominazione = match.group(1).strip()
                # Pulisci eventuali artefatti
                denominazione = re.sub(r'\s+', ' ', denominazione)
                # Rimuovi "Data" e tutto quello che segue
                denominazione = re.sub(r'\s+Data\s+.*$', '', denominazione, flags=re.IGNORECASE)
                # Rimuovi caratteri speciali finali
                denominazione = re.sub(r'[,\.\-]+$', '', denominazione)
                if len(denominazione) > 3:
                    data['Denominazione'] = denominazione
                    break

        # PARTITA IVA (multipli pattern)
        piva_patterns = [
            r"(?:Partita\s+IVA|P\.?\s*IVA|PARTITA\s+IVA)[:\s]*\n?\s*(\d{11})",
            r"(?:P\.IVA|PIVA)[:\s]+(\d{11})",
            r"IVA[:\s]*(\d{11})",
        ]
        for pattern in piva_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Partita_IVA'):
                data['Partita_IVA'] = match.group(1)
                break

        # CODICE FISCALE AZIENDA (supporta sia società con 11 cifre che ditte individuali con 16 caratteri)
        # Prima prova con 11 cifre (società)
        cf_pattern_societa = r"Codice fiscale[:\s]+(?:e[^\n]*?(?:Registro\s+Imprese|iscr\.?\s+al))?[:\s]*(\d{11})(?!\d)"
        match = re.search(cf_pattern_societa, text, re.IGNORECASE)
        if match:
            data['Codice_Fiscale'] = match.group(1)
        else:
            # Prova con 16 caratteri (ditta individuale - CF personale)
            cf_pattern_individuale = r"Codice fiscale[:\s]+(?:e[^\n]*?(?:Registro\s+Imprese|iscr\.?\s+al))?[:\s]*([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])"
            match = re.search(cf_pattern_individuale, text, re.IGNORECASE)
            if match:
                data['Codice_Fiscale'] = match.group(1)

        # NUMERO REA (multipli pattern)
        rea_patterns = [
            r"(?:Numero\s+REA|N\.?\s*REA|REA)[:\s]*\n?\s*([A-Z]{2})[\s\-]*(\d+)",
            r"REA[:\s]*([A-Z]{2})\s*-\s*(\d+)",
            r"(?:Repertorio\s+[Ee]conomico)[^\n]*[:\s]*([A-Z]{2})\s*[\-\s]*(\d+)",
        ]
        for pattern in rea_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Numero_REA'):
                if len(match.groups()) == 2:
                    data['Numero_REA'] = f"{match.group(1)} - {match.group(2)}"
                else:
                    data['Numero_REA'] = match.group(1)
                break

        # FORMA GIURIDICA (multipli pattern - includi ditte individuali)
        forma_patterns = [
            r"(?:Forma\s+giuridica|Natura\s+giuridica)[:\s]*\n?\s*([a-z\s']+(?:limitata|semplificata|per azioni|società|individuale|s\.r\.l\.|s\.p\.a\.)[^\n]*)",
            r"(?:FORMA\s+GIURIDICA)[:\s]*\n?\s*([^\n]+)",
            r"(società\s+a\s+responsabilità\s+limitata[^\n]*)",
            r"(SOCIETA'?\s+A\s+RESPONSABILITA'?\s+LIMITATA[^\n]*)",
            r"(impresa\s+individuale)",
        ]
        for pattern in forma_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Forma_Giuridica'):
                forma = match.group(1).strip()
                forma = re.sub(r'\s+', ' ', forma)
                if len(forma) > 3:
                    data['Forma_Giuridica'] = forma
                    break

        # SEDE LEGALE con indirizzo completo (pattern unificato come visura_extractor.py)
        # Questo pattern cattura tutto insieme: Comune, Provincia, Indirizzo, CAP
        sede_pattern = r"(?:Sede legale|Indirizzo Sede(?:\s+legale)?)[:\s]+([A-Z][A-Z\s']+?)\s*\(([A-Z]{2})\)\s*(VIA|PIAZZA|CORSO|VIALE)\s+([^\n]+?)(?:CAP\s*)?(\d{5})"
        match = re.search(sede_pattern, text, re.IGNORECASE)
        if match:
            data['Comune'] = match.group(1).strip()
            data['Provincia'] = match.group(2)
            indirizzo = f"{match.group(3).strip()} {match.group(4).strip()}"
            # Rimuovi CAP dall'indirizzo se presente
            indirizzo = re.sub(r'\s*CAP.*$', '', indirizzo)
            data['Sede_Legale'] = indirizzo
            data['CAP'] = match.group(5)

        # Pattern di fallback per sede senza formato standard
        if not data.get('Sede_Legale'):
            sede_patterns_fallback = [
                r"(?:Sede\s+legale|Indirizzo\s+[Ss]ede)[:\s]*\n?\s*([A-Z][^\n]+?)(?:CAP\s*\d{5}|\n|$)",
                r"(?:Indirizzo)[:\s]*([^\n]+?)(?:\d{5})",
            ]
            for pattern in sede_patterns_fallback:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    sede = match.group(1).strip()
                    sede = re.sub(r'\s+', ' ', sede)
                    sede = re.sub(r'CAP.*$', '', sede)
                    if len(sede) > 5:
                        data['Sede_Legale'] = sede
                        break

        # CAP fallback (se non già estratto dalla sede)
        if not data.get('CAP'):
            cap_patterns = [
                r"(?:CAP|Cap)[:\s]*(\d{5})",
                r"(?:^|\s)(\d{5})(?:\s+[A-Z][A-Za-z]+\s*\([A-Z]{2}\))",
            ]
            for pattern in cap_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    data['CAP'] = match.group(1)
                    break

        # COMUNE fallback (se non già estratto dalla sede)
        if not data.get('Comune'):
            comune_patterns = [
                r"(?:Comune)[:\s]+([A-Z][A-Za-z\s]+?)(?:\s*\([A-Z]{2}\)|\n|$)",
                r"\d{5}\s*[-,]?\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})(?:\s*\([A-Z]{2}\))",
            ]
            for pattern in comune_patterns:
                match = re.search(pattern, text, re.MULTILINE)
                if match:
                    comune = match.group(1).strip()
                    # Valida che non contenga parole non valide
                    invalid = ['NUMERO', 'REPERTORIO', 'REA', 'AMMINISTRATIVO', 'ATTIVITA', 'REGISTRO', 'PARTITA', 'IVA', 'CODICE', 'FISCALE']
                    if not any(word in comune.upper() for word in invalid) and len(comune) > 2:
                        data['Comune'] = comune
                        break

        # PROVINCIA fallback (se non già estratta dalla sede)
        if not data.get('Provincia'):
            prov_patterns = [
                r"\(([A-Z]{2})\)",
                r"(?:Provincia|Prov\.?)[:\s]*\(?\s*([A-Z]{2})\s*\)?",
            ]
            for pattern in prov_patterns:
                match = re.search(pattern, text)
                if match:
                    data['Provincia'] = match.group(1)
                    break

        # DATA COSTITUZIONE / ISCRIZIONE
        data_cost_patterns = [
            r"(?:Data\s+atto\s+di\s+costituzione|Data\s+costituzione)[:\s]*\n?\s*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{4})",
            r"(?:Data\s+iscrizione|Data\s+di\s+iscrizione)[:\s]*\n?\s*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{4})",
            r"(?:Costituita\s+il)[:\s]*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{4})",
        ]
        for pattern in data_cost_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Data_Costituzione'):
                data['Data_Costituzione'] = match.group(1)
                break

        # DATA INIZIO ATTIVITÀ
        data_inizio_patterns = [
            r"(?:Data\s+inizio\s+attività|Data\s+inizio\s+attivit[aà])[:\s]*\n?\s*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{4})",
            r"(?:Inizio\s+attività)[:\s]*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{4})",
        ]
        for pattern in data_inizio_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Data_Inizio_Attivita'):
                data['Data_Inizio_Attivita'] = match.group(1)
                break

        # CAPITALE SOCIALE
        capitale_patterns = [
            r"(?:Capitale\s+sociale)[:\s]*\n?\s*(?:€|EUR|Euro)?\s*([\d\.,]+)",
            r"(?:Capitale)[:\s]+(?:€|EUR)?\s*([\d\.,]+)",
            r"(?:sottoscritto|versato)[:\s]*(?:€)?\s*([\d\.,]+)",
        ]
        for pattern in capitale_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Capitale_Sociale'):
                data['Capitale_Sociale'] = match.group(1)
                break

        # STATO ATTIVITÀ
        stato_patterns = [
            r"(?:Stato\s+attività|Stato)[:\s]*\n?\s*(ATTIVA|ATTIVO|CESSATA|CESSATO|SOSPESA|SOSPESO)",
            r"(?:stato)[:\s]+(attiva|cessata|sospesa)",
        ]
        for pattern in stato_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Stato_Attivita'):
                data['Stato_Attivita'] = match.group(1).upper()
                break

        # CODICE ATECO (IMPORTANTE!)
        ateco_patterns = [
            r"(?:Codice\s+ATECO|ATECO|Cod\.\s*ATECO)[:\s]*\n?\s*(\d{2}\.\d{2}(?:\.\d{1,2})?)",
            r"(?:Attività\s+prevalente).*?(\d{2}\.\d{2}(?:\.\d{1,2})?)",
            r"ATECO[:\s]+(\d{2}\.\d{2}(?:\.\d{1,2})?)",
            r"(\d{2}\.\d{2}(?:\.\d{1,2})?)",  # Pattern generico per codici
        ]
        for pattern in ateco_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match and not data.get('Codice_ATECO'):
                ateco = match.group(1)
                # Verifica che sia un formato valido (XX.XX o XX.XX.X/XX.XX.XX)
                if re.match(r'\d{2}\.\d{2}(?:\.\d{1,2})?$', ateco):
                    data['Codice_ATECO'] = ateco
                    break

        # ATTIVITÀ PREVALENTE (descrizione)
        attivita_patterns = [
            r"Attivit[aà]\s+prevalente\s*(?:[:\s]*\n+)?\s*(.+?)(?=\n\s*(?:Codice\s+ATECO|Codice\s+NACE|Attivit[aà]\s+import\s+export|Contratto\s+di\s+rete|Albi\s+ruoli|Albi\s+e\s+registri|Stato\s+attivit[aà]|Data\s+inizio\s+attivit[aà]|Addetti|Titolari|Unit[aà]\s+locali|Pratiche|Trasferimenti|Partecipazioni|$))",
            r"Attivit[aà]\s+prevalente\s+(.+?)\n\s*Codice\s+ATECO",
            r"Attivit[aà]\s+prevalente\s*\n+\s*((?:(?!Codice\s+ATECO|Codice\s+NACE|Codice\s*:\s*|Importanza:)[^\n]+\n*)+)",
            r"Attivit[aà]\s+prevalente\s+([^\n]+)",
            r"(?:Attività\s+prevalente)[:\s]*\n?\s*([a-z][a-z\s,]+(?:prodotti|servizi|commercio|produzione|vendita|gestione)[^\n]{0,150})",
            r"(?:ATTIVITA'?\s+PREVALENTE)[:\s]*([^\n]+)",
            r"(?:Oggetto\s+sociale)[:\s]*([A-Z][^\n]{20,200})",
        ]
        for pattern in attivita_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match and not data.get('Attivita_Prevalente'):
                attivita = match.group(1).strip()
                attivita = re.sub(r'\s+', ' ', attivita)
                attivita = re.sub(r'\bCodice\s+ATECO\b.*$', '', attivita, flags=re.IGNORECASE).strip()
                attivita = re.sub(r'\bCodice\s+NACE\b.*$', '', attivita, flags=re.IGNORECASE).strip()
                attivita = re.sub(r'\(fonte\s+Agenzia\s+delle\s+Entrate\).*$', '', attivita, flags=re.IGNORECASE).strip()
                attivita = re.sub(r'\bImportanza:\s*.*$', '', attivita, flags=re.IGNORECASE).strip()
                if len(attivita) > 10:
                    data['Attivita_Prevalente'] = attivita[:200]  # Max 200 caratteri
                    break

        # ESTRAZIONE DI TUTTE LE PERSONE (amministratori, soci, titolari) CON DATI PERSONALI
        # Questo è lo stesso sistema implementato in visura_extractor.py
        persone = []

        def normalize_name(value: str) -> str:
            value = re.split(r"\n\s*(?:DOMICILIO|RESIDENZA|NATO|CODICE|RAPPRESENTANTE|QUOTA)\b", value, flags=re.IGNORECASE)[0]
            return re.sub(r"\s+", " ", value.strip())

        def is_noise_name(value: str) -> bool:
            upper = value.upper()
            if "DIRITTO DI PARTECIPARE" in upper:
                return True
            noise_tokens = {
                "DIRITTO",
                "DECISIONI",
                "INDICATE",
                "PARTECIPARE",
                "SOPRA",
                "IMPRESA",
                "HA",
                "NON",
                "PUO",
                "Puo'",
                "SOCI",
                "SOCIO",
            }
            tokens = upper.split()
            if len(tokens) <= 2 and any(token in noise_tokens for token in tokens):
                return True
            return False

        def split_full_name(full_name: str) -> tuple[str, str]:
            parts = [p for p in full_name.split() if p]
            # Deduplica token finali ripetuti (es. STEFANO STEFANO)
            while len(parts) >= 2 and parts[-1] == parts[-2]:
                parts.pop()
            if len(parts) == 2:
                # Caso semplice: cognome + nome
                return parts[1], parts[0]
            if len(parts) >= 3:
                # Regola: ultimi due token nel nome, il resto nel cognome
                nome = " ".join(parts[-2:])
                cognome = " ".join(parts[:-2])
                return nome, cognome
            return "", ""


        def is_company_name(value: str) -> bool:
            upper = value.upper()
            markers = [
                "SRL",
                "S.R.L",
                "SPA",
                "S.P.A",
                "SAS",
                "S.A.S",
                "SNC",
                "S.N.C",
                "SOCIETA",
                "COMPANY",
                "LTD",
                "PLC",
                "LLC",
            ]
            return any(marker in upper for marker in markers)

        def add_person(role: str, full_name: str, is_company: bool = False) -> None:
            full_name = normalize_name(full_name)
            if not full_name:
                return
            if is_noise_name(full_name):
                return
            if is_company:
                cognome = full_name
                nome = ""
            else:
                nome, cognome = split_full_name(full_name)
                if not nome or not cognome:
                    return
            if any(p['cognome'] == cognome and p['nome'] == nome and p['carica'] == role for p in persone):
                return
            persone.append({
                'carica': role,
                'cognome': cognome,
                'nome': nome,
                'full_name': full_name
            })

        # Pattern amministratore
        amm_pattern = r"(?:Amministratore|AMMINISTRATORE)[:\s]*(?:Unico|UNICO)?[:\s]*([A-Z][A-Z\s\n'\.&-]+?)(?=\s+(?:Rappresentante|RAPPRESENTANTE|nato|NATO|Codice|CODICE|residente|RESIDENTE|quota|QUOTA|domicilio|DOMICILIO)\b|$)"
        for match in re.finditer(amm_pattern, text):
            add_person('AMMINISTRATORE', match.group(1))

        # Pattern legale rappresentante
        legale_pattern = r"(?:Legale\s+rappresentante|Rappresentante\s+legale)[:\s]*([A-Z][A-Z\s\n'\.&-]+?)(?=\s+(?:nato|NATO|Codice|CODICE|residente|RESIDENTE|quota|QUOTA|domicilio|DOMICILIO)\b|$)"
        for match in re.finditer(legale_pattern, text, re.IGNORECASE):
            add_person('LEGALE RAPPRESENTANTE', match.group(1))

        # Pattern per soci
        soci_pattern = r"(?:Socio|SOCIO)[:\s]*([A-Z][A-Z\s\n'\.&-]+?)(?=\s+(?:nato|NATO|Codice|CODICE|residente|RESIDENTE|quota|QUOTA|domicilio|DOMICILIO)\b|$)"
        for match in re.finditer(soci_pattern, text):
            full_name = normalize_name(match.group(1))
            if is_company_name(full_name):
                add_person('SOCIO AZIENDA', full_name, is_company=True)
            else:
                add_person('SOCIO', full_name)

        # Pattern per titolari (gestisce ditte individuali)
        # Pattern 1: "Titolare di impresa individualeFUSTO VALENTINA" o "Titolare Firmataria FUSTO VALENTINA"
        titolare_pattern1 = r"(?:Titolare|TITOLARE)(?:\s+di\s+impresa\s+individuale|\s+Firmataria)?[:\s\n]*([A-Z\s\n'\.&-]+?)(?=\s+(?:nato|NATO|Codice|CODICE|Registro|REGISTRO|domicilio|DOMICILIO)\b|$)"
        # Pattern 2: Standard "Titolare: NOME COGNOME"
        titolare_pattern2 = r"(?:Titolare|TITOLARE)[:\s]*([A-Z\s\n'\.&-]+?)(?=\s+(?:nato|NATO|Codice|CODICE|residente|RESIDENTE|domicilio|DOMICILIO)\b|$)"

        for pattern in [titolare_pattern1, titolare_pattern2]:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                full_name = normalize_name(match.group(1))
                add_person('TITOLARE', full_name)

        # Socio azienda in sezione pegno (multi-linea)
        pegno_pattern = r"(?:Pegno|PEGNO)\s*\n+((?:[A-Z0-9][A-Z0-9\s'\.&-]+\n)+)"
        for match in re.finditer(pegno_pattern, text):
            company = normalize_name(match.group(1).replace("\n", " "))
            if company:
                add_person('SOCIO AZIENDA', company, is_company=True)

        def extract_quota_for_person(full_text: str, cognome: str, nome: str) -> str:
            """Estrae la quota partecipazione (percentuale o valore) per una persona."""
            name_part = rf"{cognome}\s+{nome}" if nome else rf"{cognome}"
            base_pattern = name_part + r"[^\n]{0,200}?(?:quota|QUOTA|partecipazione)"
            percent_pattern = base_pattern + r"[^0-9]{0,20}(\d{1,3}(?:[\.,]\d{1,2})?)\s*%"
            value_pattern = base_pattern + r"[^\n]{0,80}?(?:€|EUR|Euro)\s*([\d\.,]+)"

            match = re.search(percent_pattern, full_text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}%"

            match = re.search(value_pattern, full_text, re.IGNORECASE)
            if match:
                return f"EUR {match.group(1)}"

            return ""

        # Per ogni persona, cerca i dati personali nel testo
        for i, persona in enumerate(persone[:5], start=1):
            cognome = persona['cognome']
            nome = persona['nome']

            data[f'Carica {i}'] = persona['carica']
            data[f'Cognome {i}'] = cognome
            data[f'Nome {i}'] = nome
            data[f'Ambiguita Nome {i}'] = 'NO'
            quota = extract_quota_for_person(text, cognome, nome)
            if quota:
                data[f'Quota {i}'] = quota

            if not nome:
                continue

            # Cerca SOLO nella sezione dettagliata che contiene Nato, CF e domicilio tutti insieme
            persona_section_pattern = rf"{cognome}\s+{nome}[^\n]*\n+Nato\s+a.*?domicilio.*?CAP\s+\d{{5}}"
            persona_match = re.search(persona_section_pattern, text, re.DOTALL | re.IGNORECASE)

            if persona_match:
                persona_text = persona_match.group(0)

                # Data e luogo di nascita
                nascita_pattern = r"Nato\s+a\s+([A-Z][A-Za-z\s]+?)\s*\(([A-Z]{2})\)\s+il\s+(\d{2}/\d{2}/\d{4})"
                nascita_match = re.search(nascita_pattern, persona_text, re.IGNORECASE)
                if nascita_match:
                    data[f'Comune Nas {i}'] = nascita_match.group(1).strip()
                    data[f'Provincia Nas {i}'] = nascita_match.group(2)
                    data[f'Data Nas {i}'] = nascita_match.group(3)
                    data[f'Stato Nas {i}'] = 'ITALIA'

                # Codice fiscale
                cf_persona_pattern = r"Codice fiscale[:\s]+([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])"
                cf_persona_match = re.search(cf_persona_pattern, persona_text, re.IGNORECASE)
                if cf_persona_match:
                    cf = cf_persona_match.group(1)
                    data[f'Codfisc {i}'] = cf

                    data[f'Ambiguita Nome {i}'] = 'NO'

                    # Estrai sesso dal CF (9° carattere: <40=M, >=40=F)
                    try:
                        giorno_sesso = int(cf[9:11])
                        data[f'Sesso {i}'] = 'M' if giorno_sesso < 40 else 'F'
                    except:
                        pass

                # Domicilio/Residenza
                domicilio_pattern = r"domicilio\s+([A-Z][A-Za-z\s]+?)\s*\(([A-Z]{2})\)\s+(VIA|PIAZZA|CORSO|VIALE)\s+([^\n]+?)\s+CAP\s+(\d{5})"
                domicilio_match = re.search(domicilio_pattern, persona_text, re.IGNORECASE)
                if domicilio_match:
                    data[f'Comune Res {i}'] = domicilio_match.group(1).strip()
                    data[f'Prov Res {i}'] = domicilio_match.group(2)
                    indirizzo_res = domicilio_match.group(4).strip()
                    data[f'Indirizzo Res {i}'] = indirizzo_res
                    data[f'Cap Res {i}'] = domicilio_match.group(5)
                    data[f'Stato Res {i}'] = 'ITALIA'

        # Gestione speciale per ditte individuali
        # Se il CF azienda è di 16 caratteri (CF personale) e c'è un titolare senza CF,
        # copia il CF azienda al titolare e deriva il sesso
        cf_azienda = data.get('Codice_Fiscale', '')
        if len(cf_azienda) == 16 and data.get('Carica 1') == 'TITOLARE':
            # Se il titolare non ha già un CF, usa il CF dell'azienda
            if not data.get('Codfisc 1'):
                data['Codfisc 1'] = cf_azienda

                # Deriva il sesso dal CF
                try:
                    giorno_sesso = int(cf_azienda[9:11])
                    data['Sesso 1'] = 'M' if giorno_sesso < 40 else 'F'
                except:
                    pass

        return data
    
    def parse_documento_identita(self, text):
        """Analizza il testo del documento d'identità ed estrae i dati"""
        data = {}

        # Normalizza il testo per facilitare matching
        text_clean = text.replace('\n', ' ').replace('  ', ' ')

        # Pattern multipli per ogni campo (più flessibili)

        # CODICE FISCALE (priorità alta - più affidabile)
        cf_patterns = [
            r"([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])",  # Standard
            r"(?:CF|C\.F\.|Codice\s*Fiscale)[:\s]*([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])",
        ]
        for pattern in cf_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['CF_Persona'] = match.group(1) if len(match.groups()) == 1 else match.group(2)
                break

        # COGNOME (multipli pattern)
        cognome_patterns = [
            r"(?:Cognome|COGNOME|Surname)[:\s]+([A-Z][A-Z\s]+?)(?:\s+Nome|\s+NOME|\s+Name|\n)",
            r"(?:Cognome|COGNOME)[:\s]*\n+([A-Z][A-Z\s]+)",
            r"^([A-Z]{2,}(?:\s+[A-Z]{2,})*)\s+(?:[A-Z][a-z]+|NOME)",  # ROSSI Mario
        ]
        for pattern in cognome_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match and not data.get('Cognome'):
                data['Cognome'] = match.group(1).strip()
                break

        # NOME (multipli pattern)
        nome_patterns = [
            r"(?:Nome|NOME|Name)[:\s]+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)",
            r"(?:Cognome|COGNOME)[^\n]+\n+(?:Nome|NOME)[:\s]*\n*([A-Z][A-Za-z]+)",
            r"[A-Z]{2,}\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:nato|Nat)",  # ROSSI Mario nato
        ]
        for pattern in nome_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match and not data.get('Nome'):
                data['Nome'] = match.group(1).strip()
                break

        # DATA DI NASCITA (molto flessibile)
        data_nascita_patterns = [
            r"(?:nat[oa]\s+il|Data\s+di\s+nascita|Date\s+of\s+birth)[:\s]*(\d{1,2}[/\.\-\s]\d{1,2}[/\.\-\s]\d{2,4})",
            r"(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{4})",  # Qualsiasi data
            r"(?:il|del)\s+(\d{1,2}[/\.\-\s]\d{1,2}[/\.\-\s]\d{2,4})",
        ]
        for pattern in data_nascita_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Data_Nascita'):
                date_str = match.group(1).strip()
                # Normalizza la data
                date_str = re.sub(r'[/\.\-\s]+', '/', date_str)
                # Se anno a 2 cifre, converti a 4
                parts = date_str.split('/')
                if len(parts) == 3 and len(parts[2]) == 2:
                    year = int(parts[2])
                    parts[2] = f"19{year}" if year > 30 else f"20{year}"
                    date_str = '/'.join(parts)
                data['Data_Nascita'] = date_str
                break

        # LUOGO DI NASCITA
        luogo_patterns = [
            r"(?:nat[oa]\s+a|nato\s+il\s+\d+[/\-\.]\d+[/\-\.]\d+\s+a)\s+([A-Z][A-Za-z\s']+?)(?:\s*\([A-Z]{2}\)|$|\s+il|\s+\d)",
            r"(?:Luogo\s+di\s+nascita|Place\s+of\s+birth)[:\s]*([A-Z][A-Za-z\s']+?)(?:\s*\(|$|\n)",
            r"(?:Comune\s+di\s+nascita)[:\s]*([A-Z][A-Za-z\s']+)",
        ]
        for pattern in luogo_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Luogo_Nascita'):
                luogo = match.group(1).strip()
                # Rimuovi date se catturate per errore
                luogo = re.sub(r'\d+[/\-\.]\d+[/\-\.]\d+', '', luogo).strip()
                if luogo and len(luogo) > 2:
                    data['Luogo_Nascita'] = luogo
                break

        # PROVINCIA NASCITA
        prov_patterns = [
            r"(?:nat[oa]\s+a)[^\n]*\(([A-Z]{2})\)",
            r"([A-Z]{2})\s*\)\s*il\s+\d",
            r"\(\s*([A-Z]{2})\s*\)",
        ]
        for pattern in prov_patterns:
            match = re.search(pattern, text)
            if match and not data.get('Provincia_Nascita'):
                data['Provincia_Nascita'] = match.group(1)
                break

        # SESSO
        sesso_patterns = [
            r"(?:Sesso|Sex)[:\s]*([MF])",
            r"\b([MF])\b(?:\s+\d{3}\s+cm|\s+nat)",  # M 180 cm o M nato
        ]
        for pattern in sesso_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Sesso'):
                data['Sesso'] = match.group(1).upper()
                break

        # STATURA
        statura_patterns = [
            r"(?:Statura|Height)[:\s]*(\d{2,3})\s*(?:cm)?",
            r"([MF])\s+(\d{3})\s*cm",  # M 180 cm
            r"(\d{3})\s*cm",
        ]
        for pattern in statura_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Statura'):
                statura = match.group(2) if len(match.groups()) > 1 else match.group(1)
                data['Statura'] = statura
                break

        # CITTADINANZA
        if 'ITALIANA' in text.upper() or 'ITALY' in text.upper():
            data['Cittadinanza'] = 'ITALIANA'

        # RESIDENZA (pattern semplificato)
        residenza_patterns = [
            r"(?:Residenza|Residence)[:\s]*([A-Z][A-Za-z0-9\s,\.'-]+?)(?:\n\n|Rilasciat)",
            r"(?:Via|Viale|Piazza|Corso)\s+([A-Za-z0-9\s,\.'-]+?)(?:\d{5}|\n)",
        ]
        for pattern in residenza_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Residenza'):
                data['Residenza'] = match.group(1).strip()
                break

        # COMUNE RESIDENZA
        comune_res_patterns = [
            r"(?:Comune)[:\s]*([A-Z][A-Za-z\s]+?)(?:\s*\(|$|\n)",
            r"\d{5}\s+([A-Z][A-Za-z\s]+?)(?:\s*\([A-Z]{2}\)|$)",
        ]
        for pattern in comune_res_patterns:
            match = re.search(pattern, text)
            if match and not data.get('Comune_Residenza'):
                data['Comune_Residenza'] = match.group(1).strip()
                break

        # NUMERO DOCUMENTO (CI elettronica formato: CA12345AA o simili)
        numero_patterns = [
            r"(?:N\.|Numero|Nr)[:\s]*([A-Z]{2}\s*\d{5,7}\s*[A-Z]{0,2})",
            r"([A-Z]{2}\d{5,7}[A-Z]{0,2})",  # CA12345AA
            r"Carta\s+d[''i]?\s*identit[aà]\s+(?:N\.?|n\.?)\s*([A-Z0-9]{6,10})",
        ]
        for pattern in numero_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Numero_Documento'):
                numero = match.group(1).replace(' ', '')
                data['Numero_Documento'] = numero
                break

        # DATA RILASCIO
        rilascio_patterns = [
            r"(?:Rilasciat[oa]\s+il|Emess[oa]\s+il|Data\s+di\s+rilascio)[:\s]*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})",
            r"(?:del|il)\s+(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{4})",
        ]
        for pattern in rilascio_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Data_Rilascio'):
                data['Data_Rilascio'] = re.sub(r'[/\.\-\s]+', '/', match.group(1))
                break

        # DATA SCADENZA
        scadenza_patterns = [
            r"(?:Scadenza|valida\s+fino\s+al)[:\s]*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})",
            r"(?:Valid until|Date of expiry)[:\s]*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})",
        ]
        for pattern in scadenza_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Data_Scadenza'):
                data['Data_Scadenza'] = re.sub(r'[/\.\-\s]+', '/', match.group(1))
                break

        # COMUNE RILASCIO
        comune_rilascio_patterns = [
            r"(?:Comune\s+di|Rilasciat[oa]\s+da)[:\s]*([A-Z][A-Za-z\s]+?)(?:\s*\n|$|il)",
            r"(?:Sindaco\s+del\s+Comune\s+di)[:\s]*([A-Z][A-Za-z\s]+)",
        ]
        for pattern in comune_rilascio_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not data.get('Comune_Rilascio'):
                data['Comune_Rilascio'] = match.group(1).strip()
                break

        # TIPO DOCUMENTO
        if any(keyword in text.upper() for keyword in ['CARTA', 'IDENTITA', 'IDENTITY']):
            data['Tipo_Documento'] = "CARTA D'IDENTITA"
        elif 'PATENTE' in text.upper():
            data['Tipo_Documento'] = 'PATENTE'
        elif 'PASSAPORTO' in text.upper() or 'PASSPORT' in text.upper():
            data['Tipo_Documento'] = 'PASSAPORTO'

        return data
    
    def is_visura_camerale(self, text):
        """Determina se il testo è di una visura camerale"""
        keywords = ['camera di commercio', 'visura', 'rea', 'partita iva']
        text_lower = text.lower()
        return sum(1 for keyword in keywords if keyword in text_lower) >= 2
    
    def is_documento_identita(self, text):
        """Determina se il testo è di un documento d'identità"""
        keywords = [
            'carta identita', 'identity card', 'patente', 'passaporto',
            'documento', 'rilasciato', 'luogo di nascita', 'data di nascita',
            'residenza', 'comune di', 'cittadinanza', 'codice fiscale'
        ]
        text_lower = text.lower()
        return sum(1 for keyword in keywords if keyword in text_lower) >= 2

def load_template():
    """Ritorna le colonne AML per l'output"""
    return AML_TEMPLATE_COLUMNS

def map_data_to_template(visura_data, documento_data):
    """Mappa i dati estratti alle colonne del template"""
    # Usa solo le colonne AML
    row = {col: "" for col in AML_TEMPLATE_COLUMNS}

    # Mappa dati della visura
    if visura_data:
        row['AZ_TipoSoggetto'] = 'S' if visura_data.get('Denominazione') else 'P'
        row['AZ_RagioneSociale'] = visura_data.get('Denominazione', '')
        row['AZ_FormaGiuridica'] = visura_data.get('Forma_Giuridica', '')
        row['AZ_CF'] = visura_data.get('Codice_Fiscale', '')
        row['AZ_PIVA'] = visura_data.get('Partita_IVA', '')
        row['AZ_REA'] = visura_data.get('Numero_REA', '')
        row['AZ_ATECO'] = visura_data.get('Codice_ATECO', '')
        row['AZ_Attivita'] = visura_data.get('Attivita_Prevalente', '')
        row['AZ_Sede_Indirizzo'] = visura_data.get('Sede_Legale', '')
        row['AZ_Sede_Comune'] = visura_data.get('Comune', '')
        row['AZ_Sede_CAP'] = visura_data.get('CAP', '')
        row['AZ_Sede_Provincia'] = visura_data.get('Provincia', '')
        row['AZ_Sede_Stato'] = 'ITALIA'
        row['AZ_DataCostituzione'] = visura_data.get('Data_Costituzione', '')
        row['ID_Tipo'] = 'Diretta'
        row['ID_Data'] = datetime.now().strftime('%Y-%m-%d')
        row['PEP'] = 'NO'

    # Mappa dati delle persone (fino a 5 persone)
    # PRIORITA': Usa i dati dalla visura se disponibili (estrazione completa),
    # altrimenti usa i dati dal documento d'identità

    # Estrai dati persone dalla visura (già estratti con il nuovo sistema)
    if visura_data:
        for i in range(1, 6):  # Fino a 5 persone
            carica_key = f'Carica {i}'
            if carica_key in visura_data:
                # Mappa tutti i dati personali dalla visura
                row[f'P{i}_Ruolo'] = visura_data.get(f'Carica {i}', '')
                row[f'P{i}_Nome'] = visura_data.get(f'Nome {i}', '')
                row[f'P{i}_Cognome'] = visura_data.get(f'Cognome {i}', '')
                row[f'P{i}_AmbiguitaNome'] = visura_data.get(f'Ambiguita Nome {i}', '')
                row[f'P{i}_Quota'] = visura_data.get(f'Quota {i}', '')
                row[f'P{i}_Sesso'] = visura_data.get(f'Sesso {i}', '')
                row[f'P{i}_DataNascita'] = visura_data.get(f'Data Nas {i}', '')
                row[f'P{i}_ComuneNascita'] = visura_data.get(f'Comune Nas {i}', '')
                row[f'P{i}_ProvinciaNascita'] = visura_data.get(f'Provincia Nas {i}', '')
                row[f'P{i}_StatoNascita'] = visura_data.get(f'Stato Nas {i}', '')
                row[f'P{i}_CF'] = visura_data.get(f'Codfisc {i}', '')
                row[f'P{i}_IndirizzoRes'] = visura_data.get(f'Indirizzo Res {i}', '')
                row[f'P{i}_ComuneRes'] = visura_data.get(f'Comune Res {i}', '')
                row[f'P{i}_CAPRes'] = visura_data.get(f'Cap Res {i}', '')
                row[f'P{i}_ProvinciaRes'] = visura_data.get(f'Prov Res {i}', '')
                row[f'P{i}_StatoRes'] = visura_data.get(f'Stato Res {i}', '')

    # Se c'è un documento d'identità, usa quei dati per Persona 1
    # (sovrascrive o integra i dati dalla visura)
    if documento_data:
        # Se non c'è già una carica dalla visura, imposta come TITOLARE/RAPPRESENTANTE
        if not row.get('P1_Ruolo'):
            row['P1_Ruolo'] = 'TITOLARE' if visura_data else 'RAPPRESENTANTE LEGALE'

        # Mappa dati documento per Persona 1 (integra o sovrascrive)
        if not row.get('P1_Nome'):
            row['P1_Nome'] = documento_data.get('Nome', '')
        if not row.get('P1_Cognome'):
            row['P1_Cognome'] = documento_data.get('Cognome', '')
        if not row.get('P1_Sesso'):
            row['P1_Sesso'] = documento_data.get('Sesso', '')
        if not row.get('P1_DataNascita'):
            row['P1_DataNascita'] = documento_data.get('Data_Nascita', '')
        if not row.get('P1_ComuneNascita'):
            row['P1_ComuneNascita'] = documento_data.get('Luogo_Nascita', '')
        if not row.get('P1_ProvinciaNascita'):
            row['P1_ProvinciaNascita'] = documento_data.get('Provincia_Nascita', '')
        if not row.get('P1_StatoNascita'):
            row['P1_StatoNascita'] = 'ITALIA'
        if not row.get('P1_CF'):
            row['P1_CF'] = documento_data.get('CF_Persona', '')
        if not row.get('P1_IndirizzoRes'):
            row['P1_IndirizzoRes'] = documento_data.get('Residenza', '')
        if not row.get('P1_ComuneRes'):
            row['P1_ComuneRes'] = documento_data.get('Comune_Residenza', '')
        if not row.get('P1_ProvinciaRes'):
            row['P1_ProvinciaRes'] = documento_data.get('Provincia_Nascita', '')
        if not row.get('P1_StatoRes'):
            row['P1_StatoRes'] = 'ITALIA'

        # Dati specifici del documento (sempre dal documento)
        row['DOC_Tipo'] = documento_data.get('Tipo_Documento', '')
        row['DOC_Numero'] = documento_data.get('Numero_Documento', '')
        row['DOC_DataRilascio'] = documento_data.get('Data_Rilascio', '')
        row['DOC_DataScadenza'] = documento_data.get('Data_Scadenza', '')
        row['DOC_Autorita'] = documento_data.get('Comune_Rilascio', '')

    return pd.DataFrame([filter_aml_template_row(row)])


def build_visura_template_dataframe(visura_data):
    """Crea il DataFrame AML per una sola visura senza documento associato."""
    return map_data_to_template(visura_data, {})

def create_download_link(df, filename, file_format):
    """Crea un link per il download del file"""
    if file_format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        b64 = base64.b64encode(output.read()).decode()
        return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}.xlsx">📥 Scarica Excel</a>'
    else:  # CSV
        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
        b64 = base64.b64encode(csv.encode()).decode()
        return f'<a href="data:text/csv;base64,{b64}" download="{filename}.csv">📥 Scarica CSV</a>'

def main():
    """Funzione principale dell'applicazione"""
    
    # Header
    st.markdown('<h1 class="main-header">📄 Document Extractor</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Estrazione automatica dati da Visure Camerali e Documenti d\'Identità</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("# 📄 Document Extractor")
        st.markdown("---")
        
        st.markdown("### 📋 Informazioni")
        st.info("""
        **Documenti supportati:**
        - 📄 Visure Camerali (PDF)
        - 🆔 Carte d'Identità
        - 🚗 Patenti
        - 🛂 Passaporti
        
        **Formati supportati:**
        - PDF
        - JPG/JPEG
        - PNG

        **OCR:**
        - Google Cloud Vision
        """)
        
        st.markdown("---")
        st.markdown("### ⚙️ Impostazioni")
        
        export_format = st.radio(
            "Formato esportazione:",
            ["Excel (.xlsx)", "CSV (.csv)", "Entrambi"],
            index=2
        )
        
        st.markdown("---")
        st.markdown("### 📊 Statistiche")
        if 'processed_docs' not in st.session_state:
            st.session_state.processed_docs = 0
        st.metric("Documenti elaborati", st.session_state.processed_docs)
        
        st.markdown("---")
        st.markdown("### 🔗 Link Utili")
        st.markdown("- [GitHub Repository](#)")
        st.markdown("- [Documentazione](#)")
        st.markdown("- [Segnala Bug](#)")
    
    # Tabs principale
    tab1, tab2, tab3 = st.tabs(["📤 Carica Documento", "📊 Risultati", "ℹ️ Guida"])
    
    with tab1:
        st.markdown("### Carica il tuo documento")

        # Info sul template
        template_exists = load_template() is not None
        if template_exists:
            st.info("📋 Output limitato ai soli campi AML")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📄 Visura Camerale")
            visura_file = st.file_uploader(
                "Carica file PDF della visura",
                type=['pdf'],
                key='visura',
                help="Carica il PDF della visura camerale ottenuto dalla Camera di Commercio"
            )

            if visura_file:
                st.success(f"✅ File caricato: {visura_file.name}")

                if st.button("🔍 Estrai Dati Visura", key='btn_visura'):
                    with st.spinner("Elaborazione in corso..."):
                        extractor = DocumentExtractor()
                        text = extractor.extract_text_from_pdf(visura_file)

                        if text:
                            # Debug: mostra testo estratto
                            with st.expander("🔍 Visualizza testo estratto dal PDF"):
                                st.text(text[:2000])  # Mostra primi 2000 caratteri

                            data = extractor.parse_visura_camerale(text)
                            data['Nome_File'] = visura_file.name
                            data['Tipo_Documento'] = 'Visura Camerale'
                            data['Data_Elaborazione'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            st.session_state.visura_data = data
                            st.session_state.visura_template_data = build_visura_template_dataframe(data)
                            st.session_state.processed_docs += 1

                            if len(data) > 3:  # Se ha estratto più di 3 campi
                                st.success("✅ Dati estratti con successo!")
                                st.balloons()
                            else:
                                st.warning("⚠️ Alcuni dati potrebbero non essere stati estratti. Verifica il formato del PDF.")

        with col2:
            st.markdown("#### 🆔 Documento d'Identità")
            doc_file = st.file_uploader(
                "Carica immagine o PDF del documento",
                type=['pdf', 'jpg', 'jpeg', 'png'],
                key='documento',
                help="Carica foto o scansione del documento d'identità"
            )

            if doc_file:
                st.success(f"✅ File caricato: {doc_file.name}")

                # Mostra preview dell'immagine
                if doc_file.type.startswith('image'):
                    image = Image.open(doc_file)
                    st.image(image, caption="Preview documento", use_column_width=True)

                if st.button("🔍 Estrai Dati Documento", key='btn_doc'):
                    with st.spinner("Elaborazione in corso..."):
                        extractor = DocumentExtractor()

                        if doc_file.type == 'application/pdf':
                            text = extractor.extract_text_from_pdf(doc_file)
                        else:
                            image = Image.open(doc_file)
                            text = extractor.extract_text_from_image(image)

                        if text:
                            # Debug: mostra testo estratto
                            with st.expander("🔍 Visualizza testo estratto dall'OCR"):
                                st.text(text)

                            data = extractor.parse_documento_identita(text)
                            data['Nome_File'] = doc_file.name
                            data['Tipo_Documento'] = 'Documento Identità'
                            data['Data_Elaborazione'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            st.session_state.documento_data = data
                            st.session_state.processed_docs += 1

                            if len(data) > 3:  # Se ha estratto più di 3 campi
                                st.success("✅ Dati estratti con successo!")
                                st.balloons()
                            else:
                                st.warning("⚠️ Alcuni dati potrebbero non essere stati estratti. Controlla la qualità dell'immagine.")

        # Pulsante per combinare i dati
        st.markdown("---")
        if 'visura_data' in st.session_state or 'documento_data' in st.session_state:
            if st.button("🔄 Combina Visura e Documento nel Formato Template", use_container_width=True):
                visura = st.session_state.get('visura_data', {})
                documento = st.session_state.get('documento_data', {})

                # Crea il DataFrame mappato al template
                st.session_state.combined_data = map_data_to_template(visura, documento)
                st.success("✅ Dati combinati nel formato template!")
                st.info("📊 Vai alla tab 'Risultati' per scaricare il file Excel")
        
        # Elaborazione Batch
        st.markdown("---")
        st.markdown("### 📦 Elaborazione Batch (Multipla)")
        st.info("Carica più documenti contemporaneamente per un'elaborazione veloce")
        
        batch_files = st.file_uploader(
            "Carica più file",
            type=['pdf', 'jpg', 'jpeg', 'png'],
            accept_multiple_files=True,
            key='batch',
            help="Seleziona più file da elaborare in una volta"
        )
        
        if batch_files and st.button("🚀 Elabora Tutti i Documenti"):
            st.caption("OCR: Google Vision. Compilazione campi: parser visura basato sul template AML.")
            visure_data = []
            documenti_data = []
            unmatched_data = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            # Fase 1: Estrazione dati da tutti i file
            status_text.text("Fase 1/2: Estrazione dati dai documenti...")

            for idx, file in enumerate(batch_files):
                extractor = DocumentExtractor()

                try:
                    if file.type == 'application/pdf':
                        text = extractor.extract_text_from_pdf(file)
                    else:
                        image = Image.open(file)
                        text = extractor.extract_text_from_image(image)

                    if text:
                        if extractor.is_visura_camerale(text):
                            data = extractor.parse_visura_camerale(text)
                            data['Nome_File'] = file.name
                            data['Tipo_Documento'] = 'Visura Camerale'
                            visure_data.append(data)
                        elif extractor.is_documento_identita(text):
                            data = extractor.parse_documento_identita(text)
                            data['Nome_File'] = file.name
                            data['Tipo_Documento'] = 'Documento Identità'
                            documenti_data.append(data)
                        else:
                            unmatched_data.append({
                                'Nome_File': file.name,
                                'Tipo_Documento': 'Non Riconosciuto',
                                'Errore': 'Tipo documento non identificato'
                            })

                except Exception as e:
                    st.warning(f"⚠️ Errore con {file.name}: {str(e)}")
                    unmatched_data.append({
                        'Nome_File': file.name,
                        'Tipo_Documento': 'Errore',
                        'Errore': str(e)
                    })

                progress_bar.progress((idx + 1) / (len(batch_files) * 2))

            # Fase 2: Matching e creazione template
            status_text.text("Fase 2/2: Matching documenti e creazione formato template...")

            template_rows = []
            matched_visure = set()
            matched_documenti = set()

            # Strategia 1: Match per codice fiscale
            for i, visura in enumerate(visure_data):
                cf_azienda = visura.get('Codice_Fiscale', '')

                # Cerca documento con stesso CF
                for j, doc in enumerate(documenti_data):
                    cf_persona = doc.get('CF_Persona', '')

                    # Match se il CF azienda coincide con CF persona (impresa individuale)
                    # oppure se abbiamo altri criteri di matching
                    if cf_azienda and cf_persona and (cf_azienda == cf_persona):
                        # Crea riga template
                        template_df = map_data_to_template(visura, doc)
                        template_rows.append(template_df)
                        matched_visure.add(i)
                        matched_documenti.add(j)
                        break

            # Strategia 2: Match per nome file (pattern comune)
            for i, visura in enumerate(visure_data):
                if i in matched_visure:
                    continue

                # Estrai pattern dal nome file (es. partita IVA, codice fiscale)
                visura_file = visura.get('Nome_File', '').lower()

                for j, doc in enumerate(documenti_data):
                    if j in matched_documenti:
                        continue

                    doc_file = doc.get('Nome_File', '').lower()

                    # Cerca pattern comuni nei nomi dei file
                    # Es: entrambi contengono lo stesso codice fiscale o nome azienda
                    cf_visura = visura.get('Codice_Fiscale', '')
                    if cf_visura and cf_visura.lower() in doc_file:
                        template_df = map_data_to_template(visura, doc)
                        template_rows.append(template_df)
                        matched_visure.add(i)
                        matched_documenti.add(j)
                        break

            # Strategia 3: Abbinamento manuale per ordine (se caricati in coppia)
            remaining_visure = [v for i, v in enumerate(visure_data) if i not in matched_visure]
            remaining_docs = [d for j, d in enumerate(documenti_data) if j not in matched_documenti]

            # Se abbiamo lo stesso numero, abbiniamo per ordine
            if len(remaining_visure) == len(remaining_docs):
                for visura, doc in zip(remaining_visure, remaining_docs):
                    template_df = map_data_to_template(visura, doc)
                    template_rows.append(template_df)
                    matched_visure.add(visure_data.index(visura))
                    matched_documenti.add(documenti_data.index(doc))
            else:
                # Abbina quelli rimanenti singolarmente
                for visura in remaining_visure:
                    template_df = map_data_to_template(visura, {})
                    template_rows.append(template_df)

                for doc in remaining_docs:
                    template_df = map_data_to_template({}, doc)
                    template_rows.append(template_df)

            # Combina tutti i DataFrame template in uno unico
            if template_rows:
                batch_template_df = pd.concat(template_rows, ignore_index=True)
                st.session_state.batch_template_data = batch_template_df
            else:
                st.session_state.batch_template_data = None

            # Salva anche i dati non matchati per riferimento
            st.session_state.batch_unmatched = unmatched_data
            st.session_state.processed_docs += len(batch_files)

            progress_bar.progress(1.0)
            status_text.text("")

            # Statistiche finali
            st.success(f"✅ Elaborazione completata!")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 Totale file", len(batch_files))
            with col2:
                st.metric("📋 Visure", len(visure_data))
            with col3:
                st.metric("🆔 Documenti", len(documenti_data))
            with col4:
                st.metric("✅ Righe template", len(template_rows) if template_rows else 0)

            if unmatched_data:
                st.warning(f"⚠️ {len(unmatched_data)} file non riconosciuti o con errori")
    
    with tab2:
        st.markdown("### 📊 Dati Estratti")

        # Visualizza dati combinati nel formato template
        if 'combined_data' in st.session_state and st.session_state.combined_data is not None:
            st.markdown("#### 📋 Dati nel Formato Template")
            st.success("✅ I dati sono stati mappati al formato import personalizzato")

            df_combined = st.session_state.combined_data

            # Statistiche
            st.markdown('<div class="success-box">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                filled_cols = df_combined.notna().sum(axis=1).iloc[0]
                st.metric("📊 Campi compilati", int(filled_cols))
            with col2:
                total_cols = len(df_combined.columns)
                st.metric("📋 Totale colonne", total_cols)
            with col3:
                percentage = (filled_cols / total_cols * 100) if total_cols > 0 else 0
                st.metric("✅ Completamento", f"{percentage:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)

            # Mostra alcune colonne chiave
            st.markdown("##### Anteprima Dati Principali")
            key_columns = ['Ragionesociale', 'Codfisc Azienda', 'Partita Iva Azienda',
                          'Nome 1', 'Cognome 1', 'Codfisc 1', 'Comune Sede']
            available_cols = [col for col in key_columns if col in df_combined.columns]
            if available_cols:
                st.dataframe(df_combined[available_cols], use_container_width=True)

            # Mostra tutti i dati
            with st.expander("🔍 Visualizza Tutti i Campi"):
                st.dataframe(df_combined, use_container_width=True)

            # Download
            st.markdown("#### 💾 Download Formato Template")
            col1, col2 = st.columns(2)

            with col1:
                if export_format in ["Excel (.xlsx)", "Entrambi"]:
                    st.markdown(create_download_link(df_combined, "dati_formato_import", "excel"), unsafe_allow_html=True)

            with col2:
                if export_format in ["CSV (.csv)", "Entrambi"]:
                    st.markdown(create_download_link(df_combined, "dati_formato_import", "csv"), unsafe_allow_html=True)

            st.markdown("---")

        # Visualizza dati singolo documento (visura o documento separato)
        if 'visura_data' in st.session_state or 'documento_data' in st.session_state:
            st.markdown("#### Dati Estratti Individuali")

            if 'visura_template_data' in st.session_state and st.session_state.visura_template_data is not None:
                with st.expander("📄 Visura Camerale - formato template"):
                    st.dataframe(st.session_state.visura_template_data)

            if 'visura_data' in st.session_state:
                with st.expander("🔍 Visura Camerale - dati grezzi"):
                    df_visura = pd.DataFrame([st.session_state.visura_data])
                    st.dataframe(df_visura)

            if 'documento_data' in st.session_state:
                with st.expander("🆔 Documento d'Identità"):
                    df_doc = pd.DataFrame([st.session_state.documento_data])
                    st.dataframe(df_doc)
        
        # Visualizza dati batch nel formato template
        if 'batch_template_data' in st.session_state and st.session_state.batch_template_data is not None:
            st.markdown("---")
            st.markdown("#### 📦 Elaborazione Batch - Formato Template")
            st.success("✅ Tutti i documenti batch sono stati mappati al formato import")

            df_batch = st.session_state.batch_template_data

            # Statistiche
            st.markdown('<div class="success-box">', unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Righe totali", len(df_batch))
            with col2:
                total_cols = len(df_batch.columns)
                st.metric("📋 Colonne template", total_cols)
            with col3:
                # Media campi compilati per riga
                avg_filled = df_batch.notna().sum(axis=1).mean()
                st.metric("📈 Media campi/riga", f"{int(avg_filled)}")
            with col4:
                # Percentuale media completamento
                avg_percentage = (avg_filled / total_cols * 100) if total_cols > 0 else 0
                st.metric("✅ Completamento medio", f"{avg_percentage:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)

            # Anteprima colonne chiave
            st.markdown("##### 🔍 Anteprima Dati Principali")
            key_columns = ['Ragionesociale', 'Codfisc Azienda', 'Partita Iva Azienda',
                          'Nome 1', 'Cognome 1', 'Codfisc 1', 'Comune Sede']
            available_cols = [col for col in key_columns if col in df_batch.columns]
            if available_cols:
                st.dataframe(df_batch[available_cols], use_container_width=True)

            # Tabella completa espandibile
            with st.expander("📋 Visualizza Tutte le Colonne del Template"):
                st.dataframe(df_batch, use_container_width=True)

            # Info su file non matchati
            if 'batch_unmatched' in st.session_state and st.session_state.batch_unmatched:
                with st.expander("⚠️ File Non Riconosciuti o con Errori"):
                    df_unmatched = pd.DataFrame(st.session_state.batch_unmatched)
                    st.dataframe(df_unmatched, use_container_width=True)

            # Download batch
            st.markdown("#### 💾 Download Batch Formato Template")
            col1, col2 = st.columns(2)

            with col1:
                if export_format in ["Excel (.xlsx)", "Entrambi"]:
                    st.markdown(create_download_link(df_batch, "batch_formato_import", "excel"), unsafe_allow_html=True)

            with col2:
                if export_format in ["CSV (.csv)", "Entrambi"]:
                    st.markdown(create_download_link(df_batch, "batch_formato_import", "csv"), unsafe_allow_html=True)

        if ('combined_data' not in st.session_state and
            'batch_template_data' not in st.session_state and
            'visura_data' not in st.session_state and
            'documento_data' not in st.session_state):
            st.info("👆 Carica ed elabora un documento nella tab **Carica Documento** per visualizzare i risultati qui")
    
    with tab3:
        st.markdown("### 📖 Guida all'uso")
        
        st.markdown("""
        #### 🚀 Come utilizzare l'applicazione
        
        **1. Carica il documento**
        - Scegli tra Visura Camerale o Documento d'Identità
        - Clicca su "Browse files" e seleziona il file
        - Formati supportati: PDF, JPG, PNG
        
        **2. Estrai i dati**
        - Clicca sul pulsante "Estrai Dati"
        - Attendi l'elaborazione (pochi secondi)
        - I dati verranno mostrati nella tab "Risultati"
        
        **3. Scarica i risultati**
        - Vai alla tab "Risultati"
        - Scegli il formato (Excel o CSV)
        - Clicca sul link di download
        - **I dati sono su una singola riga con colonne multiple**
        
        ---
        
        #### 📋 Dati estratti
        
        **Dalla Visura Camerale:**
        - Denominazione/Ragione Sociale
        - Partita IVA
        - Codice Fiscale
        - Numero REA
        - Forma Giuridica
        - Sede Legale, CAP, Comune, Provincia
        - Data di Costituzione
        - Capitale Sociale
        - Stato Attività
        
        **Dal Documento d'Identità:**
        - Nome e Cognome
        - Data e Luogo di Nascita (con Provincia)
        - Codice Fiscale
        - Residenza e Comune di Residenza
        - Numero Documento
        - Data di Rilascio e Scadenza
        - Comune di Rilascio
        - Sesso, Statura, Cittadinanza
        - Tipo Documento
        
        ---
        
        #### 💡 Suggerimenti per migliori risultati
        
        **Per le Visure:**
        - Usa PDF originali dalla Camera di Commercio
        - Evita scansioni di bassa qualità
        
        **Per i Documenti d'Identità:**
        - Fotografia ben illuminata
        - Documento piatto (non piegato)
        - Risoluzione minima 300 DPI
        - Evita riflessi
        
        ---
        
        #### ⚠️ Note importanti
        
        - Questa è una versione web dell'applicazione
        - Richiede Google Cloud Vision configurato con un service account
        - I dati vengono elaborati localmente (privacy garantita)
        - Per uso professionale, considera il deploy su server dedicato
        
        ---
        
        #### 🔗 Risorse
        
        - [GitHub Repository](https://github.com/tuousername/document-extractor)
        - [Documentazione Completa](https://github.com/tuousername/document-extractor/blob/main/README.md)
        - [Segnala un Bug](https://github.com/tuousername/document-extractor/issues)
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>📄 Document Extractor v2.0 Web Edition | Sviluppato con ❤️ usando Streamlit</p>
        <p>🔒 I tuoi dati sono sicuri - Elaborazione locale | 🆓 Open Source - MIT License</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
