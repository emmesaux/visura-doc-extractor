# Estrattore Dati Visure Camerali

Sistema automatico per l'estrazione di dati da **Visure Camerali** e **Documenti di Identità** con output nel formato Excel personalizzato.

## Caratteristiche

- Estrazione automatica da PDF e immagini (JPG, JPEG, PNG)
- Riconoscimento OCR per documenti scansionati
- Output diretto nel formato template Excel fornito
- Processamento batch di multiple cartelle
- Supporto per visure camerali italiane
- Estrazione dati da carte d'identità e documenti
- Estrazione multipla di soci/amministratori (fino a 5 persone)

## Requisiti

### Software necessario

1. **Python 3.8+**
2. **Google Cloud Vision OCR** (per il riconoscimento ottico dei caratteri)

### Configurazione Google Vision con API key (Windows)

1. Crea un progetto su Google Cloud
2. Abilita l'API **Vision AI**
3. Crea una chiave API per Vision
4. Crea un file `.env` locale con:
	```bash
	GOOGLE_VISION_API_KEY=la_tua_chiave_api
	```
5. Non caricare il file `.env` su GitHub

### Deploy su Streamlit Cloud

Se pubblichi l'app su Streamlit Cloud, inserisci la stessa chiave in `st.secrets` con un file `.streamlit/secrets.toml` sul deploy:

```toml
GOOGLE_VISION_API_KEY = "la_tua_chiave_api"
```

Non committare il file reale: usa il modello [secrets.toml.example](.streamlit/secrets.toml.example).

### Librerie Python

Installa le dipendenze con:
```bash
pip install pandas openpyxl PyPDF2 google-cloud-vision PyMuPDF pillow
```

Librerie richieste:
- pandas (manipolazione dati)
- openpyxl (gestione Excel)
- PyPDF2 (estrazione testo da PDF)
- requests (chiamate HTTP verso Google Vision)
- python-dotenv (caricamento del file .env)
- PyMuPDF (rendering PDF in immagini per l'OCR)
- pillow (gestione immagini)

## Struttura delle Cartelle

Il sistema si aspetta questa struttura:

```
prova estrazione/
├── format import.xlsx          # Template Excel (NON modificare)
├── visura_extractor.py         # Script principale
├── README.md                   # Questo file
├── CARTELLA AZIENDA 1/
│   ├── visura-camerale.pdf    # Visura (nome file deve contenere "visur")
│   └── documento.pdf           # Documento identità (nome deve contenere "doc")
├── CARTELLA AZIENDA 2/
│   ├── VISUORD-xxx.pdf
│   └── carta-identita.jpg
└── ...
```

## Come Usare

### Metodo 1: Doppio click

Semplicemente fai doppio click su `visura_extractor.py`

### Metodo 2: Da terminale

```bash
cd "path/to/prova estrazione"
python visura_extractor.py
```

## Output

Lo script crea un file Excel con nome formato:
```
dati_estratti_YYYYMMDD_HHMMSS.xlsx
```

Il file conterrà:
- Una riga per ogni cartella processata
- Tutte le 149 colonne del template originale preservate
- Dati estratti dalle visure e documenti

## Dati Estratti

### Dalla Visura Camerale:
- Denominazione/Ragione Sociale
- Forma giuridica
- Codice Fiscale azienda
- Partita IVA
- Camera di Commercio e REA
- Sede legale (indirizzo, comune, CAP, provincia)
- Attività prevalente
- Codice ATECO
- Amministratori, soci e cariche (fino a 5 persone)
- Date costituzione/inizio attività

### Dal Documento di Identità:
- Nome e Cognome
- Data e luogo di nascita
- Codice Fiscale
- Sesso
- Residenza completa
- Tipo documento
- Numero documento
- Autorità di rilascio
- Date rilascio e scadenza

## Convenzioni per i Nomi dei File

Per un riconoscimento ottimale:

**Visure camerali** - il nome deve contenere:
- "visur"
- "VISUR"
- "visuord"
- "VISUORD"

**Documenti di identità** - il nome deve contenere:
- "doc"
- "DOC"
- "identit"
- "carta"

## Risoluzione Problemi

### Google Vision non configurato
**Soluzione**: crea un file `.env` con `GOOGLE_VISION_API_KEY` oppure usa `st.secrets` sul deploy

### Nessun dato estratto
**Possibili cause**:
- PDF protetto o criptato
- Qualità immagine troppo bassa
- Nome file non segue le convenzioni
- Formato visura non standard

**Soluzioni**:
- Verifica che i PDF siano leggibili
- Aumenta risoluzione scansioni (minimo 300 DPI)
- Rinomina i file seguendo le convenzioni
- Controlla i log dello script

### Errori di estrazione
**Soluzione**: Controlla il log dello script per dettagli specifici

## Personalizzazione

### Modificare i pattern di riconoscimento

I pattern regex per l'estrazione si trovano nei metodi:
- `extract_visura_data()` - riga 76+
- `extract_documento_data()` - riga 204+

### Aggiungere nuovi campi

Modifica il metodo `create_row_from_data()` alla riga 306+

## Note Tecniche

- L'estrazione avviene prima tentando di leggere il testo dal PDF
- Se il testo è insufficiente, viene usato OCR Google Vision
- I dati vengono validati con espressioni regolari
- Il formato date è italiano (GG/MM/AAAA)
- Supporto completo per caratteri accentati italiani
- Gestione automatica di più soci/amministratori per azienda

## Correzioni Recenti (v1.1.0)

- ✅ Campo 'Prest Prof' ora lasciato vuoto
- ✅ Pattern 'Indirizzo Sede' corretto (rimuove "legale" extra)
- ✅ Pattern 'Nome Rappresentante' migliorato
- ✅ Estrazione multipla di soci/amministratori (fino a 5)
- ✅ Pattern 'Ragione Sociale' senza testo extra
- ✅ Template Excel preserva tutte le 149 colonne

## Versione

1.1.0 - Correzioni pattern estrazione
