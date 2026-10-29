import streamlit as st
from frontend.ui import api, header, require_staff, done
from frontend.components import record_picker, next_step
header("Upload course sources", "Add an original course file. Next, check its details before making it visible to learners.")
require_staff()
st.subheader("1  Choose your original file")
upload=st.file_uploader("Choose a PDF, Word document, or Markdown file",type=["pdf","docx","md"])
st.caption("PDF, Word DOCX or Markdown · Up to 10 MiB · The original file format is preserved.")
ocr=st.checkbox("Read text from scanned pages",help="Use this only for a scanned PDF or a photo without selectable text.")
if st.button("Upload document",type="primary",disabled=upload is None):
    if upload.size>10*1024*1024:
        st.error("Choose a file no larger than 10 MiB.")
    else:
        with st.spinner("Reading the course file..."):
            result=api("POST","/api/v1/catalog/uploads",files={"file":(upload.name,upload.getvalue())},data={"enable_ocr":str(ocr).lower()})
        if result:
            st.session_state["review_upload"]=result["upload_id"]
            prefix="This exact file was already saved as " if result["already_uploaded"] else "Saved original file: "
            done(prefix+result["filename"]+" ("+result["file_type"].upper()+"). It has not been published.")
next_step("2  Check the source and course facts", "Open the review page, read the extracted text and verify the details. Publishing is a separate final step.",
          "pages/4_Course_Approvals.py", "Continue to review and publish")
records=api("GET","/api/v1/catalog/uploads")
if records and records["items"]:
    st.subheader("Previously uploaded originals")
    st.caption("These are separate saved files. A PDF upload does not create MD or DOCX source copies.")
    selected=record_picker(records["items"],key="upload-library",id_field="upload_id",title_field="filename",label="uploads")
    if selected and st.button("Review selected source",type="primary"):
        st.session_state["review_upload"]=selected
        st.switch_page("pages/4_Course_Approvals.py")
