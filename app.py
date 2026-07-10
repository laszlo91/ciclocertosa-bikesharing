"""
App Streamlit — Wizard prenotazione bici.
State machine: landing -> email -> otp -> return_time -> disclaimer -> unlock
"""
import base64
import html
import os
import re
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components

import config
import db
import email_service
from db import BikeUnavailableError
from email_service import EmailError

# ---------------------------------------------------------------------------
# Stile: DM Sans, near-black, rosso Ciclocertosa, gerarchia pulsanti
# ---------------------------------------------------------------------------
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', Arial, sans-serif !important;
}

/* ---------- layout ---------- */
.stApp {
    background-color: #111111;
}

/* ---------- typography ---------- */
h1, h2, h3, h4, h5, h6 {
    color: #FFFFFF !important;
    letter-spacing: -0.02em;
}
p, label, span, div {
    color: #FFFFFF !important;
}

/* ---------- inputs ---------- */
.stTextInput > div > div > input {
    background-color: #1C1C1C;
    color: #FFFFFF;
    border: 2px solid #444444;
    border-radius: 6px;
    font-size: 1rem;
}
.stTextInput > div > div > input:focus {
    border-color: #D62828 !important;
    box-shadow: 0 0 0 1px #D62828;
}

/* ---------- buttons (base) ---------- */
.stButton > button {
    font-weight: 700;
    font-size: 1rem;
    border-radius: 6px;
    padding: 0.65rem 1.4rem;
    width: 100%;
    box-sizing: border-box;
    transition: opacity 0.15s;
}
/* primary */
[data-testid="baseButton-primary"] {
    background-color: #D62828 !important;
    color: #FFFFFF !important;
    border: 2px solid #D62828 !important;
}
[data-testid="baseButton-primary"]:hover {
    background-color: #B82020 !important;
    border-color: #B82020 !important;
}
/* secondary */
[data-testid="baseButton-secondary"] {
    background-color: transparent !important;
    color: #FFFFFF !important;
    border: 2px solid #555555 !important;
}
[data-testid="baseButton-secondary"]:hover {
    border-color: #FFFFFF !important;
    background-color: rgba(255,255,255,0.06) !important;
}

/* ---------- checkbox ---------- */
.stCheckbox label span {
    color: #FFFFFF !important;
}

/* ---------- progress ---------- */
.progress-wrap {
    margin: 0.2rem 0 1.4rem 0;
}
.progress-track {
    background-color: #333333;
    border-radius: 4px;
    height: 5px;
    width: 100%;
    overflow: hidden;
}
.progress-fill {
    background-color: #D62828;
    height: 100%;
    border-radius: 4px;
}
.progress-text {
    display: block;
    font-size: 0.78rem;
    color: #888888 !important;
    margin-top: 0.3rem;
}

/* ---------- bike cards ---------- */
.bike-card-wrap {
    background-color: #1C1C1C;
    border: 2px solid #2A2A2A;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 1rem;
}
.bike-card-wrap:hover {
    border-color: #D62828;
}
.bike-card-img-wrap {
    display: flex;
    justify-content: center;
    padding: 1.2rem 1rem 0 1rem;
    background-color: #1C1C1C;
}
.bike-card-img {
    width: 160px;
    height: 160px;
    border-radius: 50%;
    object-fit: cover;
    display: block;
}
.bike-card-no-img {
    width: 160px;
    height: 160px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: #2A2A2A;
    color: #666666 !important;
    font-size: 0.85rem;
    font-style: italic;
    text-align: center;
}
.bike-card-body {
    padding: 0.5rem 1rem 0.75rem 1rem;
}
.bike-card-name {
    font-size: 1.05rem;
    font-weight: 400;
    font-style: italic;
    color: #FFFFFF !important;
    margin: 0.4rem 0 0 0;
    text-align: center;
}

