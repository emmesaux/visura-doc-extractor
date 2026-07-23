"""
Script per l'estrazione automatica di dati da Visure Camerali e Documenti di Identità
e scrittura nel formato Excel template fornito.
"""

import os
import re
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import PyPDF2
from PIL import Image
from aml_fields import AML_TEMPLATE_COLUMNS, filter_aml_template_row
from google_ocr import extract_text_from_image as google_extract_text_from_image
from google_ocr import extract_text_from_pdf as google_extract_text_from_pdf

# Per Google Vision imposta GOOGLE_APPLICATION_CREDENTIALS al JSON del service account


class VisuraExtractor:
    """Classe per l'estrazione dati dalle visure camerali"""

    def __init__(self):
        self.data = {}

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Estrae il testo da un PDF"""
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            # Se il testo estratto è vuoto o molto breve, prova con OCR Google
            if len(text.strip()) < 100:
                print(f"  Testo estratto insufficiente, provo con OCR Google...")
                text = self.extract_text_with_ocr(pdf_path)

            return text
        except Exception as e:
            print(f"  Errore nell'estrazione da {pdf_path}: {e}")
            return ""

    def extract_text_with_ocr(self, pdf_path: str) -> str:
        """Estrae testo da PDF usando Google Cloud Vision"""
        try:
            return google_extract_text_from_pdf(pdf_path)
        except Exception as e:
            print(f"  Errore OCR Google: {e}")
            return ""

    def extract_text_from_image(self, image_path: str) -> str:
        """Estrae testo da un'immagine usando Google Cloud Vision"""
        try:
            image = Image.open(image_path)
            return google_extract_text_from_image(image)
        except Exception as e:
            print(f"  Errore nell'estrazione da immagine {image_path}: {e}")
            return ""

    def extract_visura_data(self, text: str) -> Dict:
        """Estrae i dati principali da una visura camerale"""
        data = {}

        # Denominazione/Ragione Sociale
        # Pattern principale: cerca dopo "Denominazione:"
        ragione_pattern = r"(?:Denominazione|DENOMINAZIONE)[:\s]+([A-Z][^\n]*(?:\n(?!Data\s)[A-Z][^\n]*)*)"
        match = re.search(ragione_pattern, text, re.IGNORECASE | re.MULTILINE)

        # Pattern per ditte individuali: cerca dopo "VISURA ORDINARIA DELL'IMPRESA"
        if not match:
            ragione_pattern_ditta = r"VISURA\s+ORDINARIA\s+DELL['\']IMPRESA\s*\n+\s*\n([A-Z][A-Z\s]+?)(?:\n\s*\n|\n\s+\d)"
            match = re.search(ragione_pattern_ditta, text, re.IGNORECASE)

        # Pattern alternativo: cerca dopo "VISURA ORDINARIA" per visure che non hanno "Denominazione:"
        if not match:
            ragione_pattern_alt = r"VISURA\s+ORDINARIA[^\n]*\n+\s*\n([^\n]+(?:\n[^\n]+)*?)\n\s*\n"
            match = re.search(ragione_pattern_alt, text)

        if match:
            # Rimuovi eventuali newline interni e normalizza spazi
            ragione = match.group(1).strip()
            ragione = re.sub(r'\s+', ' ', ragione)  # Normalizza spazi multipli/newline
            # Rimuovi eventuali "Data" finali che potrebbero essere stati catturati
            ragione = re.sub(r'\s+Data\s+.*$', '', ragione, flags=re.IGNORECASE)
            data['Ragionesociale'] = ragione

        # Forma giuridica (includi impresa individuale)
        forma_pattern = r"Forma giuridica[:\s]+([a-z\s']+(?:limitata|semplificata|per azioni|società|individuale|s\.r\.l\.|s\.p\.a\.|s\.a\.s\.)[^\n]*)"
        match = re.search(forma_pattern, text, re.IGNORECASE)
        if match:
            data['Natura Giuridica'] = match.group(1).strip()

        # Codice Fiscale Azienda (supporta sia 11 cifre per società che 16 caratteri per ditte individuali)
        # Prima prova con 11 cifre (società)
        cf_pattern_societa = r"Codice fiscale[:\s]+(?:e[^\n]*?(?:Registro\s+Imprese|iscr\.?\s+al))?[:\s]*(\d{11})(?!\d)"
        match = re.search(cf_pattern_societa, text, re.IGNORECASE)
        if match:
            data['Codfisc Azienda'] = match.group(1)
        else:
            # Prova con 16 caratteri (ditta individuale - CF personale)
            cf_pattern_individuale = r"Codice fiscale[:\s]+(?:e[^\n]*?(?:Registro\s+Imprese|iscr\.?\s+al))?[:\s]*([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])"
            match = re.search(cf_pattern_individuale, text, re.IGNORECASE)
            if match:
                data['Codfisc Azienda'] = match.group(1)

        # Partita IVA
        piva_pattern = r"Partita IVA[:\s]+(\d{11})"
        match = re.search(piva_pattern, text, re.IGNORECASE)
        if match:
            data['Partita Iva Azienda'] = match.group(1)

        # CCIAA e REA
        cciaa_pattern = r"(?:Camera di Commercio|CCIAA)[^\n]*?([A-Z\s]+(?:SICILIA|MILANO|ROMA|NAPOLI|TORINO|CATANIA|PALERMO)[^\n]*)"
        match = re.search(cciaa_pattern, text, re.IGNORECASE)
        if match:
            data['Cciaa'] = match.group(1).strip()

        rea_pattern = r"(?:REA|Numero.*?REA)[:\s]+([A-Z]{2})\s*-?\s*(\d+)"
        match = re.search(rea_pattern, text, re.IGNORECASE)
        if match:
            data['Cciaa'] = f"{match.group(1)} - {match.group(2)}"

        # Sede legale
        sede_pattern = r"(?:Sede legale|Indirizzo Sede(?:\s+legale)?)[:\s]+([A-Z][A-Z\s']+?)\s*\(([A-Z]{2})\)\s*(VIA|PIAZZA|CORSO|VIALE)\s+([^\n]+?)(?:CAP\s*)?(\d{5})"
        match = re.search(sede_pattern, text, re.IGNORECASE)
        if match:
            data['Comune Sede'] = match.group(1).strip()
            data['Prov Sede'] = match.group(2)
            data['Indirizzo Sede'] = f"{match.group(3).strip()} {match.group(4).strip()}"
            data['Cap Sede'] = match.group(5)
            data['Stato Sede'] = 'ITALIA'

        # Attività prevalente
        attivita_patterns = [
            r"Attivit[aà]\s+prevalente\s*(?:[:\s]*\n+)?\s*(.+?)(?=\n\s*(?:Codice\s+ATECO|Codice\s+NACE|Attivit[aà]\s+import\s+export|Contratto\s+di\s+rete|Albi\s+ruoli|Albi\s+e\s+registri|Stato\s+attivit[aà]|Data\s+inizio\s+attivit[aà]|Addetti|Titolari|Unit[aà]\s+locali|Pratiche|Trasferimenti|Partecipazioni|$))",
            r"Attivit[aà]\s+prevalente\s+(.+?)\n\s*Codice\s+ATECO",
            r"Attivit[aà]\s+prevalente\s*\n+\s*((?:(?!Codice\s+ATECO|Codice\s+NACE|Codice\s*:\s*|Importanza:)[^\n]+\n*)+)",
            r"Attivit[aà]\s+prevalente\s+([^\n]+)",
            r"(?:Attività prevalente|attività prevalente)[:\s]+([a-z][a-z\s]+(?:prodotti|servizi|commercio|produzione)[^\n]{,100})",
        ]
        for pattern in attivita_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match and not data.get('Attivita'):
                attivita = match.group(1).strip()
                attivita = re.sub(r'\s+', ' ', attivita)
                attivita = re.sub(r'\bCodice\s+ATECO\b.*$', '', attivita, flags=re.IGNORECASE).strip()
                attivita = re.sub(r'\bCodice\s+NACE\b.*$', '', attivita, flags=re.IGNORECASE).strip()
                attivita = re.sub(r'\(fonte\s+Agenzia\s+delle\s+Entrate\).*$', '', attivita, flags=re.IGNORECASE).strip()
                attivita = re.sub(r'\bImportanza:\s*.*$', '', attivita, flags=re.IGNORECASE).strip()
                data['Attivita'] = attivita
                break

        # Codice ATECO
        ateco_pattern = r"(?:Codice ATECO|ATECO)[:\s]+(\d{2}\.\d{2}(?:\.\d{1,2})?)"
        match = re.search(ateco_pattern, text, re.IGNORECASE)
        if match:
            data['Cod Ateco'] = match.group(1)

        # Data costituzione
        costituzione_pattern = r"(?:Data.*?costituzione|atto di costituzione)[:\s]+(\d{2}\/\d{2}\/\d{4})"
        match = re.search(costituzione_pattern, text, re.IGNORECASE)
        if match:
            data['Data Ini Rapporto'] = match.group(1)

        # Data inizio attività
        inizio_pattern = r"Data inizio attività[:\s]+(\d{2}\/\d{2}\/\d{4})"
        match = re.search(inizio_pattern, text, re.IGNORECASE)
        if match:
            data['Data Ini Rapporto'] = match.group(1)

        # Capitale sociale
        capitale_pattern = r"(?:Capitale sociale|Versato)[:\s]+(\d+[\.,]\d{2})"
        match = re.search(capitale_pattern, text, re.IGNORECASE)
        if match:
            # Non c'è un campo capitale nel template, ma lo conserviamo
            pass

        # Estrazione di tutte le persone (amministratori, soci, titolari) con dati personali
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
            while len(parts) >= 2 and parts[-1] == parts[-2]:
                parts.pop()
            if len(parts) == 2:
                return parts[1], parts[0]
            if len(parts) >= 3:
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
        for i, persona in enumerate(persone[:5], start=1):  # Massimo 5 persone
            cognome = persona['cognome']
            nome = persona['nome']

            # Assegna i dati base
            data[f'Carica {i}'] = persona['carica']
            data[f'Cognome {i}'] = cognome
            data[f'Nome {i}'] = nome
            data[f'Ambiguita Nome {i}'] = 'NO'
            quota = extract_quota_for_person(text, cognome, nome)
            if quota:
                data[f'Quota {i}'] = quota

            if not nome:
                continue

            # Cerca i dati personali di questa persona
            # Cerca SOLO nella sezione dettagliata che contiene Nato, CF e domicilio tutti insieme
            persona_section_pattern = rf"{cognome}\s+{nome}[^\n]*\n+Nato\s+a.*?domicilio.*?CAP\s+\d{{5}}"
            persona_match = re.search(persona_section_pattern, text, re.DOTALL | re.IGNORECASE)

            if persona_match:
                persona_text = persona_match.group(0)

                # Data e luogo di nascita: "Nato a LUOGO (PROV) il DD/MM/YYYY"
                nascita_pattern = r"Nato\s+a\s+([A-Z][A-Za-z\s]+?)\s*\(([A-Z]{2})\)\s+il\s+(\d{2}/\d{2}/\d{4})"
                nascita_match = re.search(nascita_pattern, persona_text, re.IGNORECASE)
                if nascita_match:
                    data[f'Comune Nas {i}'] = nascita_match.group(1).strip()
                    data[f'Provincia Nas {i}'] = nascita_match.group(2)
                    data[f'Data Nas {i}'] = nascita_match.group(3)
                    data[f'Stato Nas {i}'] = 'ITALIA'

                    # Estrai sesso dal codice fiscale (se disponibile) o dalla data
                    # Per ora impostiamo in base al nome, o lo lasciamo vuoto
                    # Lo estrarremo dal CF quando lo troviamo

                # Codice fiscale: "Codice fiscale: XXXXXXXXXXXXXXXX"
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

                # Domicilio/Residenza: "domicilio COMUNE (PROV) VIA INDIRIZZO CAP XXXXX"
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
        cf_azienda = data.get('Codfisc Azienda', '')
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

    def extract_documento_data(self, text: str) -> Dict:
        """Estrae i dati da un documento di identità"""
        data = {}

        # Nome
        nome_pattern = r"Nome[:\s]+([A-Z]+)"
        match = re.search(nome_pattern, text)
        if match:
            data['Nome'] = match.group(1).strip()

        # Cognome
        cognome_pattern = r"Cognome[:\s]+([A-Z]+)"
        match = re.search(cognome_pattern, text)
        if match:
            data['Cognome'] = match.group(1).strip()

        # Data di nascita
        nascita_pattern = r"nato il[:\s]+(\d{2}\/\d{2}\/\d{4})"
        match = re.search(nascita_pattern, text, re.IGNORECASE)
        if match:
            data['Data Nas'] = match.group(1)

        # Luogo di nascita
        luogo_pattern = r"(?:nato|à)[:\s]+[^\n]*?([A-Z\s]+)\s*\(([A-Z]{2})\)"
        match = re.search(luogo_pattern, text)
        if match:
            data['Comune Nas'] = match.group(1).strip()
            data['Provincia Nas'] = match.group(2)
            data['Stato Nas'] = 'ITALIA'

        # Codice fiscale
        cf_pattern = r"([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])"
        match = re.search(cf_pattern, text)
        if match:
            data['Codfisc'] = match.group(1)
            # Estrai sesso dal CF (9° carattere: dispari=M, pari=F dopo 40)
            nono = int(match.group(1)[9:11])
            data['Sesso'] = 'M' if nono < 40 else 'F'

        # Residenza
        residenza_pattern = r"Residenza[:\s]+([A-Z][^\n]+)"
        match = re.search(residenza_pattern, text, re.IGNORECASE)
        if match:
            res = match.group(1).strip()
            # Prova a separare indirizzo, comune, cap
            res_parts = re.search(r"([^,]+),?\s*([A-Z\s]+)\s*\(([A-Z]{2})\).*?(\d{5})?", res)
            if res_parts:
                data['Indirizzo Res'] = res_parts.group(1).strip()
                data['Comune Res'] = res_parts.group(2).strip()
                data['Prov Res'] = res_parts.group(3)
                if res_parts.group(4):
                    data['Cap Res'] = res_parts.group(4)
                data['Stato Res'] = 'ITALIA'

        # Tipo documento
        tipo_doc_pattern = r"(CARTA D['\s]*IDENTIT[AÀ]|PATENTE|PASSAPORTO)"
        match = re.search(tipo_doc_pattern, text, re.IGNORECASE)
        if match:
            data['Tipo Doc'] = match.group(1).upper().replace("'", "'")

        # Numero documento
        num_doc_pattern = r"(?:N[°\s]*|Numero)[:\s]*([A-Z]{2}\s*\d+)"
        match = re.search(num_doc_pattern, text, re.IGNORECASE)
        if match:
            data['Num Doc'] = match.group(1).replace(' ', '')

        # Rilasciato da
        rilascio_pattern = r"(?:Rilasciato da|Firma dal|S\.M\.|COMUNE DI)[:\s]*([A-Z][A-Z\s\.]+)"
        match = re.search(rilascio_pattern, text, re.IGNORECASE)
        if match:
            data['Autorita Doc'] = match.group(1).strip()

        # Scadenza
        scadenza_pattern = r"(?:Scadenza|scadenza)[:\s]+(\d{2}\/\d{2}\/\d{4})"
        match = re.search(scadenza_pattern, text, re.IGNORECASE)
        if match:
            data['Scadenza Doc'] = match.group(1)

        # Data documento (spesso diversa dalla scadenza)
        data_doc_pattern = r"(?:Data di|del)[:\s]+(\d{2}\/\d{2}\/\d{4})"
        match = re.search(data_doc_pattern, text, re.IGNORECASE)
        if match:
            data['Data Doc'] = match.group(1)

        return data


