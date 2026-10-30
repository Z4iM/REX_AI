"""REX's single entry point with task-based navigation."""
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frontend.ui import api

st.set_page_config(page_title="REX AI", page_icon="🎓", layout="wide")
with st.sidebar:
    st.title("REX AI")
    st.caption("Academy workspace")
status = api("GET", "/api/v1/system", staff=False)
pages = {
    "Start": [st.Page("pages/0_Home.py", title="Home", icon="🏠", default=True)],
    "For learners": [st.Page("pages/1_Course_Catalog.py", title="Browse courses", icon="📚"),
                     st.Page("assistant_page.py", title="Ask REX", icon="💬")],
    "For staff": [st.Page("pages/3_Course_Documents.py", title="1 · Add course documents", icon="📥"),
                  st.Page("pages/4_Course_Approvals.py", title="2 · Review & publish", icon="✅"),
                  st.Page("pages/5_Document_Generation.py", title="3 · Create documents", icon="📄"),
                  st.Page("pages/2_RFP_Research.py", title="Training opportunities", icon="🔎"),
                  st.Page("pages/6_Learner_Follow_Up.py", title="Learner follow-up", icon="📋")],
}
if status and status["mode"] == "demo":
    pages["TA demonstration"] = [st.Page("pages/7_Demo_Setup.py", title="Demo setup", icon="▶️")]
st.navigation(pages, expanded=True).run()
