import streamlit as st
from frontend.ui import header

status = header("Welcome to REX AI", "Find a course, prepare training documents, or manage academy work.")
left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("I want to learn")
        st.write("Browse published courses or answer a few questions to find a suitable option.")
        st.page_link("pages/1_Course_Catalog.py", label="Browse courses", icon="📚")
        st.page_link("assistant_page.py", label="Ask REX or get a recommendation", icon="💬")
with right:
    with st.container(border=True):
        st.subheader("I work at the academy")
        st.write("Add a course, check its information, and make reviewed documents. Sign in once on any staff page.")
        st.page_link("pages/3_Course_Documents.py", label="Add a course document", icon="📥")
        st.page_link("pages/5_Document_Generation.py", label="Create a document", icon="📄")
        st.page_link("pages/2_RFP_Research.py", label="Training opportunities", icon="🔎")
if status and status["mode"] == "demo":
    st.info("Wanna try functions? Start with Demo setup. It loads fictional source files for you to review and publish.")
    st.page_link("pages/7_Demo_Setup.py", label="Start Demo walkthrough", icon="▶️")
else:
    with st.expander("Need examples for a demonstration?"):
        st.write("Run the separate demo application. Your existing academy data stays separate.")
        st.code("python scripts/run_demo.py", language="powershell")
st.caption("The normal course workflow is: Upload → Review → Publish → Use in chat or documents.")
