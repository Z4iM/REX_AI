import streamlit as st
from frontend.ui import api, header, require_staff
header("Demo setup", "Fictional examples, stored separately from academy records. Follow these steps in order.")
require_staff()
status = api("GET", "/api/v1/system", staff=False)
if not status or status["mode"] != "demo":
    st.error("Start Demo mode with python scripts/run_demo.py")
    st.stop()
st.subheader("1. Load the example documents")
st.write("Load four course documents with suggestions already filled in. You still review and publish each course yourself.")
if st.button("Load course examples", type="primary"):
    with st.spinner("Reading the course files..."):
        result = api("POST", "/api/v1/demo/stage-courses", json={"reviewer": st.session_state["staff_name"]})
    if result:
        st.success(result["notice"])
        st.dataframe(result["items"], hide_index=True)
st.write("Open **Review and publish**, choose Python Foundations Demo, verify the fields, select Save verified course, then Publish course below.")
st.subheader("2. Try the learner workflow")
st.write("Open Course library, then Learning advisor. Ask: What does Python Foundations Demo cost and who teaches it? Try the guided recommendation with a beginner level, online delivery and a 3000 EGP budget.")
st.subheader("3. Create and review a document")
st.write("Open **Document studio**, approve the course description template, choose the published Python course and generate a draft. Review it, save a decision and download PDF or Word. Arabic is also available.")
st.subheader("4. Try Faris's opportunity workflow")
if st.button("Load tender examples"):
    result = api("POST", "/api/v1/demo/stage-tenders")
    if result:
        st.success(f"Added {result['new']} opportunities; rejected {result['rejected']}; duplicates {result['duplicates']}.")
st.write("Open Training opportunities. Egyptian and Saudi training examples should appear. Germany and expired examples are filtered out. Change a review status and inspect dashboard alerts. No email or webhook is sent.")
st.subheader("5. Test rejection and download all examples")
st.write("Download the pack below. Upload negative_cases/reject_missing_information.md in Add course documents, reject it with a reason, and confirm it cannot be approved. Word and PDF course copies let you test all three upload formats. The reference pack contains ten authored teaching-document examples; use the Curriculum studio to generate and review the teaching plan before creating curriculum-based materials.")
if st.button("Prepare example pack download"):
    data = api("GET", "/api/v1/demo/examples.zip", binary=True)
    if data:
        st.download_button("Download all Demo examples", data, file_name="rex-demo-examples.zip", mime="application/zip")

st.subheader("6. Connect curriculum, documents and marketing")
st.write("Open Curriculum studio, select the published Python source and generate a 24-hour beginner curriculum. Review all modules and assessments, submit it for review and approve it with a reason. The approved version can now be selected in Document studio and Campaign studio.")
st.write("In Document studio, select a curriculum-based template, approve its structure, choose the source course and approved curriculum, then generate and review a PDF. In Campaign studio, select the same curriculum, choose an audience and channels, generate variations and review them before downloading the campaign.")
st.caption("Generated plans and campaigns are drafts. Demo approvals are for fictional assessment examples only.")