class ExcelWriter:
    """Classe per scrivere i dati nel formato Excel template"""

    def __init__(self, template_path: str):
        """Inizializza con le colonne AML"""
        self.columns = AML_TEMPLATE_COLUMNS
        self.template_df = pd.DataFrame(columns=self.columns)
        if template_path:
            print(f"Output AML attivo (colonne: {len(self.columns)})")

    def create_row_from_data(self, visura_data: Dict, documenti_data_list: List[Dict]) -> Dict:
        """Crea una riga di dati da inserire nel template"""
        row = {}

        # Inizializza tutte le colonne a None
        for col in self.columns:
            row[col] = None

        # Dati base
        row['AZ_TipoSoggetto'] = 'S' if visura_data.get('Ragionesociale') else 'P'
        row['AZ_RagioneSociale'] = visura_data.get('Ragionesociale', '')
        row['AZ_FormaGiuridica'] = visura_data.get('Natura Giuridica', '')
        row['AZ_CF'] = visura_data.get('Codfisc Azienda', '')
        row['AZ_PIVA'] = visura_data.get('Partita Iva Azienda', '')
        row['AZ_REA'] = visura_data.get('Cciaa', '')
        row['AZ_Attivita'] = visura_data.get('Attivita', '')
        row['AZ_ATECO'] = visura_data.get('Cod Ateco', '')

        # Sede
        row['AZ_Sede_Indirizzo'] = visura_data.get('Indirizzo Sede', '')
        row['AZ_Sede_Comune'] = visura_data.get('Comune Sede', '')
        row['AZ_Sede_CAP'] = visura_data.get('Cap Sede', '')
        row['AZ_Sede_Provincia'] = visura_data.get('Prov Sede', '')
        row['AZ_Sede_Stato'] = visura_data.get('Stato Sede', 'ITALIA')

        # Date
        row['AZ_DataCostituzione'] = visura_data.get('Data Ini Rapporto', '')

        # Gestione di tutte le persone (amministratori, soci, titolari)
        # Determina quante persone sono state estratte dalla visura
        num_persone = 0
        for i in range(1, 6):  # Massimo 5 persone
            if f'Carica {i}' in visura_data or f'Nome {i}' in visura_data:
                num_persone = i

        # Popola i dati di ogni persona
        for i in range(1, num_persone + 1):
            # Dati dalla visura
            row[f'P{i}_Ruolo'] = visura_data.get(f'Carica {i}', '')
            row[f'P{i}_Nome'] = visura_data.get(f'Nome {i}', '')
            row[f'P{i}_Cognome'] = visura_data.get(f'Cognome {i}', '')
            row[f'P{i}_AmbiguitaNome'] = visura_data.get(f'Ambiguita Nome {i}', '')
            row[f'P{i}_CF'] = visura_data.get(f'Codfisc {i}', '')
            row[f'P{i}_Quota'] = visura_data.get(f'Quota {i}', '')

            # Se c'è un documento corrispondente, aggiungi i dati
            if i - 1 < len(documenti_data_list):
                doc_data = documenti_data_list[i - 1]

                # Completa i dati mancanti con quelli del documento
                if not row.get(f'P{i}_Nome'):
                    row[f'P{i}_Nome'] = doc_data.get('Nome', '')
                if not row.get(f'P{i}_Cognome'):
                    row[f'P{i}_Cognome'] = doc_data.get('Cognome', '')
                if not row.get(f'P{i}_CF'):
                    row[f'P{i}_CF'] = doc_data.get('Codfisc', '')

                # Dati aggiuntivi dal documento
                row[f'P{i}_Sesso'] = doc_data.get('Sesso', '')
                row[f'P{i}_DataNascita'] = doc_data.get('Data Nas', '')
                row[f'P{i}_ComuneNascita'] = doc_data.get('Comune Nas', '')
                row[f'P{i}_ProvinciaNascita'] = doc_data.get('Provincia Nas', '')
                row[f'P{i}_StatoNascita'] = doc_data.get('Stato Nas', 'ITALIA')
                row[f'P{i}_IndirizzoRes'] = doc_data.get('Indirizzo Res', '')
                row[f'P{i}_ComuneRes'] = doc_data.get('Comune Res', '')
                row[f'P{i}_CAPRes'] = doc_data.get('Cap Res', '')
                row[f'P{i}_ProvinciaRes'] = doc_data.get('Prov Res', '')
                row[f'P{i}_StatoRes'] = doc_data.get('Stato Res', 'ITALIA')

                # Documenti di identità (solo per la prima persona - layout template)
                if i == 1:
                    row['DOC_Tipo'] = doc_data.get('Tipo Doc', '')
                    row['DOC_Numero'] = doc_data.get('Num Doc', '')
                    row['DOC_Autorita'] = doc_data.get('Autorita Doc', '')
                    row['DOC_DataRilascio'] = doc_data.get('Data Doc', '')
                    row['DOC_DataScadenza'] = doc_data.get('Scadenza Doc', '')

        # Identificazione
        row['ID_Tipo'] = 'Diretta'
        row['ID_Data'] = datetime.now().strftime('%Y-%m-%d')
        row['PEP'] = 'NO'

        return filter_aml_template_row(row)

    def append_row(self, row_data: Dict):
        """Aggiunge una riga al DataFrame"""
        # Assicurati che row_data abbia tutte le colonne del template
        # Riempi con None le colonne mancanti
        complete_row = {col: row_data.get(col, None) for col in self.columns}

        # Crea un DataFrame con la nuova riga completa
        new_row_df = pd.DataFrame([complete_row], columns=self.columns)

        # Append alla tabella esistente
        self.template_df = pd.concat([self.template_df, new_row_df], ignore_index=True)

    def save(self, output_path: str):
        """Salva il DataFrame in Excel"""
        try:
            self.template_df.to_excel(output_path, index=False)
            print(f"\nFile salvato: {output_path}")
            print(f"Righe totali: {len(self.template_df)}")
        except Exception as e:
            print(f"Errore nel salvare il file: {e}")


