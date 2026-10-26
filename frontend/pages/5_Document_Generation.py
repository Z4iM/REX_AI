"""Staff-only document generation, version history, review and downloads."""
import streamlit as st
from frontend.ui import api, header, require_staff
header("Create documents", "Step 3 of 3 · Choose published courses, generate a draft, review it, and download Word or PDF.")
require_staff()
reviewer = st.session_state["staff_name"]
if message := st.session_state.pop("document_feedback", None):
    st.success(message)

templates = api("GET", "/api/v1/documents/templates")
records = api("GET", "/api/v1/documents")
courses = api("GET", "/api/v1/catalog/courses")
if templates is None or records is None or courses is None:
    st.stop()
st.caption("Documents requested and reviewed as: " + reviewer)
by_template = {t["template_id"]: t for t in templates["items"]}
kind = st.selectbox("Document type", list(by_template), format_func=lambda k: by_template[k]["name"])
template = by_template[kind]
with st.expander("Review document template", expanded=not template["approved"]):
    st.write(template["purpose"])
    st.write(template["sections"])
    st.caption(f'Template version {template["version"]}')
    if not template["approved"]:
        if st.button("Approve this template version"):
            if len(reviewer.strip()) < 2:
                st.error("Enter your staff identifier first.")
            elif api("POST", f"/api/v1/documents/templates/{kind}/approve", json={"reviewer": reviewer}):
                st.rerun()
with st.expander("Which documents can REX create?"):
    st.write("Course descriptions, course proposals and participant guides are available. Curriculum-based materials become available after the Curriculum Agent is integrated.")

course_labels = {c["course_id"]: f'{c["course_id"]} — {c["title"]}' for c in courses["items"]}
prior = {r["artifact_id"]: r for r in records["items"]}
with st.form("generate_document"):
    chosen = st.multiselect("Published courses", list(course_labels), format_func=course_labels.get, max_selections=5)
    language = st.selectbox("Language", ["en", "ar"], format_func=lambda x: "English" if x == "en" else "Arabic")
    audience = st.text_input("Intended audience", value="Prospective learners", max_chars=240)
    revision_of = st.selectbox("Revise an existing document", [None, *prior], format_func=lambda x:
                               "New document" if x is None else f'{prior[x]["title"]} v{prior[x]["version"]} [{prior[x]["status"]}]')
    instructions = st.text_area("Revision instructions", max_chars=2000)
    generate = st.form_submit_button("Generate document draft", disabled=not template["approved"] or not course_labels)
if generate:
    if not chosen or len(reviewer.strip()) < 2:
        st.error("Choose at least one published course and enter your staff identifier.")
    else:
        with st.spinner("Generating grounded content and rendering DOCX/PDF..."):
            result = api("POST", "/api/v1/documents", json={"document_type": kind, "course_ids": chosen,
                         "language": language, "audience": audience, "requester": reviewer,
                         "revision_of": revision_of, "revision_instructions": instructions})
        if result:
            st.session_state["selected_document"] = result["artifact_id"]
            st.session_state["document_feedback"] = "Draft saved. Inspect the content, source facts and files before approval."
            st.rerun()

st.divider()
st.subheader("Document review and version history")
if not prior:
    st.info("No generated documents yet. Publish a reviewed course, approve a template, then generate a draft.")
    st.stop()
options = list(prior)
selected = st.selectbox("Saved document", options, index=options.index(st.session_state.get("selected_document"))
                       if st.session_state.get("selected_document") in options else 0,
                       format_func=lambda x: f'{prior[x]["title"]} v{prior[x]["version"]} [{prior[x]["status"]}]')
record = api("GET", f"/api/v1/documents/{selected}")
if record is None:
    st.stop()
st.write(f'Status: {record["status"]} | Version: {record["version"]} | Language: {record["language"]}')
st.subheader(record["content"]["title"])
for section in record["content"]["sections"]:
    st.markdown("**" + section["heading"] + "**")
    st.write(section["text"])

with st.expander("Source snapshots and audit history"):
    st.json({"sources": record["sources"], "history": record["history"]})
if record["status"] == "pending_review":
    with st.form("review_" + selected):
        decision = st.selectbox("Review decision", ["approve", "request_revision", "reject"])
        reason = st.text_area("Review reason", max_chars=4000)
        checked = st.checkbox("I checked the complete document and source facts")
        submit = st.form_submit_button("Save review decision")
    if submit:
        if len(reviewer.strip()) < 2 or not reason.strip() or not checked:
            st.error("Enter reviewer identification, a reason, and confirm the document review.")
        elif api("POST", f"/api/v1/documents/{selected}/review", json={
                "reviewer": reviewer, "decision": decision, "reason": reason}):
            st.session_state["document_feedback"] = "Review decision saved. Use the generation form to create a revision when needed."
            st.rerun()
if record["status"] in ("pending_review", "approved"):
    for fmt in ("pdf", "docx"):
        data = api("GET", f"/api/v1/documents/{selected}/download/{fmt}", binary=True)
        if data is not None:
            st.download_button(f'Download {record["status"]} {fmt.upper()}', data,
                               file_name=f"rex-{selected}.{fmt}", key=selected + fmt)
