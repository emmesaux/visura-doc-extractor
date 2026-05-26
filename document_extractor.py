#!/usr/bin/env python3
"""
Applicazione per l'estrazione di dati da Visura Camerale e Documento d'Identità
Esporta i dati in formato Excel e CSV su una singola riga
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
from pathlib import Path
import re
from datetime import datetime
import PyPDF2
from PIL import Image
import pytesseract
import os
from aml_fields import filter_aml_raw

class DocumentExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Estrattore Dati Documenti")
        self.root.geometry("900x700")
        
        # Dati estratti
        self.data = {}
        
        # Configurazione interfaccia
        self.setup_ui()
        
    def setup_ui(self):
        """Configura l'interfaccia utente"""
        
        # Frame principale
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Titolo
        title_label = ttk.Label(main_frame, text="Estrattore Dati da Documenti", 
                                font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # Sezione Visura Camerale
        visura_frame = ttk.LabelFrame(main_frame, text="Visura Camerale", padding="10")
        visura_frame.grid(row=1, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        self.visura_path_var = tk.StringVar()
        ttk.Label(visura_frame, text="File PDF:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(visura_frame, textvariable=self.visura_path_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(visura_frame, text="Sfoglia", command=self.select_visura).grid(row=0, column=2)
        ttk.Button(visura_frame, text="Estrai Dati", command=self.extract_visura).grid(row=1, column=0, columnspan=3, pady=10)
        
        # Sezione Documento Identità
        doc_frame = ttk.LabelFrame(main_frame, text="Documento d'Identità", padding="10")
        doc_frame.grid(row=2, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        self.doc_path_var = tk.StringVar()
        ttk.Label(doc_frame, text="File Immagine:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(doc_frame, textvariable=self.doc_path_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(doc_frame, text="Sfoglia", command=self.select_document).grid(row=0, column=2)
        ttk.Button(doc_frame, text="Estrai Dati", command=self.extract_document).grid(row=1, column=0, columnspan=3, pady=10)
        
        # Area di visualizzazione dati
        data_frame = ttk.LabelFrame(main_frame, text="Dati Estratti", padding="10")
        data_frame.grid(row=3, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Treeview per visualizzare i dati
        self.tree = ttk.Treeview(data_frame, columns=("Campo", "Valore"), show="headings", height=15)
        self.tree.heading("Campo", text="Campo")
        self.tree.heading("Valore", text="Valore")
        self.tree.column("Campo", width=250)
        self.tree.column("Valore", width=500)
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pulsanti di esportazione
        export_frame = ttk.Frame(main_frame)
        export_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        ttk.Button(export_frame, text="Esporta in Excel", command=self.export_excel).grid(row=0, column=0, padx=5)
        ttk.Button(export_frame, text="Esporta in CSV", command=self.export_csv).grid(row=0, column=1, padx=5)
        ttk.Button(export_frame, text="Pulisci Dati", command=self.clear_data).grid(row=0, column=2, padx=5)
        
        # Configurazione ridimensionamento
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        data_frame.columnconfigure(0, weight=1)
        data_frame.rowconfigure(0, weight=1)
    
    def select_visura(self):
        """Seleziona il file della visura camerale"""
        filename = filedialog.askopenfilename(
            title="Seleziona Visura Camerale",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.visura_path_var.set(filename)
    
    def select_document(self):
        """Seleziona il file del documento d'identità"""
        filename = filedialog.askopenfilename(
            title="Seleziona Documento d'Identità",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.doc_path_var.set(filename)
    
    def extract_visura(self):
        """Estrae i dati dalla visura camerale"""
        file_path = self.visura_path_var.get()
        if not file_path:
            messagebox.showwarning("Attenzione", "Seleziona prima un file PDF")
            return
        
        try:
            text = self.extract_text_from_pdf(file_path)
            self.parse_visura_camerale(text)
            self.data = filter_aml_raw(self.data)
            self.update_treeview()
            messagebox.showinfo("Successo", "Dati estratti dalla visura camerale!")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nell'estrazione: {str(e)}")
    
    def extract_document(self):
        """Estrae i dati dal documento d'identità"""
        file_path = self.doc_path_var.get()
        if not file_path:
            messagebox.showwarning("Attenzione", "Seleziona prima un file immagine")
            return
        
        try:
            if file_path.lower().endswith('.pdf'):
                text = self.extract_text_from_pdf(file_path)
            else:
                text = self.extract_text_from_image(file_path)
            
            self.parse_documento_identita(text)
            self.data = filter_aml_raw(self.data)
            self.update_treeview()
            messagebox.showinfo("Successo", "Dati estratti dal documento d'identità!")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nell'estrazione: {str(e)}")
    
    def extract_text_from_pdf(self, file_path):
        """Estrae il testo da un file PDF"""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def extract_text_from_image(self, file_path):
        """Estrae il testo da un'immagine usando OCR"""
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang='ita')
        return text
    
    def parse_visura_camerale(self, text):
        """Analizza il testo della visura camerale ed estrae i dati"""
        
        # Denominazione/Ragione Sociale
        denominazione = self.extract_pattern(text, r"(?:Denominazione|Ragione sociale)[:\s]*([A-Z][^\n]+)")
        if denominazione:
            self.data['Denominazione'] = denominazione.strip()
        
        # Partita IVA
        piva = self.extract_pattern(text, r"(?:P\.IVA|Partita IVA)[:\s]*(\d{11})")
        if piva:
            self.data['Partita_IVA'] = piva
        
        # Codice Fiscale
        cf = self.extract_pattern(text, r"(?:Codice Fiscale|C\.F\.)[:\s]*([A-Z0-9]{11,16})")
        if cf:
            self.data['Codice_Fiscale'] = cf
        
        # Numero REA
        rea = self.extract_pattern(text, r"(?:REA|N\. REA)[:\s]*([A-Z]{2}[\s\-]?\d+)")
        if rea:
            self.data['Numero_REA'] = rea
        
        # Forma giuridica
        forma = self.extract_pattern(text, r"(?:Forma giuridica|Natura giuridica)[:\s]*([^\n]+)")
        if forma:
            self.data['Forma_Giuridica'] = forma.strip()
        
        # Sede legale
        sede = self.extract_pattern(text, r"(?:Sede legale|Indirizzo)[:\s]*([^\n]+?)(?:\d{5})")
        if sede:
            self.data['Sede_Legale'] = sede.strip()
        
        # CAP
        cap = self.extract_pattern(text, r"(\d{5})")
        if cap:
            self.data['CAP'] = cap
        
        # Comune
        comune = self.extract_pattern(text, r"\d{5}\s+([A-Z][A-Za-z\s]+?)(?:\(|Provincia)")
        if comune:
            self.data['Comune'] = comune.strip()
        
        # Provincia
        provincia = self.extract_pattern(text, r"(?:Provincia|\()\s*([A-Z]{2})\s*(?:\)|$)")
        if provincia:
            self.data['Provincia'] = provincia
        
        # Data costituzione
        data_cost = self.extract_pattern(text, r"(?:Data costituzione|Costituita il)[:\s]*(\d{2}/\d{2}/\d{4})")
        if data_cost:
            self.data['Data_Costituzione'] = data_cost
        
        # Capitale sociale
        capitale = self.extract_pattern(text, r"(?:Capitale sociale|Capitale)[:\s]*(?:€|EUR)?\s*([\d.,]+)")
        if capitale:
            self.data['Capitale_Sociale'] = capitale
        
        # Stato attività
        stato = self.extract_pattern(text, r"(?:Stato)[:\s]*(ATTIVA|CESSATA|SOSPESA)")
        if stato:
            self.data['Stato_Attivita'] = stato
    
    def parse_documento_identita(self, text):
        """Analizza il testo del documento d'identità ed estrae i dati"""
        
        # Nome
        nome = self.extract_pattern(text, r"(?:Nome|NOME)[:\s]*([A-Z][a-z]+)")
        if nome:
            self.data['Nome'] = nome
        
        # Cognome
        cognome = self.extract_pattern(text, r"(?:Cognome|COGNOME)[:\s]*([A-Z]+)")
        if cognome:
            self.data['Cognome'] = cognome
        
        # Data di nascita
        data_nascita = self.extract_pattern(text, r"(?:Nat[oa]|Data di nascita)[:\s]*(?:il\s*)?(\d{2}[/\.-]\d{2}[/\.-]\d{4})")
        if data_nascita:
            self.data['Data_Nascita'] = data_nascita
        
        # Luogo di nascita
        luogo_nascita = self.extract_pattern(text, r"(?:Nat[oa]\s*a|Luogo di nascita)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)")
        if luogo_nascita:
            self.data['Luogo_Nascita'] = luogo_nascita
        
        # Codice Fiscale
        cf = self.extract_pattern(text, r"([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])")
        if cf:
            self.data['CF_Persona'] = cf
        
        # Numero documento
        numero_doc = self.extract_pattern(text, r"(?:N\.|Numero|NUMERO)[:\s]*([A-Z]{2}\d{7}|[A-Z0-9]{6,9})")
        if numero_doc:
            self.data['Numero_Documento'] = numero_doc
        
        # Data rilascio
        data_rilascio = self.extract_pattern(text, r"(?:Rilasciato|Emesso|Data di rilascio)[:\s]*(?:il\s*)?(\d{2}[/\.-]\d{2}[/\.-]\d{4})")
        if data_rilascio:
            self.data['Data_Rilascio'] = data_rilascio
        
        # Data scadenza
        data_scadenza = self.extract_pattern(text, r"(?:Scadenza|Valida fino al)[:\s]*(\d{2}[/\.-]\d{2}[/\.-]\d{4})")
        if data_scadenza:
            self.data['Data_Scadenza'] = data_scadenza
        
        # Tipo documento
        tipo_doc = self.extract_pattern(text, r"(CARTA D'IDENTITA|PATENTE|PASSAPORTO)")
        if tipo_doc:
            self.data['Tipo_Documento'] = tipo_doc
    
    def extract_pattern(self, text, pattern):
        """Estrae un pattern dal testo usando regex"""
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1) if match else None
    
    def update_treeview(self):
        """Aggiorna la visualizzazione dei dati estratti"""
        # Pulisce la treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Aggiunge i dati
        for key, value in sorted(self.data.items()):
            self.tree.insert("", "end", values=(key, value))
    
    def export_excel(self):
        """Esporta i dati in formato Excel"""
        if not self.data:
            messagebox.showwarning("Attenzione", "Nessun dato da esportare")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Crea DataFrame con una singola riga
                df = pd.DataFrame([self.data])
                df.to_excel(filename, index=False)
                messagebox.showinfo("Successo", f"Dati esportati in {filename}")
            except Exception as e:
                messagebox.showerror("Errore", f"Errore nell'esportazione: {str(e)}")
    
    def export_csv(self):
        """Esporta i dati in formato CSV"""
        if not self.data:
            messagebox.showwarning("Attenzione", "Nessun dato da esportare")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Crea DataFrame con una singola riga
                df = pd.DataFrame([self.data])
                df.to_csv(filename, index=False, sep=';', encoding='utf-8-sig')
                messagebox.showinfo("Successo", f"Dati esportati in {filename}")
            except Exception as e:
                messagebox.showerror("Errore", f"Errore nell'esportazione: {str(e)}")
    
    def clear_data(self):
        """Pulisce tutti i dati"""
        self.data = {}
        self.visura_path_var.set("")
        self.doc_path_var.set("")
        self.update_treeview()
        messagebox.showinfo("Successo", "Dati puliti")

def main():
    root = tk.Tk()
    app = DocumentExtractorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
