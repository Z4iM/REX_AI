import streamlit as st
from frontend.ui import header
from frontend.components import next_step

status = header("What would you like to do?", "Andalusia Academy · REX AI")
learner, staff = st.columns(2)
with learner:
    st.subheader("I want to learn", icon=":material/school:")
    next_step("Find the right course", "Tell REX what you want to learn and get help choosing.",
              "assistant_page.py", "Get course advice")
    next_step("See available courses", "Check course topics, fees and schedules in the academy catalog.",
              "pages/1_Course_Catalog.py", "Browse courses")
with staff:
    st.subheader("I work at the academy", icon=":material/badge:")
    next_step("Ask REX to help", "Describe what you need. REX shows its plan before making any changes.",
              "pages/10_Instructor.py", "Open staff chat")
    next_step("Add a course for learners", "Upload a file, verify its details, then publish the course.",
              "pages/3_Course_Documents.py", "Upload a course file")

st.subheader("Staff shortcuts")
for page, label, icon in [
    ("4_Course_Approvals.py", "Review and publish courses", "fact_check"),
    ("8_Curriculum.py", "Plan what to teach", "account_tree"),
    ("5_Document_Generation.py", "Make and download a document", "description"),
    ("9_Marketing.py", "Prepare a marketing campaign", "campaign"),
    ("2_RFP_Research.py", "Find training opportunities", "travel_explore"),
    ("6_Learner_Follow_Up.py", "See who asked to be contacted", "contact_page"),
]:
    st.page_link("pages/" + page, label=label, icon=f":material/{icon}:")

if status and status["mode"] == "demo":
    next_step("Try with fictional data", "The guided demo walks you through the workflows without changing academy records.",
              "pages/7_Demo_Setup.py", "Open demo setup")
