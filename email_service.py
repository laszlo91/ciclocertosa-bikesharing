"""
Invio email transazionali: OTP via SMTP.
"""
import smtplib
import secrets
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config


class EmailError(Exception):
    """Sollevata quando l'invio email fallisce."""


def generate_otp() -> str:
    """Genera un codice OTP numerico a 6 cifre."""
    return str(secrets.randbelow(900000) + 100000)


def send_otp(to_email: str, otp_code: str) -> None:
    """
    Invia un'email con il codice OTP all'indirizzo specificato.
    Utilizza SMTP con STARTTLS (porta 587) o SSL (porta 465).
    Solleva EmailError in caso di errore di invio.
    """
    if not config.SMTP_CONFIGURED:
        raise EmailError(
            "Configurazione SMTP mancante. "
            "Imposta SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM nel file .env"
        )

    subject = "Il tuo codice di verifica"
    body = (
        f"Il tuo codice di verifica per Bikesharing di quartiere e': {otp_code}\n\n"
        "Il codice e' valido per questa sessione.\n"
        "Se non hai richiesto questo codice, ignora questa email."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if config.SMTP_PORT == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx, timeout=10) as server:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM, to_email, msg.as_string())
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()  # RFC 3207 §4: re-issue EHLO dopo STARTTLS
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM, to_email, msg.as_string())
    except smtplib.SMTPException as exc:
        raise EmailError(f"Invio non riuscito: {exc}") from exc
    except OSError as exc:
        raise EmailError(f"Connessione SMTP fallita: {exc}") from exc


def send_booking_confirmation(
    to_email: str, bike_label: str, estimated_return_at: str
) -> None:
    """
    Invia un'email di conferma prenotazione all'utente.
    Non bloccante: se SMTP non configurato ritorna silenziosamente.
    Solleva EmailError in caso di errore di invio.
    """
    if not config.SMTP_CONFIGURED:
        return

    from datetime import datetime as _dt

    try:
        dt_str = _dt.fromisoformat(estimated_return_at).strftime("%d/%m/%Y alle %H:%M")
    except (ValueError, TypeError):
        dt_str = estimated_return_at

    subject = "Conferma prenotazione bici"
    body = (
        f"La tua prenotazione e' confermata.\n\n"
        f"Bici: {bike_label}\n"
        f"Restituzione indicativa: {dt_str}\n\n"
        "Ti chiediamo di rispettare la bici e di riportarla entro l'orario indicato.\n"
        "Altre persone del quartiere fanno affidamento su queste biciclette.\n\n"
        "Grazie."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if config.SMTP_PORT == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx, timeout=10) as server:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM, to_email, msg.as_string())
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM, to_email, msg.as_string())
    except smtplib.SMTPException as exc:
        raise EmailError(f"Invio conferma non riuscito: {exc}") from exc
    except OSError as exc:
        raise EmailError(f"Connessione SMTP fallita: {exc}") from exc