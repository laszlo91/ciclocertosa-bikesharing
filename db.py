"""
Layer di accesso dati SQLite.
Schema: tabelle bikes, bookings, emails (da stack.md).
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

import config


class BikeUnavailableError(Exception):
    """Sollevata quando la bici non è più disponibile al momento della prenotazione."""


@contextmanager
def _get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Crea le tabelle se non esistono."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bikes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                label       TEXT NOT NULL,
                status      TEXT NOT NULL CHECK(status IN ('available', 'unavailable')),
                unlock_code TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                bike_id             INTEGER NOT NULL REFERENCES bikes(id),
                user_email          TEXT NOT NULL,
                estimated_return_at DATETIME NOT NULL,
                booked_at           DATETIME NOT NULL
            );

            CREATE TABLE IF NOT EXISTS emails (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email        TEXT UNIQUE NOT NULL,
                verified     INTEGER NOT NULL DEFAULT 0,
                first_seen_at DATETIME NOT NULL
            );
        """)
        conn.commit()


def get_available_bikes() -> list[sqlite3.Row]:
    """Restituisce tutte le bici con status='available'."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, label FROM bikes WHERE status = 'available' ORDER BY id"
        ).fetchall()


def get_bike_by_id(bike_id: int) -> Optional[sqlite3.Row]:
    """Restituisce la bici con l'id dato, o None se non esiste."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, label, status, unlock_code FROM bikes WHERE id = ?",
            (bike_id,),
        ).fetchone()


def get_email(email: str) -> Optional[sqlite3.Row]:
    """Restituisce il record email, o None se non esiste."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, email, verified FROM emails WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()


def upsert_email(email: str, verified: bool) -> None:
    """Inserisce o aggiorna il record email."""
    # Timezone naive UTC per coerenza con estimated_return_at (P5)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    email = email.lower().strip()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO emails (email, verified, first_seen_at)
            VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET verified = MAX(emails.verified, excluded.verified)
            """,
            (email, 1 if verified else 0, now),
        )
        conn.commit()


def create_booking(bike_id: int, user_email: str, estimated_return_at: str) -> None:
    """
    Crea una prenotazione e imposta la bici come non disponibile.
    Transazione atomica: se la bici è già unavailable solleva BikeUnavailableError.
    """
    # Timezone naive UTC per coerenza con estimated_return_at (P5)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE bikes SET status = 'unavailable' WHERE id = ? AND status = 'available'",
            (bike_id,),
        )
        if cur.rowcount != 1:
            raise BikeUnavailableError(f"Bici {bike_id} non più disponibile")
        conn.execute(
            """
            INSERT INTO bookings (bike_id, user_email, estimated_return_at, booked_at)
            VALUES (?, ?, ?, ?)
            """,
            (bike_id, user_email.lower().strip(), estimated_return_at, now),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Funzioni admin (CAP-5)
# ---------------------------------------------------------------------------

class BikeNotFoundError(Exception):
    """Sollevata quando la bici con l'id dato non esiste."""


def list_all_bikes() -> list[sqlite3.Row]:
    """Restituisce tutte le bici (tutti i campi), ordinate per id."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, label, status, unlock_code FROM bikes ORDER BY id"
        ).fetchall()


def update_bike_status(bike_id: int, status: str) -> None:
    """Imposta lo status della bici. Solleva BikeNotFoundError se non esiste."""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE bikes SET status = ? WHERE id = ?",
            (status, bike_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise BikeNotFoundError(f"Bici {bike_id} non trovata")


def update_bike_unlock_code(bike_id: int, code: str) -> None:
    """Aggiorna il codice di sblocco della bici. Solleva BikeNotFoundError se non esiste."""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE bikes SET unlock_code = ? WHERE id = ?",
            (code, bike_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise BikeNotFoundError(f"Bici {bike_id} non trovata")


def get_last_n_bookings(n: int) -> list[sqlite3.Row]:
    """Restituisce le ultime n prenotazioni (JOIN con bikes), ordinate per booked_at DESC."""
    with _get_conn() as conn:
        return conn.execute(
            """
            SELECT bk.id, bk.bike_id, b.label AS bike_label,
                   bk.user_email, bk.estimated_return_at, bk.booked_at
            FROM bookings bk
            JOIN bikes b ON b.id = bk.bike_id
            ORDER BY bk.booked_at DESC
            LIMIT ?
            """,
            (n,),
        ).fetchall()


def add_bike(label: str, unlock_code: str) -> int:
    """Inserisce una nuova bici con status='available'. Restituisce l'id assegnato."""
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO bikes (label, status, unlock_code) VALUES (?, 'available', ?)",
            (label, unlock_code),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


def remove_bike(bike_id: int) -> None:
    """
    Rimuove la bici in un'unica transazione atomica.
    Solleva BikeNotFoundError se non esiste,
    BikeUnavailableError se status='unavailable' o ha prenotazioni collegate (FK constraint).
    BEGIN IMMEDIATE blocca scritture concorrenti tra SELECT e DELETE (P2).
    """
    with _get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status FROM bikes WHERE id = ?", (bike_id,)
        ).fetchone()
        if row is None:
            raise BikeNotFoundError(f"Bici {bike_id} non trovata")
        if row["status"] == "unavailable":
            raise BikeUnavailableError(f"Bici {bike_id} è attualmente unavailable — impossibile rimuovere")
        try:
            conn.execute("DELETE FROM bikes WHERE id = ?", (bike_id,))
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise BikeUnavailableError(
                f"Bici {bike_id} ha prenotazioni collegate — impossibile rimuovere"
            ) from exc


def ping_db() -> None:
    """Esegue una query minimale per verificare la raggiungibilità del DB."""
    with _get_conn() as conn:
        conn.execute("SELECT 1")


def restore_overdue_bikes() -> int:
    """
    Ripristina a 'available' le bici unavailable la cui prenotazione più recente
    ha estimated_return_at strettamente antecedente a oggi (00:00 ora locale).

    Usa MAX(booked_at) per identificare la prenotazione attiva — gestisce
    correttamente bici ripristinate manualmente e poi riprenotate.

    Restituisce il numero di bici ripristinate. Idempotente: chiamate successive
    sullo stesso stato restituiscono 0.
    """
    with _get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE bikes SET status = 'available'
            WHERE status = 'unavailable'
            AND id IN (
                SELECT b.bike_id
                FROM bookings b
                INNER JOIN (
                    SELECT bike_id, MAX(booked_at) AS max_booked_at
                    FROM bookings
                    GROUP BY bike_id
                ) latest ON b.bike_id = latest.bike_id
                         AND b.booked_at = latest.max_booked_at
                WHERE DATE(b.estimated_return_at) < DATE('now', 'localtime')
            )
            """
        )
        conn.commit()
        return cur.rowcount

