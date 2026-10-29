import streamlit as st
from frontend.ui import header

status = header("A clearer path to learning", "Andalusia Academy / REX AI")
st.markdown('<div class="academy-hero"><span class="academy-eyebrow">KNOWLEDGE INTO OPPORTUNITY</span><h2>What would you like to do?</h2><p>Choose a task below. REX will guide you through the next step.</p></div>', unsafe_allow_html=True)
left, right = st.columns([1, 1])
with left:
    with st.container(border=True):
        st.subheader("Discover your next step", icon=":material/school:")
        st.write("Explore published courses or tell the learning advisor about your experience and goals.")
        st.page_link("pages/1_Course_Catalog.py", label="Explore the course library", icon=":material/menu_book:")
        st.page_link("assistant_page.py", label="Find a course with REX", icon=":material/forum:")
with right:
    with st.container(border=True):
        st.subheader("Build with confidence", icon=":material/architecture:")
        st.write("Staff review every source before publication. Generated curricula, documents and campaigns each receive a separate human review.")
        st.page_link("pages/10_Instructor.py", label="Coordinate work with instructor chat", icon=":material/assistant:")
        st.page_link("pages/3_Course_Documents.py", label="Add a course source", icon=":material/upload_file:")
        st.page_link("pages/8_Curriculum.py", label="Plan a course", icon=":material/account_tree:")
        st.page_link("pages/5_Document_Generation.py", label="Make a training document", icon=":material/description:")
        st.page_link("pages/9_Marketing.py", label="Create marketing content", icon=":material/campaign:")
        st.page_link("pages/2_RFP_Research.py", label="Review training opportunities", icon=":material/travel_explore:")
st.subheader("From source to delivery")
cols = st.columns(4)
for col, title, text, icon in zip(cols, ["1. Verify", "2. Design", "3. Create", "4. Review"],
    ["Upload a source, check the facts and publish the course.", "Build a curriculum from published facts and approve the teaching plan.", "Create training materials and a campaign from the approved curriculum.", "Check each output, request revisions and export approved work."],
    [":material/verified:", ":material/account_tree:", ":material/edit_document:", ":material/fact_check:"]):
    with col:
        with st.container(border=True):
            st.subheader(title, icon=icon)
            st.write(text)
if status and status["mode"] == "demo":
    st.info("Demonstration workspace: all example courses and tenders are fictional. Begin with the guided setup.")
    st.page_link("pages/7_Demo_Setup.py", label="Open guided demonstration", icon=":material/play_circle:")
else:
    with st.expander("Try the complete workflow with example documents"):
        st.write("Launch the separate demonstration workspace, then open Guided demonstration in its sidebar.")
        st.code("python scripts/run_demo.py", language="powershell")
