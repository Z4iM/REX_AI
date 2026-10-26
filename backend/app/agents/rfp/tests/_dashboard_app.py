"""Streamlit entry point for testing the RFP dashboard."""

from backend.app.agents.rfp.ui import render

render(
    authenticated=False,
    key_prefix="rfp_",
)