/* ---------- logo ---------- */
.logo-wrap {
    text-align: center;
    margin-bottom: 1rem;
}
.logo-img {
    width: 90px;
    height: 90px;
    border-radius: 50%;
    object-fit: cover;
    display: block;
    margin: 0 auto;
}

/* ---------- unlock code ---------- */
.unlock-code {
    font-size: clamp(1.6rem, 7vw, 2.8rem);
    font-weight: 700;
    letter-spacing: 0.12em;
    color: #D62828 !important;
    text-align: center;
    padding: 1.2rem;
    border: 3px solid #D62828;
    border-radius: 10px;
    background-color: #1C1C1C;
    overflow-wrap: break-word;
    word-break: break-all;
    max-width: 100%;
    box-sizing: border-box;
}
.copy-btn {
    display: block;
    width: 100%;
    margin-top: 0.75rem;
    padding: 0.65rem 1.4rem;
    background-color: transparent;
    color: #FFFFFF;
    border: 2px solid #555555;
    border-radius: 6px;
    font-family: inherit;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    box-sizing: border-box;
    transition: border-color 0.15s, background-color 0.15s;
}
.copy-btn:hover {
    border-color: #FFFFFF;
    background-color: rgba(255,255,255,0.06);
}

/* ---------- messages ---------- */
.error-msg {
    color: #FF6B6B !important;
    font-weight: 700;
}
.info-msg {
    color: #6FCF97 !important;
}

/* ---------- admin link ---------- */
.admin-link-wrap {
    text-align: right;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #2A2A2A;
}
.admin-link {
    color: #888888 !important;
    font-size: 0.85rem;
    text-decoration: none;
    border: 1px solid #444444;
    padding: 0.3rem 0.75rem;
    border-radius: 4px;
    transition: color 0.15s, border-color 0.15s;
}
.admin-link:hover {
    color: #FFFFFF !important;
    border-color: #888888;
}
</style>
"""

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _reset(keep_step: str = "landing") -> None:
    """Azzera la session_state e torna alla landing."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["step"] = keep_step


def _go(step: str) -> None:
    st.session_state["step"] = step
    st.rerun()


# ---------------------------------------------------------------------------
# Helpers UI
# ---------------------------------------------------------------------------
_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")

_STEP_NUMS: dict[str, tuple[int, int]] = {
    "landing":     (1, 5),
    "email":       (2, 5),
    "otp":         (2, 5),
    "return_time": (3, 5),
    "disclaimer":  (4, 5),
    "unlock":      (5, 5),
}


