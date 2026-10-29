"""Shared navigation, clear feedback and one staff sign-in per browser session."""
import os
from pathlib import Path
import requests
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
API = (os.getenv("REX_API_URL") or "http://127.0.0.1:8000").rstrip("/")


def api(method, path, *, staff=True, binary=False, request_timeout=240, **kwargs):
    key = st.session_state.get("staff_key", "") if staff else ""
    try:
        headers = {"X-API-Key": key} if key else {}
        if key and st.session_state.get("staff_name"):
            headers["X-REX-Reviewer"] = st.session_state["staff_name"]
        response = requests.request(method, API + path, headers=headers, timeout=request_timeout, **kwargs)
        response.raise_for_status()
        return response.content if binary else response.json()
    except requests.exceptions.HTTPError as exc:
        try:
            detail = exc.response.json().get("detail", "Request failed")
        except ValueError:
            detail = "The server could not complete this action."
        if isinstance(detail, list):
            detail = "; ".join(f'{" / ".join(str(x) for x in error.get("loc", [])[1:])}: {error["msg"]}' for error in detail)
        if exc.response.status_code == 401:
            st.session_state.pop("staff_key", None)
            detail = "Your staff sign-in is invalid or expired. Sign in again."
        st.error(str(detail))
    except requests.exceptions.Timeout:
        st.error("This request took too long. Refresh and check the saved record before trying the action again.")
    except requests.exceptions.RequestException:
        st.error("REX is not responding. Refresh once, then ask your administrator to check the service if it continues.")
    return None


def header(title, description):
    apply_theme()
    st.title(title)
    st.caption(description)
    status = api("GET", "/api/v1/system", staff=False)
    if status and status["mode"] == "demo":
        st.warning("DEMO · Fictional examples for assessment. These are not real academy courses or tenders.")
    if message := st.session_state.pop("feedback", None):
        st.success(message)
    return status


def require_staff():
    if st.session_state.get("staff_key"):
        if api("GET", "/api/v1/catalog/staff/session"):
            with st.sidebar:
                st.caption("Signed in as " + st.session_state.get("staff_name", "Staff"))
                if st.button("Sign out", key="staff_sign_out"):
                    st.session_state.pop("staff_key", None)
                    st.session_state.pop("staff_name", None)
                    st.rerun()
            return st.session_state.get("staff_name", "Staff")
        if st.session_state.get("staff_key"):
            st.stop()
    st.subheader("Staff sign-in")
    st.write("Sign in once to upload, review, create documents, and manage opportunities.")
    with st.form("staff_sign_in"):
        name = st.text_input("Your name", max_chars=120)
        key = st.text_input("Staff access key", type="password", help="Your academy administrator supplies this key. Keep it out of chat and screenshots.")
        submit = st.form_submit_button("Sign in", type="primary")
    if submit:
        if len(name.strip()) < 2 or not key:
            st.error("Enter your name and staff access key.")
        else:
            st.session_state["staff_key"] = key
            if api("GET", "/api/v1/catalog/staff/session"):
                st.session_state["staff_name"] = name.strip()
                st.rerun()
            st.session_state.pop("staff_key", None)
    st.stop()


def done(message):
    st.session_state["feedback"] = message
    st.rerun()


def diagnostics(value, label="Technical details"):
    if st.session_state.get("show_technical_details"):
        with st.expander(label):
            st.json(value)


def apply_theme():
    st.markdown("""<style>
    .stApp{background:#fff;color:#212d30}
    h1,h2,h3{font-family:Avenir,Arial,sans-serif!important;letter-spacing:-.025em;color:#212d30}
    h1{font-size:2.55rem!important;font-weight:700!important}
    [data-testid="stSidebar"]{background:#faf7f5;border-right:1px solid #eadbd2}
    [data-testid="stSidebar"] a{border-radius:7px}
    [data-testid="stVerticalBlockBorderWrapper"]{border-radius:10px}
    .stButton button,.stDownloadButton button,.stLinkButton a{border-radius:7px;min-height:2.7rem}
    .stButton button[kind="primary"]{background:#b07963;border-color:#b07963}
    .stTabs [data-baseweb="tab-list"]{gap:20px;border-bottom:1px solid #eadbd2}
    .academy-hero{padding:2.2rem 2.6rem;margin:1rem 0 2rem;background:#faf6f3;border:1px solid #e6cfc1;border-radius:10px;color:#212d30;border-top:3px solid #b07963}
    .academy-hero h2{color:#212d30!important;font-size:2.2rem!important;margin:.6rem 0}
    .academy-hero p{max-width:780px;font-size:1.06rem;line-height:1.7;color:#596165}
    .academy-eyebrow{font-size:.72rem;letter-spacing:.16em;color:#9d654f;font-weight:700}
    .block-container{padding-top:2rem;max-width:1350px}
    [data-testid="stMetric"]{background:#faf6f3;padding:1rem;border:1px solid #eadbd2;border-radius:8px}
    </style>""", unsafe_allow_html=True)
