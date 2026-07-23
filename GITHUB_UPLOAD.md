# 🚀 Come Caricare il Progetto su GitHub

## Metodo 1: Usando l'Interfaccia Web di GitHub (PIÙ FACILE)

### Passo 1: Crea un Nuovo Repository su GitHub

1. Vai su [GitHub](https://github.com) e accedi al tuo account
2. Clicca sul pulsante **"+"** in alto a destra
3. Seleziona **"New repository"**
4. Compila i campi:
   - **Repository name**: `document-extractor` (o il nome che preferisci)
   - **Description**: `Applicazione per l'estrazione automatica di dati da Visure Camerali e Documenti d'Identità`
   - **Public/Private**: Scegli se vuoi che sia pubblico o privato
   - **NON** selezionare "Initialize this repository with a README" (abbiamo già il nostro)
   - **NON** aggiungere .gitignore o license (li abbiamo già)
5. Clicca su **"Create repository"**

### Passo 2: Collega il Repository Locale a GitHub

Dopo aver creato il repository, GitHub ti mostrerà una pagina con le istruzioni. Segui questi comandi nel terminale:

**Windows (PowerShell o CMD):**
```bash
cd C:\percorso\alla\cartella\document-extractor
git remote add origin https://github.com/TUO_USERNAME/document-extractor.git
git branch -M main
git push -u origin main
```

**macOS/Linux:**
```bash
cd /percorso/alla/cartella/document-extractor
git remote add origin https://github.com/TUO_USERNAME/document-extractor.git
git branch -M main
git push -u origin main
```

**Nota**: Sostituisci `TUO_USERNAME` con il tuo username GitHub e `document-extractor` con il nome del repository che hai scelto.

### Passo 3: Inserisci le Credenziali

Ti verrà chiesto di autenticarti:
- **Username**: Il tuo username GitHub
- **Password**: Il tuo Personal Access Token (NON la password del tuo account!)

#### Come Creare un Personal Access Token:

1. Vai su GitHub → Clicca sulla tua foto profilo → **Settings**
2. Scorri in basso e clicca su **Developer settings**
3. Clicca su **Personal access tokens** → **Tokens (classic)**
4. Clicca su **Generate new token** → **Generate new token (classic)**
5. Dai un nome al token (es: "Document Extractor Upload")
6. Seleziona lo scope **"repo"** (permette di accedere ai repository)
7. Clicca su **Generate token**
8. **COPIA IL TOKEN** (lo vedrai una sola volta!)
9. Usa questo token come password quando richiesto

---

## Metodo 2: Usando GitHub Desktop (FACILE)

### Passo 1: Scarica GitHub Desktop

1. Vai su [desktop.github.com](https://desktop.github.com/)
2. Scarica e installa GitHub Desktop
3. Accedi con il tuo account GitHub

### Passo 2: Aggiungi il Repository Locale

1. Apri GitHub Desktop
2. Clicca su **File** → **Add local repository**
3. Seleziona la cartella `document-extractor`
4. Clicca su **Add repository**

### Passo 3: Pubblica su GitHub

1. Clicca sul pulsante **"Publish repository"** in alto
2. Scegli il nome del repository
3. Aggiungi una descrizione (opzionale)
4. Deseleziona "Keep this code private" se vuoi renderlo pubblico
5. Clicca su **Publish repository**

---

## Metodo 3: Usando Git dalla Linea di Comando (AVANZATO)

Se hai già dimestichezza con Git:

```bash
# Naviga nella cartella del progetto
cd /percorso/document-extractor

# Verifica lo stato
git status

# Crea il repository su GitHub (via browser)
# Poi esegui questi comandi:

# Aggiungi il remote
git remote add origin https://github.com/TUO_USERNAME/document-extractor.git

# Rinomina il branch in main (opzionale, Git moderno usa 'main')
git branch -M main

# Pusha il codice
git push -u origin main
```

---

## ✅ Verifica che Funzioni

Dopo aver caricato il progetto:

1. Vai su `https://github.com/TUO_USERNAME/document-extractor`
2. Dovresti vedere tutti i file del progetto
3. Il README.md verrà visualizzato automaticamente nella home del repository

---

## 📝 Aggiornamenti Futuri

Quando modifichi il codice e vuoi aggiornare GitHub:

```bash
# Aggiungi i file modificati
git add .

# Fai il commit con un messaggio descrittivo
git commit -m "Descrizione delle modifiche"

# Pusha su GitHub
git push
```

---

## 🔐 Sicurezza

**IMPORTANTE:**
- **NON** caricare mai file con dati sensibili (documenti reali, password, ecc.)
- Il `.gitignore` è già configurato per escludere file PDF, immagini e Excel
- Se hai documenti di test, aggiungili a `.gitignore`

### Segreti e chiave Google Vision

- In locale usa un file `.env` con `GOOGLE_VISION_API_KEY=...`
- Su Streamlit Cloud usa `st.secrets` tramite `.streamlit/secrets.toml` nel deploy
- Se usi GitHub Actions o altri workflow, salva la chiave nei **Repository secrets** di GitHub con il nome `GOOGLE_VISION_API_KEY`
- Non committare mai il valore reale della chiave nel repository

---

## 🆘 Problemi Comuni

### "Permission denied (publickey)"

**Soluzione**: Usa HTTPS invece di SSH:
```bash
git remote set-url origin https://github.com/TUO_USERNAME/document-extractor.git
```

### "Authentication failed"

**Soluzione**: 
1. Assicurati di usare un Personal Access Token, NON la password del tuo account
2. Verifica che il token abbia i permessi "repo"

### "Repository not found"

**Soluzione**:
1. Verifica che il repository esista su GitHub
2. Controlla di aver scritto correttamente l'URL
3. Verifica di avere i permessi per accedere al repository

### File troppo grandi

**Soluzione**:
Se hai file > 100MB, GitHub li bloccherà. Verifica con:
```bash
find . -size +100M
```
E aggiungi questi file a `.gitignore`

---

## 📊 Dopo il Caricamento

Una volta caricato su GitHub, puoi:

1. **Condividere il link** con colleghi e clienti
2. **Creare una Release** per versioni stabili
3. **Abilitare GitHub Pages** per la documentazione
4. **Aggiungere Issues** per tracciare bug e feature
5. **Accettare Pull Requests** da collaboratori

---

## 🎯 Best Practices

1. **Commit frequenti** con messaggi descrittivi
2. **Non committare** file sensibili o temporanei
3. **Tagga le versioni** importanti (v1.0, v1.1, ecc.)
4. **Documenta** ogni modifica importante nel README
5. **Testa** prima di pushare

---

## 📧 Supporto

Se hai problemi:
1. Controlla la [documentazione ufficiale di GitHub](https://docs.github.com)
2. Verifica su [GitHub Community](https://github.community)
3. Cerca su [Stack Overflow](https://stackoverflow.com/questions/tagged/github)

---

**Buon lavoro! 🚀**
