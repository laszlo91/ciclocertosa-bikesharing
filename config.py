"""
Carica e valida la configurazione dell'app dalle variabili d'ambiente.
Usa python-dotenv per leggere un file .env se presente.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Percorso del file SQLite
DB_PATH: str = os.getenv("DB_PATH", "bikesharing.db")

# Configurazione SMTP
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
try:
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
except ValueError:
    SMTP_PORT = 587
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM: str = os.getenv("SMTP_FROM", "")

# Verifica che le variabili SMTP siano presenti (warn solo a runtime, non al caricamento del modulo)
SMTP_CONFIGURED: bool = all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM])

# URL del pannello admin
ADMIN_URL: str = os.getenv("ADMIN_URL", "http://localhost:8001/docs#/")
