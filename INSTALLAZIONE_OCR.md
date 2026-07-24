# Guida Installazione OCR Google Vision + Gemini

Questa guida spiega come configurare le due chiavi Google usate dall'app:
una per l'OCR (Google Cloud Vision) e una per la strutturazione dei dati
(Gemini). **Sono due prodotti diversi e le chiavi NON sono intercambiabili**:
una chiave creata su Google AI Studio per Gemini restituisce 401 se usata
su Cloud Vision, e una chiave Cloud Vision in genere non è abilitata per
Gemini.

## Requisiti

- Un progetto Google Cloud con **Vision API** attiva e fatturazione abilitata
  (Vision API non ha una vera free tier via API key) → `GOOGLE_VISION_API_KEY`
- Una chiave **Gemini** (es. da https://aistudio.google.com/apikey), con
  quota/billing sufficiente per il modello usato (`gemini-2.0-flash`) →
  `GEMINI_API_KEY`
- Un file `.env` locale nella cartella del progetto

## Configurazione Locale

1. Crea un file `.env` nella root del progetto.
2. Inserisci queste righe:

```bash
GOOGLE_VISION_API_KEY=la_tua_chiave_cloud_vision
GEMINI_API_KEY=la_tua_chiave_gemini
```

Se `GEMINI_API_KEY` non è impostata, il codice ripiega su
`GOOGLE_VISION_API_KEY` per compatibilità, ma funziona solo se quella chiave
è abilitata anche per la Generative Language API.

3. Non caricare il file `.env` su GitHub.
4. Per la repo, usa un file `.env.example` come riferimento.

## Errori comuni

- **401 Unauthorized su vision.googleapis.com / "API keys are not supported
  by this API"**: la chiave in `GOOGLE_VISION_API_KEY` è una chiave Gemini/AI
  Studio, non una chiave Cloud Vision. Crea una API key dalla Google Cloud
  Console sul progetto con Vision API abilitata.
- **429 RESOURCE_EXHAUSTED con `limit: 0` su generativelanguage.googleapis.com**:
  il progetto legato alla chiave Gemini non ha quota free-tier (spesso perché
  manca la fatturazione attiva o il progetto non è idoneo al free tier).
  Abilita la fatturazione sul progetto o usa una chiave di un progetto con
  quota disponibile.

## Test rapido

Esegui:

```bash
python verifica_installazione.py
```

Se la chiave e' presente, il controllo mostrera' lo stato OK per Google Vision OCR.

## Note

- L'OCR funziona su immagini JPG, PNG e su PDF scansionati convertiti in immagini.
- Se il testo del PDF e' gia' selezionabile, l'app prova prima l'estrazione diretta senza OCR.
- `pdf2image` resta utile per i PDF scansionati.
