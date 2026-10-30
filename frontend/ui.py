"""Shared navigation, clear feedback and one staff sign-in per browser session."""
import os
from pathlib import Path
import requests
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
API = (os.getenv("REX_API_URL") or "http://127.0.0.1:8000").rstrip("/")


def api(method, path, *, staff=True, binary=False, **kwargs):
    key = st.session_state.get("staff_key", "") if staff else ""
    try:
        response = requests.request(method, API + path, headers={"X-API-Key": key} if key else {}, timeout=240, **kwargs)
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
        st.error("This request took too long. Your saved work is safe; refresh the page before retrying.")
    except requests.exceptions.RequestException:
        st.error("Cannot reach REX. Start the backend first, then refresh this page.")
    return None


def header(title, description):
    st.title(title)
    st.caption(description)
    status = api("GET", "/api/v1/system", staff=False)
    if status and status["mode"] == "demo":
        st.warning("TA DEMO · Fictional examples for assessment. These are not real academy courses or tenders.")
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
        key = st.text_input("Staff access key", type="password", help="Use REX_CATALOG_ADMIN_KEY from your local .env. Never share it in screenshots.")
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
    with st.expander(label):
        st.json(value)
