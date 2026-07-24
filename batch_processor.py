#!/usr/bin/env python3
"""
Script per l'elaborazione batch di documenti
Elabora automaticamente tutti i documenti in una cartella
"""

import os
import sys
from pathlib import Path
import pandas as pd
import PyPDF2
from PIL import Image
import re
from datetime import datetime
from google_ocr import extract_text_from_image as google_extract_text_from_image
from google_ocr import extract_text_from_pdf as google_extract_text_from_pdf
from google_ocr import extract_visura_structured_data

class BatchDocumentProcessor:
    def __init__(self, input_folder, output_file):
        self.input_folder = Path(input_folder)
        self.output_file = output_file
        self.all_data = []
        
    def process_all_documents(self):
        """Elabora tutti i documenti nella cartella"""
        if not self.input_folder.exists():
            print(f"ERRORE: La cartella {self.input_folder} non esiste!")
            return
        
        # Trova tutti i file PDF e immagini
        files = []
        for ext in ['*.pdf', '*.PDF', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG', '*.png', '*.PNG']:
            files.extend(self.input_folder.glob(ext))
        
        if not files:
            print(f"Nessun documento trovato in {self.input_folder}")
            return
        
        print(f"Trovati {len(files)} documenti da elaborare\n")
        
        for idx, file_path in enumerate(files, 1):
            print(f"[{idx}/{len(files)}] Elaborazione: {file_path.name}")
            try:
                data = self.process_single_document(file_path)
                data['Nome_File'] = file_path.name
                data['Data_Elaborazione'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.all_data.append(data)
                print(f"  ✓ Completato\n")
            except Exception as e:
                print(f"  ✗ Errore: {str(e)}\n")
        
        # Esporta tutti i dati
        self.export_data()
    
    def process_single_document(self, file_path):
        """Elabora un singolo documento"""
        # Estrae il testo
        if file_path.suffix.lower() == '.pdf':
            text = self.extract_text_from_pdf(file_path)
        else:
            text = self.extract_text_from_image(file_path)
        
        data = {}
        
        # Determina il tipo di documento e estrae i dati appropriati
        if self.is_visura_camerale(text):
            data.update(self.parse_visura_camerale(text))
            data['Tipo_File'] = 'Visura Camerale'
        elif self.is_documento_identita(text):
            data.update(self.parse_documento_identita(text))
            data['Tipo_File'] = 'Documento Identità'
        else:
            data['Tipo_File'] = 'Non Riconosciuto'
        
        return data
    
    def extract_text_from_pdf(self, file_path):
        """Estrae il testo da un file PDF"""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        if len(text.strip()) < 100:
            text = google_extract_text_from_pdf(file_path)
        return text
    
    def extract_text_from_image(self, file_path):
        """Estrae il testo da un'immagine usando Google Cloud Vision"""
        image = Image.open(file_path)
        return google_extract_text_from_image(image)
    
    def is_visura_camerale(self, text):
        """Determina se il testo è di una visura camerale"""
        keywords = ['camera di commercio', 'visura', 'rea', 'partita iva', 'codice fiscale']
        text_lower = text.lower()
        return sum(1 for keyword in keywords if keyword in text_lower) >= 2
    
    def is_documento_identita(self, text):
        """Determina se il testo è di un documento d'identità"""
        keywords = ['carta identita', 'patente', 'passaporto', 'documento', 'rilasciato']
        text_lower = text.lower()
        return sum(1 for keyword in keywords if keyword in text_lower) >= 2
    
    def parse_visura_camerale(self, text):
        """Analizza il testo della visura camerale ed estrae i dati"""
        data = {}

        try:
            ai_data = extract_visura_structured_data(text)
        except Exception as e:
            ai_data = None
            print(f"  ⚠ Estrazione AI non disponibile, uso il parser a pattern: {e}")

        if ai_data:
            data.update(ai_data)
            if data.get('Denominazione') or data.get('Ragionesociale'):
                return data
        
        # Denominazione/Ragione Sociale
        denominazione = self.extract_pattern(text, r"(?:Denominazione|Ragione sociale)[:\s]*([A-Z][^\n]+)")
        if denominazione:
            data['Denominazione'] = denominazione.strip()
        
        # Partita IVA
        piva = self.extract_pattern(text, r"(?:P\.IVA|Partita IVA)[:\s]*(\d{11})")
        if piva:
            data['Partita_IVA'] = piva
        
        # Codice Fiscale
        cf = self.extract_pattern(text, r"(?:Codice Fiscale|C\.F\.)[:\s]*([A-Z0-9]{11,16})")
        if cf:
            data['Codice_Fiscale'] = cf
        
        # Numero REA
        rea = self.extract_pattern(text, r"(?:REA|N\. REA)[:\s]*([A-Z]{2}[\s\-]?\d+)")
        if rea:
            data['Numero_REA'] = rea
        
        # Forma giuridica
        forma = self.extract_pattern(text, r"(?:Forma giuridica|Natura giuridica)[:\s]*([^\n]+)")
        if forma:
            data['Forma_Giuridica'] = forma.strip()
        
        # Sede legale
        sede = self.extract_pattern(text, r"(?:Sede legale|Indirizzo)[:\s]*([^\n]+?)(?:\d{5})")
        if sede:
            data['Sede_Legale'] = sede.strip()
        
        # CAP
        cap = self.extract_pattern(text, r"(\d{5})")
        if cap:
            data['CAP'] = cap
        
        # Comune
        comune = self.extract_pattern(text, r"\d{5}\s+([A-Z][A-Za-z\s]+?)(?:\(|Provincia)")
        if comune:
            data['Comune'] = comune.strip()
        
        # Provincia
        provincia = self.extract_pattern(text, r"(?:Provincia|\()\s*([A-Z]{2})\s*(?:\)|$)")
        if provincia:
            data['Provincia'] = provincia
        
        # Data costituzione
        data_cost = self.extract_pattern(text, r"(?:Data costituzione|Costituita il)[:\s]*(\d{2}/\d{2}/\d{4})")
        if data_cost:
            data['Data_Costituzione'] = data_cost
        
        # Capitale sociale
        capitale = self.extract_pattern(text, r"(?:Capitale sociale|Capitale)[:\s]*(?:€|EUR)?\s*([\d.,]+)")
        if capitale:
            data['Capitale_Sociale'] = capitale
        
        # Stato attività
        stato = self.extract_pattern(text, r"(?:Stato)[:\s]*(ATTIVA|CESSATA|SOSPESA)")
        if stato:
            data['Stato_Attivita'] = stato
        
        return data
    
    def parse_documento_identita(self, text):
        """Analizza il testo del documento d'identità ed estrae i dati"""
        data = {}
        
        # Nome
        nome = self.extract_pattern(text, r"(?:Nome|NOME)[:\s]*([A-Z][a-z]+)")
        if nome:
            data['Nome'] = nome
        
        # Cognome
        cognome = self.extract_pattern(text, r"(?:Cognome|COGNOME)[:\s]*([A-Z]+)")
        if cognome:
            data['Cognome'] = cognome
        
        # Data di nascita
        data_nascita = self.extract_pattern(text, r"(?:Nat[oa]|Data di nascita)[:\s]*(?:il\s*)?(\d{2}[/\.-]\d{2}[/\.-]\d{4})")
        if data_nascita:
            data['Data_Nascita'] = data_nascita
        
        # Luogo di nascita
        luogo_nascita = self.extract_pattern(text, r"(?:Nat[oa]\s*a|Luogo di nascita)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)")
        if luogo_nascita:
            data['Luogo_Nascita'] = luogo_nascita
        
        # Codice Fiscale
        cf = self.extract_pattern(text, r"([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])")
        if cf:
            data['CF_Persona'] = cf
        
        # Numero documento
        numero_doc = self.extract_pattern(text, r"(?:N\.|Numero|NUMERO)[:\s]*([A-Z]{2}\d{7}|[A-Z0-9]{6,9})")
        if numero_doc:
            data['Numero_Documento'] = numero_doc
        
        # Data rilascio
        data_rilascio = self.extract_pattern(text, r"(?:Rilasciato|Emesso|Data di rilascio)[:\s]*(?:il\s*)?(\d{2}[/\.-]\d{2}[/\.-]\d{4})")
        if data_rilascio:
            data['Data_Rilascio'] = data_rilascio
        
        # Data scadenza
        data_scadenza = self.extract_pattern(text, r"(?:Scadenza|Valida fino al)[:\s]*(\d{2}[/\.-]\d{2}[/\.-]\d{4})")
        if data_scadenza:
            data['Data_Scadenza'] = data_scadenza
        
        # Tipo documento
        tipo_doc = self.extract_pattern(text, r"(CARTA D'IDENTITA|PATENTE|PASSAPORTO)")
        if tipo_doc:
            data['Tipo_Documento'] = tipo_doc
        
        return data
    
    def extract_pattern(self, text, pattern):
        """Estrae un pattern dal testo usando regex"""
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1) if match else None
    
    def export_data(self):
        """Esporta tutti i dati in Excel e CSV"""
        if not self.all_data:
            print("Nessun dato da esportare")
            return
        
        # Crea DataFrame
        df = pd.DataFrame(self.all_data)
        
        # Esporta in Excel
        excel_file = f"{self.output_file}.xlsx"
        df.to_excel(excel_file, index=False)
        print(f"\n✓ Dati esportati in Excel: {excel_file}")
        
        # Esporta in CSV
        csv_file = f"{self.output_file}.csv"
        df.to_csv(csv_file, index=False, sep=';', encoding='utf-8-sig')
        print(f"✓ Dati esportati in CSV: {csv_file}")
        
        print(f"\nTotale documenti elaborati: {len(self.all_data)}")

def main():
    if len(sys.argv) < 2:
        print("Uso: python batch_processor.py <cartella_documenti> [nome_output]")
        print("\nEsempio:")
        print("  python batch_processor.py ./documenti risultati")
        sys.exit(1)
    
    input_folder = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"risultati_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    processor = BatchDocumentProcessor(input_folder, output_file)
    processor.process_all_documents()

if __name__ == "__main__":
    main()