def process_folder(folder_path: Path, extractor: VisuraExtractor) -> Tuple[Dict, List[Dict]]:
    """Processa una cartella contenente visura e documenti"""
    print(f"\nProcesso cartella: {folder_path.name}")

    visura_data = {}
    documenti_data = []

    # Lista file nella cartella
    files = list(folder_path.iterdir())

    for file in files:
        if not file.is_file():
            continue

        file_lower = file.name.lower()

        # Identifica visura camerale
        if 'visur' in file_lower or 'visuord' in file_lower:
            print(f"  Visura trovata: {file.name}")
            text = extractor.extract_text_from_pdf(str(file))
            visura_data = extractor.extract_visura_data(text)
            print(f"    Estratti {len(visura_data)} campi dalla visura")

        # Identifica documento di identità
        elif 'doc' in file_lower or 'identit' in file_lower or 'carta' in file_lower:
            print(f"  Documento trovato: {file.name}")

            if file.suffix.lower() == '.pdf':
                text = extractor.extract_text_from_pdf(str(file))
            elif file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                text = extractor.extract_text_from_image(str(file))
            else:
                continue

            doc_data = extractor.extract_documento_data(text)
            if doc_data:
                documenti_data.append(doc_data)
                print(f"    Estratti {len(doc_data)} campi dal documento")

    return visura_data, documenti_data


