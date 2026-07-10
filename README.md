# Bikesharing Ciclocertosa

Webapp mobile-first che consente agli utenti del quartiere di prenotare e sbloccare le biciclette della ciclofficina in autonomia. Realizzata in Python con Streamlit (frontend wizard) e FastAPI (pannello admin).

---

## Indice

1. [Requisiti](#requisiti)
2. [Setup rapido](#setup-rapido)
3. [Avvio](#avvio)
4. [Scheduler giornaliero](#scheduler-giornaliero)
5. [Struttura del progetto](#struttura-del-progetto)

---

## Requisiti

- **Python 3.10 o superiore**
- pip
- Un account SMTP per l'invio dei codici OTP via email (es. Gmail, Autistici, ecc.)

---

## Setup rapido

### 1. Clona il repository

```bash
git clone <url-del-repo>
cd bikesharing
```

### 2. Crea e attiva il virtualenv

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Installa le dipendenze

```bash
pip install -r requirements.txt
```

### 4. Configura le variabili d'ambiente

Crea un file `.env` nella radice del progetto (è già in `.gitignore`):

```dotenv
# Percorso del file SQLite (default: bikesharing.db nella working directory)
DB_PATH=bikesharing.db

# Configurazione SMTP per l'invio dei codici OTP
SMTP_HOST=smtp.tuoprovider.com
SMTP_PORT=587
SMTP_USER=tuo@indirizzo.email
SMTP_PASSWORD=la-tua-password
SMTP_FROM=tuo@indirizzo.email

# URL pannello admin (da aggiornare in produzione)
ADMIN_URL=http://localhost:8001/docs#/
```

### 5. Configura le credenziali admin

Crea prima la directory `secrets/` (non tracciata da git):

```bash
# Linux / macOS
mkdir -p secrets

# Windows
New-Item -ItemType Directory -Force -Path secrets
```

Poi crea il file `secrets/admin-credentials.env` (è già in `.gitignore`). Puoi partire dal template qui sotto — sostituisci username e password con valori sicuri:

```dotenv
# File NON da committare. Contiene le credenziali HTTP Basic Auth del pannello admin.
# Ruotare le password periodicamente.

ADMIN_USER_1=admin_nomeutente
ADMIN_PASS_1=password-sicura-1

ADMIN_USER_2=admin_nomeutente2
ADMIN_PASS_2=password-sicura-2

ADMIN_USER_3=admin_nomeutente3
ADMIN_PASS_3=password-sicura-3
```

> **Nota:** sono supportati esattamente 3 utenti admin (`_1`, `_2`, `_3`). Tutti e tre devono essere compilati.

### 6. Aggiungi il logo (facoltativo)

Copia il logo dell'associazione in `assets/logo.png`. Se il file non è presente, l'app si avvia comunque senza mostrarlo.

---

## Avvio

L'applicazione è composta da **due processi separati** che vanno avviati in parallelo.

### Frontend — Streamlit

```bash
streamlit run app.py
```

L'app sarà disponibile su [http://localhost:8501](http://localhost:8501).

### Pannello admin — FastAPI

```bash
uvicorn admin:app --port 8001 --reload
```

> `--reload` abilita il ricaricamento automatico ad ogni modifica del codice. **Rimuoverlo in produzione.**

Lo Swagger UI sarà disponibile su [http://localhost:8001/docs](http://localhost:8001/docs).  
L'accesso richiede HTTP Basic Auth con le credenziali configurate in `secrets/admin-credentials.env`.

> **Nota:** il database viene inizializzato dal frontend Streamlit all'avvio (`db.init_db()`). Avviare prima `streamlit run app.py` per creare il database; il pannello admin presuppone che esista già.

### Aggiunta della prima bici

Dopo l'avvio, apri il pannello admin, autenticati e usa l'endpoint `POST /bikes` per aggiungere almeno una bicicletta prima di testare il wizard.

---

## Scheduler giornaliero

Lo script `scheduler.py` ripristina automaticamente lo stato `available` per le bici il cui orario di restituzione stimato è scaduto.

**Linux / macOS (cron) — ogni giorno alle 07:00:**

```cron
0 7 * * * cd /percorso/bikesharing && /percorso/venv/bin/python3 scheduler.py
```

**Windows — Utilità di pianificazione:**

- Trigger: Giornaliero, ore 07:00
- Azione: `C:\percorso\venv\Scripts\python.exe C:\percorso\bikesharing\scheduler.py`
- Avvia in: `C:\percorso\bikesharing`

Puoi anche eseguirlo manualmente per test:

```bash
python scheduler.py
```

---

## Struttura del progetto

```
bikesharing/
├── app.py                  # Frontend Streamlit (wizard prenotazione)
├── admin.py                # Pannello admin FastAPI (Swagger + HTTP Basic Auth)
├── db.py                   # Layer di accesso dati SQLite
├── config.py               # Caricamento configurazione da .env
├── email_service.py        # Invio email OTP
├── scheduler.py            # Script manutenzione giornaliera
├── requirements.txt        # Dipendenze Python
├── .env                    # Variabili d'ambiente (NON in git)
├── bikesharing.db          # Database SQLite generato a runtime (NON in git)
├── .streamlit/
│   └── config.toml         # Tema Streamlit (dark, colori brand Ciclocertosa)
├── assets/
│   └── logo.png            # Logo associazione (da aggiungere manualmente)
└── secrets/
    └── admin-credentials.env  # Credenziali admin (NON in git)
```

---

## Note di sicurezza

- I file `.env` e `secrets/admin-credentials.env` sono esclusi dal repository via `.gitignore`. Non committarli mai.
- Le credenziali admin vengono confrontate con `secrets.compare_digest` per prevenire timing attacks.
- Ruotare le password admin periodicamente.