def _get_logo_b64() -> str | None:
    """Carica il logo come base64."""
    if not os.path.exists(_LOGO_PATH):
        return None
    with open(_LOGO_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _show_logo() -> None:
    logo = _get_logo_b64()
    if logo:
        st.markdown(
            f'<div class="logo-wrap"><img src="data:image/png;base64,{logo}" alt="Ciclocertosa" class="logo-img"></div>',
            unsafe_allow_html=True,
        )


def _show_progress(step_name: str) -> None:
    current, total = _STEP_NUMS.get(step_name, (1, 5))
    pct = int(current / total * 100)
    st.markdown(
        f'<div class="progress-wrap">'
        f'<div class="progress-track"><div class="progress-fill" style="width:{pct}%"></div></div>'
        f'<span class="progress-text">Passo {current} di {total}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


_MIME_FROM_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}


def _bike_photo_html(photo_filename: str | None, label: str) -> str:
    """Carica la foto della bici da assets/ come base64 oppure restituisce il placeholder."""
    if not photo_filename:
        return '<div class="bike-card-img-wrap"><div class="bike-card-no-img">Foto non disponibile</div></div>'
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", photo_filename)
    if not os.path.exists(path):
        return '<div class="bike-card-img-wrap"><div class="bike-card-no-img">Foto non disponibile</div></div>'
    ext = os.path.splitext(photo_filename)[1].lower()
    mime = _MIME_FROM_EXT.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<div class="bike-card-img-wrap"><img src="data:{mime};base64,{b64}" alt="{html.escape(label)}" class="bike-card-img"></div>'


# ---------------------------------------------------------------------------
# Inizializzazione DB (una sola volta per processo)
# ---------------------------------------------------------------------------
@st.cache_resource
def _ensure_db():
    db.init_db()
    return True


_ensure_db()

st.set_page_config(
    page_title="Bikesharing della Ciclocertosa",
    page_icon=None,
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(STYLE, unsafe_allow_html=True)

if "step" not in st.session_state:
    st.session_state["step"] = "landing"

step = st.session_state["step"]

# ---------------------------------------------------------------------------
# Step 1 — Landing: lista bici disponibili
# ---------------------------------------------------------------------------
if step == "landing":
    # Gestione selezione bici da click su immagine (query param ?bike_select=ID)
    _bike_select = st.query_params.get("bike_select")
    if _bike_select:
        st.query_params.clear()
        _all_bikes = db.get_available_bikes()
        _chosen = next((b for b in _all_bikes if str(b["id"]) == _bike_select), None)
        if _chosen:
            st.session_state["bike_id"] = _chosen["id"]
            st.session_state["bike_label"] = _chosen["label"]
            _go("email")

    _show_logo()
    _show_progress("landing")
    st.title("Bikesharing della Ciclocertosa")
    st.write("Seleziona una bici disponibile per iniziare la prenotazione.")

    # Mostra errore race condition se proveniente da step 4
    if st.session_state.pop("booking_error", False):
        st.markdown(
            '<p class="error-msg">La bici selezionata non e\' piu\' disponibile. Scegline un\'altra.</p>',
            unsafe_allow_html=True,
        )

    bikes = db.get_available_bikes()

    if not bikes:
        st.markdown('<p class="info-msg">Nessuna bici disponibile al momento.</p>', unsafe_allow_html=True)
    else:
        for bike in bikes:
            img_html = _bike_photo_html(bike["photo_url"], bike["label"])
            bike_id_safe = int(bike["id"])
            # <a href> è preservato dal sanitizer HTML di Streamlit; onclick viene rimosso.
            st.markdown(
                f'<a href="/?bike_select={bike_id_safe}" style="text-decoration:none">'
                f'<div class="bike-card-wrap">'
                f"{img_html}"
                f'<div class="bike-card-body"><p class="bike-card-name"><em>\u201c{html.escape(bike["label"])}\u201d</em></p></div>'
                f'</div></a>',
                unsafe_allow_html=True,
            )

    # Pulsante Area Admin — os.getenv usato direttamente per evitare cache stale del modulo config
    _admin_url = html.escape(os.getenv("ADMIN_URL", "http://localhost:8001/docs#/"), quote=True)
    st.markdown(
        f'<div class="admin-link-wrap">'
        f'<a href="{_admin_url}" target="_blank" class="admin-link">Area Admin</a>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Step 2 — Email
# ---------------------------------------------------------------------------
elif step == "email":
    _show_logo()
    _show_progress("email")
    st.title("Il tuo indirizzo email")
    st.write(f"Bici selezionata: **{st.session_state.get('bike_label', '')}**")

    if st.session_state.pop("otp_max_attempts", False):
        st.markdown(
            '<p class="error-msg">Troppi tentativi errati. Inserisci la tua email per ricevere un nuovo codice.</p>',
            unsafe_allow_html=True,
        )

    email_input = st.text_input("Email", key="email_input", placeholder="nome@esempio.it")

    if st.button("Avanti", type="primary"):
        email = email_input.strip().lower()
        if not EMAIL_RE.match(email):
            st.markdown('<p class="error-msg">Inserisci un indirizzo email valido.</p>', unsafe_allow_html=True)
        else:
            st.session_state["user_email"] = email
            record = db.get_email(email)
            if record and record["verified"] == 1:
                # Email conosciuta: salta OTP
                _go("return_time")
            else:
                # Email sconosciuta: genera e invia OTP
                otp = email_service.generate_otp()
                st.session_state["otp_code"] = otp
                st.session_state["otp_attempt"] = 0
                try:
                    email_service.send_otp(email, otp)
                    _go("otp")
                except EmailError:
                    st.markdown('<p class="error-msg">Invio non riuscito, riprovare.</p>', unsafe_allow_html=True)

    if st.button("Indietro", key="back_email", type="secondary"):
        _go("landing")

# ---------------------------------------------------------------------------
# Step 2b — OTP
# ---------------------------------------------------------------------------
elif step == "otp":
    _show_logo()
    _show_progress("otp")
    st.title("Verifica email")
    email = st.session_state.get("user_email", "")
    st.write(f"Abbiamo inviato un codice a **{email}**. Inseriscilo qui sotto.")

    # Attiva tastiera numerica su mobile
    components.html(
        "<script>window.parent.document.querySelectorAll('input[type=\"text\"]')"
        ".forEach(function(i){i.setAttribute('inputmode','numeric');i.setAttribute('pattern','[0-9]*');});</script>",
        height=0,
    )

    # Cambiare la key svuota il campo (Streamlit widget reset pattern)
    otp_attempt = st.session_state.get("otp_attempt", 0)
    otp_input = st.text_input(
        "Codice di verifica",
        key=f"otp_input_{otp_attempt}",
        max_chars=6,
        placeholder="123456",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Verifica", type="primary"):
            if otp_input.strip() == st.session_state.get("otp_code", ""):
                db.upsert_email(email, verified=True)
                del st.session_state["otp_code"]
                _go("return_time")
            else:
                # Incrementa il counter per svuotare il campo al prossimo rerun
                new_attempt = otp_attempt + 1
                st.session_state["otp_attempt"] = new_attempt
                if new_attempt >= 10:
                    # Cap raggiunto: resetta OTP e torna al passo email
                    st.session_state.pop("otp_code", None)
                    st.session_state.pop("otp_attempt", None)
                    st.session_state["otp_max_attempts"] = True
                    _go("email")
                else:
                    remaining = 10 - new_attempt
                    st.markdown(
                        f'<p class="error-msg">Codice errato. Riprova ({remaining} tentativi rimanenti).</p>',
                        unsafe_allow_html=True,
                    )

    with col2:
        if st.button("Invia nuovo codice", type="secondary"):
            otp = email_service.generate_otp()
            st.session_state["otp_code"] = otp
            st.session_state["otp_attempt"] = st.session_state.get("otp_attempt", 0) + 1
            try:
                email_service.send_otp(email, otp)
                st.markdown('<p class="info-msg">Nuovo codice inviato.</p>', unsafe_allow_html=True)
            except EmailError:
                st.markdown('<p class="error-msg">Invio non riuscito, riprovare.</p>', unsafe_allow_html=True)

    if st.button("Indietro", key="back_otp", type="secondary"):
        _go("email")

# ---------------------------------------------------------------------------
# Step 3 — Data e ora di restituzione
# ---------------------------------------------------------------------------
elif step == "return_time":
    _show_logo()
    _show_progress("return_time")
    st.title("Quando pensi di restituire la bici?")
    st.write("Indica una data e un orario indicativi. Non e' vincolante.")

    min_date = datetime.now().date()
    default_date = (datetime.now() + timedelta(hours=2)).date()

    return_date = st.date_input("Data di restituzione", value=default_date, min_value=min_date, key="return_date")
    return_time = st.time_input("Ora di restituzione", value=datetime.now().replace(hour=18, minute=0, second=0, microsecond=0).time(), key="return_time_input")

    if st.button("Avanti", type="primary"):
        if return_date is None or return_time is None:
            st.markdown('<p class="error-msg">Seleziona data e ora di restituzione.</p>', unsafe_allow_html=True)
        else:
            dt = datetime.combine(return_date, return_time)
            if dt <= datetime.now():
                st.markdown('<p class="error-msg">La data di restituzione non puo\' essere nel passato.</p>', unsafe_allow_html=True)
            else:
                st.session_state["estimated_return_at"] = dt.isoformat()
                _go("disclaimer")

    if st.button("Indietro", key="back_return", type="secondary"):
        _go("email")

# ---------------------------------------------------------------------------
# Step 4 — Avviso di responsabilita'
# ---------------------------------------------------------------------------
elif step == "disclaimer":
    _show_logo()
    _show_progress("disclaimer")
    st.title("Prima di procedere")
    st.markdown(
        """
**Ti chiediamo di rispettare questa bici e di riportarla.**

Altre persone del quartiere fanno affidamento su queste biciclette.
Riportarla entro l'orario indicato permette a tutti di usufruirne.
        """
    )

    agreed = st.checkbox("Ho letto e mi impegno a trattare la bici con cura e a riportarla entro l'orario indicato.")

    if st.button("Accetto e voglio il codice di sblocco", type="primary", disabled=not agreed):
        bike_id = st.session_state.get("bike_id")
        user_email = st.session_state.get("user_email")
        estimated_return_at = st.session_state.get("estimated_return_at")

        if not all([bike_id, user_email, estimated_return_at]):
            # Session state incompleta (es. refresh pagina): reset pulito alla landing
            _reset()
            st.rerun()

        try:
            db.create_booking(bike_id, user_email, estimated_return_at)
            try:
                email_service.send_booking_confirmation(
                    user_email,
                    st.session_state.get("bike_label", ""),
                    estimated_return_at,
                )
            except EmailError:
                pass  # non bloccante: prenotazione già creata
            _go("unlock")
        except BikeUnavailableError:
            # Redirect automatico alla landing con segnalazione errore (AC9)
            st.session_state["booking_error"] = True
            _go("landing")
        except Exception as exc:
            st.markdown(
                f'<p class="error-msg">Errore durante la prenotazione: {html.escape(str(exc))}</p>',
                unsafe_allow_html=True,
            )

    if st.button("Indietro", key="back_disclaimer", type="secondary"):
        _go("return_time")

# ---------------------------------------------------------------------------
# Step 5 — Codice di sblocco
# ---------------------------------------------------------------------------
elif step == "unlock":
    bike_id = st.session_state.get("bike_id")
    bike = db.get_bike_by_id(bike_id) if bike_id else None

    _show_logo()
    _show_progress("unlock")
    st.title("Prenotazione completata")

    if bike:
        st.write(f"Bici: **{bike['label']}**")
        st.write("Il codice per aprire il catenaccio e':")
        # HTML-escape del codice prima dell'iniezione (prevenzione XSS)
        safe_code_display = html.escape(str(bike["unlock_code"]))
        safe_code_attr = html.escape(str(bike["unlock_code"]), quote=True)
        st.markdown(
            f'<div class="unlock-code">{safe_code_display}</div>'
            f'<button class="copy-btn" data-code="{safe_code_attr}" '
            f'onclick="var b=this;navigator.clipboard.writeText(b.dataset.code).then(function(){{'
            f'b.textContent=\'Copiato!\';setTimeout(function(){{b.textContent=\'Copia codice\';}},2000);}});">'
            f'Copia codice</button>',
            unsafe_allow_html=True,
        )
        st.write("")
        estimated = st.session_state.get("estimated_return_at", "")
        if estimated:
            dt_str = datetime.fromisoformat(estimated).strftime("%d/%m/%Y alle %H:%M")
            st.write(f"Ricordati di riportare la bici entro il **{dt_str}**.")
    else:
        # Guard: dati mancanti o bici non trovata — torna alla landing
        st.markdown('<p class="error-msg">Dati prenotazione non trovati.</p>', unsafe_allow_html=True)

    st.write("")
    if st.button("Torna alla home", type="secondary"):
        _reset()
        st.rerun()