def main():
    """Funzione principale"""
    print("=" * 80)
    print("ESTRATTORE DATI VISURE CAMERALI")
    print("=" * 80)

    # Percorsi
    base_dir = Path(__file__).parent
    template_path = base_dir / "format import.xlsx"
    output_path = base_dir / f"dati_estratti_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    # Inizializza
    extractor = VisuraExtractor()
    excel_writer = ExcelWriter(str(template_path))

    # Trova tutte le cartelle da processare
    folders = [f for f in base_dir.iterdir()
              if f.is_dir() and not f.name.startswith('.')]

    print(f"\nTrovate {len(folders)} cartelle da processare")

    # Processa ogni cartella
    for folder in folders:
        try:
            visura_data, documenti_data = process_folder(folder, extractor)

            # Crea riga con i dati
            if visura_data or documenti_data:
                row = excel_writer.create_row_from_data(visura_data, documenti_data)
                excel_writer.append_row(row)
                print(f"  [OK] Dati aggiunti per {folder.name}")
            else:
                print(f"  [SKIP] Nessun dato estratto da {folder.name}")

        except Exception as e:
            print(f"  [ERROR] Errore in {folder.name}: {e}")

    # Salva risultati
    excel_writer.save(str(output_path))

    print("\n" + "=" * 80)
    print("ELABORAZIONE COMPLETATA")
    print("=" * 80)


if __name__ == "__main__":
    main()
