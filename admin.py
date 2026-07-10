"""
Layer Admin — CAP-5.

FastAPI app con Swagger UI (/docs) protetta da HTTP Basic Auth.
Credenziali caricate da secrets/admin-credentials.env.

Avvio:
    uvicorn admin:app --port 8001 --reload
"""
import os
import secrets as _secrets
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Annotated, Optional

from dotenv import dotenv_values
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

import db

ASSETS_DIR = Path(__file__).parent / "assets"
_ALLOWED_IMG_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_ALLOWED_IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# ---------------------------------------------------------------------------
# Credenziali admin
# ---------------------------------------------------------------------------

_CREDS_PATH = os.path.join(os.path.dirname(__file__), "secrets", "admin-credentials.env")
_creds_raw = dotenv_values(_CREDS_PATH)

ADMIN_USERS: list[tuple[str, str]] = [
    (_creds_raw.get(f"ADMIN_USER_{i}", ""), _creds_raw.get(f"ADMIN_PASS_{i}", ""))
    for i in range(1, 4)
]

if any(not user or not pw for user, pw in ADMIN_USERS):
    raise RuntimeError(
        f"Credenziali admin incomplete o file mancante: {_CREDS_PATH}. "
        "Verificare che ADMIN_USER_1/PASS_1 .. _3 siano presenti."
    )

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Bikesharing Admin API",
    description="Gestione parco bici — richiede HTTP Basic Auth su tutti gli endpoint.",
    version="1.0.0",
)

_security = HTTPBasic()


def _verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(_security)],
) -> HTTPBasicCredentials:
    """
    Confronta le credenziali con tutti gli utenti admin usando secrets.compare_digest.
    Il loop NON va in short-circuit su una corrispondenza parziale — previene timing attacks
    e username enumeration.
    """
    valid = False
    for user, pw in ADMIN_USERS:
        u_ok = _secrets.compare_digest(credentials.username.encode(), user.encode())
        p_ok = _secrets.compare_digest(credentials.password.encode(), pw.encode())
        if u_ok and p_ok:
            valid = True
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials


Auth = Annotated[HTTPBasicCredentials, Depends(_verify_credentials)]

# ---------------------------------------------------------------------------
# Schemi Pydantic
# ---------------------------------------------------------------------------


class BikeCreate(BaseModel):
    label: str = Field(..., min_length=1, description="Nome/etichetta della bici")
    unlock_code: str = Field(..., min_length=1, description="Codice del catenaccio")


class BikeStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(available|unavailable)$", description="Nuovo status della bici")


class BikeCodeUpdate(BaseModel):
    unlock_code: str = Field(..., min_length=1, description="Nuovo codice di sblocco")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@app.get("/health", summary="Health check")
def health(_: Auth) -> dict:
    """Verifica la raggiungibilità del DB SQLite."""
    try:
        db.ping_db()
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"DB non raggiungibile: {exc}",
        ) from exc


@app.get("/bikes", summary="Elenco tutte le bici")
def list_bikes(_: Auth) -> list[dict]:
    """Restituisce tutte le bici con id, label, status, unlock_code."""
    rows = db.list_all_bikes()
    return [dict(r) for r in rows]


@app.post("/bikes", status_code=status.HTTP_201_CREATED, summary="Aggiungi bici")
async def add_bike(
    _: Auth,
    label: str = Form(..., min_length=1, description="Nome/etichetta della bici"),
    unlock_code: str = Form(..., min_length=1, description="Codice del catenaccio"),
    photo: Optional[UploadFile] = File(None, description="Foto della bici (opzionale; jpg/png/gif/webp)"),
) -> dict:
    """Inserisce una nuova bici con status='available'. La foto e' opzionale."""
    photo_filename: Optional[str] = None
    if photo and photo.filename:
        content_type = photo.content_type or ""
        if content_type not in _ALLOWED_IMG_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Il file caricato non e' un'immagine valida. Usa jpg, png, gif o webp.",
            )
        ext = Path(photo.filename).suffix.lower()
        if ext not in _ALLOWED_IMG_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Estensione '{ext}' non supportata. Usa jpg, png, gif o webp.",
            )
        ASSETS_DIR.mkdir(exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest = ASSETS_DIR / safe_name
        with dest.open("wb") as buf:
            shutil.copyfileobj(photo.file, buf)
        photo_filename = safe_name

    new_id = db.add_bike(label=label, unlock_code=unlock_code, photo_url=photo_filename)
    return {"id": new_id, "label": label, "unlock_code": unlock_code, "status": "available", "photo_url": photo_filename}


@app.delete("/bikes/{bike_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Rimuovi bici")
def remove_bike(bike_id: int, _: Auth) -> Response:
    """
    Rimuove la bici. Errore 409 se la bici è unavailable (potenzialmente in uso).
    Errore 404 se non esiste.
    """
    try:
        db.remove_bike(bike_id)
    except db.BikeNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bici {bike_id} non trovata")
    except db.BikeUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bici {bike_id} è unavailable (in uso) — impossibile rimuovere",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.patch("/bikes/{bike_id}/status", summary="Cambia stato bici")
def change_bike_status(bike_id: int, body: BikeStatusUpdate, _: Auth) -> dict:
    """Imposta lo status della bici ('available' o 'unavailable')."""
    try:
        db.update_bike_status(bike_id=bike_id, status=body.status)
    except db.BikeNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bici {bike_id} non trovata")
    return {"id": bike_id, "status": body.status}


@app.patch("/bikes/{bike_id}/code", summary="Aggiorna codice sblocco")
def change_bike_code(bike_id: int, body: BikeCodeUpdate, _: Auth) -> dict:
    """Aggiorna il codice del catenaccio per la bici specificata."""
    try:
        db.update_bike_unlock_code(bike_id=bike_id, code=body.unlock_code)
    except db.BikeNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bici {bike_id} non trovata")
    return {"id": bike_id, "unlock_code": body.unlock_code}


@app.get("/bookings", summary="Ultime N prenotazioni")
def last_bookings(
    _: Auth,
    n: int = Query(default=50, ge=1, le=10_000, description="Numero massimo di prenotazioni da restituire"),
) -> list[dict]:
    """Restituisce le ultime n prenotazioni ordinate per booked_at DESC."""
    rows = db.get_last_n_bookings(n)
    return [dict(r) for r in rows]


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("ADMIN_PORT", "8001"))
    uvicorn.run("admin:app", host="0.0.0.0", port=port, reload=False)
