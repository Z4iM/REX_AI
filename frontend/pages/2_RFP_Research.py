import streamlit as st

from backend.app.agents.rfp.ui import render


st.set_page_config(
    page_title="REX AI — RFP Research",
    page_icon="📑",
    layout="wide",
)

# Use the RFP module's own password gate.
# Do not set authenticated=True until the main
# application has verified staff authentication.
render(
    authenticated=False,
    key_prefix="agent2_",
)