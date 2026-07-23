# Guida Installazione OCR Google Vision

Questa guida spiega come configurare Google Vision per l'OCR su immagini e PDF scansionati.

## Requisiti

- Un progetto Google Cloud con Vision API attiva
- Una chiave API Google Vision
- Un file `.env` locale nella cartella del progetto

## Configurazione Locale

1. Crea un file `.env` nella root del progetto.
2. Inserisci questa riga:

```bash
GOOGLE_VISION_API_KEY=la_tua_chiave_api
```

3. Non caricare il file `.env` su GitHub.
4. Per la repo, usa un file `.env.example` come riferimento.

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
