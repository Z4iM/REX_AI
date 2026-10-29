"""Andalusia Academy's unified learner and staff workspace."""
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frontend.ui import api, apply_theme

st.set_page_config(page_title="Andalusia Academy | REX AI", page_icon=str(Path(__file__).resolve().parents[1] / "assets/branding/andalusia-favicon.ico"), layout="wide", initial_sidebar_state="auto")
apply_theme()
st.logo(str(Path(__file__).resolve().parents[1] / "assets/branding/andalusia-logo.svg"), size="large")
with st.sidebar:
    st.caption("ACADEMY WORKSPACE")
    st.write("Choose a task below. Staff tools ask you to sign in.")
    st.toggle("Show technical details", value=False, key="show_technical_details", help="Keep this off for everyday work. Turn it on only when checking an issue.")
status = api("GET", "/api/v1/system", staff=False)
pages = {
    "Start here": [st.Page("pages/0_Home.py", title="Academy home", icon=":material/dashboard:", default=True)],
    "For learners": [st.Page("pages/1_Course_Catalog.py", title="Course library", icon=":material/menu_book:"),
                 st.Page("assistant_page.py", title="Learning advisor", icon=":material/forum:")],
    "Course information": [st.Page("pages/3_Course_Documents.py", title="Upload course sources", icon=":material/upload_file:"),
                  st.Page("pages/4_Course_Approvals.py", title="Review and publish", icon=":material/fact_check:")],
    "Create and review": [st.Page("pages/10_Instructor.py", title="Instructor workspace", icon=":material/assistant:"),
                  st.Page("pages/8_Curriculum.py", title="Curriculum studio", icon=":material/account_tree:"),
                  st.Page("pages/5_Document_Generation.py", title="Document studio", icon=":material/description:"),
                  st.Page("pages/9_Marketing.py", title="Campaign studio", icon=":material/campaign:")],
    "Business follow-up": [st.Page("pages/2_RFP_Research.py", title="Training opportunities", icon=":material/travel_explore:"),
                  st.Page("pages/6_Learner_Follow_Up.py", title="Learner follow-up", icon=":material/contact_page:")],
}
if status and status["mode"] == "demo":
    pages["Demonstration"] = [st.Page("pages/7_Demo_Setup.py", title="Guided demonstration", icon=":material/play_circle:")]
st.navigation(pages, expanded=True).run()
