import streamlit as st
from frontend.ui import api, header, require_staff, done, diagnostics

header("Add course documents", "Step 1 of 3 · Upload a source file. You will check its information before anyone can see the course.")
require_staff()
upload = st.file_uploader("Choose a PDF, Word document, or Markdown file", type=["pdf", "docx", "md"])
with st.expander("My PDF is a scan or photo"):
    ocr = st.checkbox("Read text from scanned pages", help="Use this only when the PDF does not already contain selectable text.")
if st.button("Upload document", type="primary", disabled=upload is None):
    with st.spinner("Reading your document..."):
        result = api("POST", "/api/v1/catalog/uploads", files={"file": (upload.name, upload.getvalue())},
                     data={"enable_ocr": str(ocr).lower()})
    if result:
        st.session_state["review_upload"] = result["upload_id"]
        done("Document saved. Go to Review & publish to check its information.")
st.page_link("pages/4_Course_Approvals.py", label="Continue to review & publish →")
records = api("GET", "/api/v1/catalog/uploads")
if records and records["items"]:
    st.subheader("Your saved source files")
    st.dataframe([{ "Document": r["filename"], "Source review": r["review_status"].replace("_", " ")}
                   for r in records["items"]], hide_index=True, width="stretch")
    diagnostics(records, "Inspect upload records")
