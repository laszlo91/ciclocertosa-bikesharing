"""
App Streamlit — Wizard prenotazione bici.
State machine: landing -> email -> otp -> return_time -> disclaimer -> unlock
"""
import html
import re
from datetime import datetime, timedelta

import streamlit as st

import db
import email_service
from db import BikeUnavailableError
from email_service import EmailError

# ---------------------------------------------------------------------------
# Stile accessibilità: alto contrasto, font leggibile, zero emoji
# ---------------------------------------------------------------------------
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Atkinson Hyperlegible', Arial, sans-serif !important;
    background-color: #000000;
    color: #FFFFFF;
}
.stApp {
    background-color: #000000;
}
h1, h2, h3, h4, h5, h6 {
    color: #FFFFFF !important;
}
p, label, span, div {
    color: #FFFFFF !important;
}
.stButton > button {
    background-color: #FFDD00;
    color: #000000 !important;
    font-weight: 700;
    font-size: 1.1rem;
    border: 2px solid #FFDD00;
    border-radius: 6px;
    padding: 0.6rem 1.4rem;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
}
.stButton > button:hover, .stButton > button:focus {
    background-color: #FFFFFF;
    border-color: #FFFFFF;
    color: #000000 !important;
}
.stTextInput > div > div > input {
    background-color: #1A1A1A;
    color: #FFFFFF;
    border: 2px solid #FFDD00;
    border-radius: 4px;
    font-size: 1rem;
}
.bike-card {
    background-color: #1A1A1A;
    border: 2px solid #FFDD00;
    border-radius: 8px;
    padding: 1.2rem;
    margin-bottom: 0.8rem;
    cursor: pointer;
}
.unlock-code {
    font-size: clamp(1.4rem, 6vw, 2.4rem);
    font-weight: 700;
    letter-spacing: 0.1em;
    color: #FFDD00 !important;
    text-align: center;
    padding: 1.2rem;
    border: 3px solid #FFDD00;
    border-radius: 8px;
    background-color: #1A1A1A;
    overflow-wrap: break-word;
    word-break: break-all;
    max-width: 100%;
    box-sizing: border-box;
}
.error-msg {
    color: #FF6B6B !important;
    font-weight: 700;
}
.info-msg {
    color: #AAFFAA !important;
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
# Inizializzazione DB (una sola volta per processo)
# ---------------------------------------------------------------------------
@st.cache_resource
def _ensure_db():
    db.init_db()
    return True


_ensure_db()

st.set_page_config(
    page_title="Bikesharing di quartiere",
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
    st.title("Bikesharing di quartiere")
    st.write("Seleziona una bici disponibile per iniziare la prenotazione.")

    # Mostra errore race condition se proveniente da step 4
    if st.session_state.pop("booking_error", False):
        st.markdown(
            '<p class="error-msg">La bici selezionata non e\' piu\' disponibile. Scegline un\'altra.</p>',
            unsafe_allow_html=True,
        )

    bikes = db.get_available_bikes()

    if not bikes:
        st.markdown('<p class="info-msg">Nessuna bici disponibile</p>', unsafe_allow_html=True)
    else:
        for bike in bikes:
            if st.button(f"Bici: {bike['label']}", key=f"bike_{bike['id']}"):
                st.session_state["bike_id"] = bike["id"]
                st.session_state["bike_label"] = bike["label"]
                _go("email")

# ---------------------------------------------------------------------------
# Step 2 — Email
# ---------------------------------------------------------------------------
elif step == "email":
    st.title("Il tuo indirizzo email")
    st.write(f"Bici selezionata: **{st.session_state.get('bike_label', '')}**")

    if st.session_state.pop("otp_max_attempts", False):
        st.markdown(
            '<p class="error-msg">Troppi tentativi errati. Inserisci la tua email per ricevere un nuovo codice.</p>',
            unsafe_allow_html=True,
        )

    email_input = st.text_input("Email", key="email_input", placeholder="nome@esempio.it")

    if st.button("Avanti"):
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

    if st.button("Indietro", key="back_email"):
        _go("landing")

# ---------------------------------------------------------------------------
# Step 2b — OTP
# ---------------------------------------------------------------------------
elif step == "otp":
    st.title("Verifica email")
    email = st.session_state.get("user_email", "")
    st.write(f"Abbiamo inviato un codice a **{email}**. Inseriscilo qui sotto.")

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
        if st.button("Verifica"):
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
        if st.button("Invia nuovo codice"):
            otp = email_service.generate_otp()
            st.session_state["otp_code"] = otp
            st.session_state["otp_attempt"] = st.session_state.get("otp_attempt", 0) + 1
            try:
                email_service.send_otp(email, otp)
                st.markdown('<p class="info-msg">Nuovo codice inviato.</p>', unsafe_allow_html=True)
            except EmailError:
                st.markdown('<p class="error-msg">Invio non riuscito, riprovare.</p>', unsafe_allow_html=True)

    if st.button("Indietro", key="back_otp"):
        _go("email")

# ---------------------------------------------------------------------------
# Step 3 — Data e ora di restituzione
# ---------------------------------------------------------------------------
elif step == "return_time":
    st.title("Quando pensi di restituire la bici?")
    st.write("Indica una data e un orario indicativi. Non e' vincolante.")

    min_date = datetime.now().date()
    default_date = (datetime.now() + timedelta(hours=2)).date()

    return_date = st.date_input("Data di restituzione", value=default_date, min_value=min_date, key="return_date")
    return_time = st.time_input("Ora di restituzione", value=datetime.now().replace(hour=18, minute=0, second=0, microsecond=0).time(), key="return_time_input")

    if st.button("Avanti"):
        if return_date is None or return_time is None:
            st.markdown('<p class="error-msg">Seleziona data e ora di restituzione.</p>', unsafe_allow_html=True)
        else:
            dt = datetime.combine(return_date, return_time)
            if dt <= datetime.now():
                st.markdown('<p class="error-msg">La data di restituzione non puo\' essere nel passato.</p>', unsafe_allow_html=True)
            else:
                st.session_state["estimated_return_at"] = dt.isoformat()
                _go("disclaimer")

    if st.button("Indietro", key="back_return"):
        _go("email")

# ---------------------------------------------------------------------------
# Step 4 — Avviso di responsabilita'
# ---------------------------------------------------------------------------
elif step == "disclaimer":
    st.title("Prima di procedere")
    st.markdown(
        """
**Ti chiediamo di rispettare questa bici e di riportarla.**

Altre persone del quartiere fanno affidamento su queste biciclette.
Riportarla entro l'orario indicato permette a tutti di usufruirne.

Confermando, accetti di trattare la bici con cura e di riportarla.
        """
    )

    if st.button("Accetto e voglio il codice di sblocco"):
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

    if st.button("Indietro", key="back_disclaimer"):
        _go("return_time")

# ---------------------------------------------------------------------------
# Step 5 — Codice di sblocco
# ---------------------------------------------------------------------------
elif step == "unlock":
    bike_id = st.session_state.get("bike_id")
    bike = db.get_bike_by_id(bike_id) if bike_id else None

    st.title("Prenotazione completata")

    if bike:
        st.write(f"Bici: **{bike['label']}**")
        st.write("Il codice per aprire il catenaccio e':")
        # HTML-escape del codice prima dell'iniezione (prevenzione XSS)
        safe_code = html.escape(str(bike["unlock_code"]))
        st.markdown(
            f'<div class="unlock-code">{safe_code}</div>',
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
    if st.button("Torna alla home"):
        _reset()
        st.rerun()
