"""Guided document creation, readable version history and human review."""
import streamlit as st
from frontend.ui import api, header, require_staff
from frontend.components import record_picker, badge, timeline, date_label, next_step
header("Document studio", "Make a training document, check it, and download the version you need.")
reviewer = require_staff()
if message := st.session_state.pop("document_feedback", None):
    st.success(message)
templates = api("GET", "/api/v1/documents/templates")
records = api("GET", "/api/v1/documents")
courses = api("GET", "/api/v1/catalog/courses")
curricula = api("GET", "/api/v1/curriculum", params={"status":"approved"})
if templates is None or records is None or courses is None or curricula is None:
    st.stop()
by_template = {t["template_id"]:t for t in templates["items"]}
prior = {r["artifact_id"]:r for r in records["items"]}
course_labels = {c["course_id"]:f'{c["title"]} ({c["course_id"]})' for c in courses["items"]}
create_tab, saved_tab = st.tabs(["Create a document", "My documents and history"])
with create_tab:
    st.subheader("1  What do you want to make?")
    kind = st.pills("Document type",list(by_template),default="course_description",format_func=lambda x:by_template[x]["name"],key="document-kind") or "course_description"
    template = by_template[kind]
    st.write(template["purpose"])
    if not template["approved"]:
        with st.container(border=True):
            st.markdown("**Check the template once before using this version**")
            for title in template["sections"]:
                st.write(title)
            st.caption("This approves the structure. Every generated document still needs its own review.")
            if st.button("Approve this template version"):
                if api("POST",f"/api/v1/documents/templates/{kind}/approve",json={"reviewer":reviewer}):
                    st.rerun()
    else:
        st.caption("Template checked · Branded PDF and Word outputs")
    st.subheader("2  Choose the course")
    if not course_labels:
        next_step("Publish a course first", "Documents use verified course facts. Upload and publish a source before creating a document.",
                  "pages/4_Course_Approvals.py", "Review course sources")
    chosen = st.pills("Published courses",list(course_labels),selection_mode="multi",format_func=course_labels.get,key="document-courses")
    chosen = chosen or []
    if len(chosen)>5:
        st.error("Choose no more than five source courses.")
    compatible = {c["id"]:c for c in curricula["items"] if set(chosen).issubset({s["course_id"] for s in c["source_records"]})}
    curriculum_id = None
    if template.get("requires_curriculum"):
        if compatible and chosen:
            ids=list(compatible);preferred=st.session_state.get("approved_curriculum_id")
            curriculum_id=st.radio("Approved teaching plan",ids,index=ids.index(preferred) if preferred in ids else 0,
                format_func=lambda x:compatible[x]["title"]+f" · #{x}")
        else:
            next_step("This document needs an approved teaching plan", "Choose a published course and approve its curriculum first.",
                      "pages/8_Curriculum.py", "Open curriculum studio")
    st.subheader("3  Set the language and audience")
    with st.form("generate_document"):
        language=st.radio("Language",["en","ar"],horizontal=True,format_func=lambda x:"English" if x=="en" else "Arabic")
        audience=st.text_input("Intended audience",value="Prospective learners",max_chars=240)
        with st.expander("Make a new version of an existing document"):
            revision_options=[r for r in prior if prior[r].get("document_type")==kind]
            revision_of=st.selectbox("Revise an existing document",[None,*revision_options],format_func=lambda x:"New document" if x is None else f'{prior[x]["title"]} · version {prior[x]["version"]}')
            instructions=st.text_area("Revision instructions",max_chars=2000)
        generate=st.form_submit_button("Generate document draft",type="primary",disabled=not template["approved"] or not chosen or len(chosen)>5 or bool(template.get("requires_curriculum") and not curriculum_id))
    if generate:
        with st.spinner("Preparing your document..."):
            result=api("POST","/api/v1/documents",json={"document_type":kind,"course_ids":chosen,"language":language,
                "audience":audience,"requester":reviewer,"curriculum_id":curriculum_id,
                "revision_of":revision_of,"revision_instructions":instructions})
        if result:
            st.session_state["selected_document"]=result["artifact_id"]
            st.session_state["document_feedback"]="Document saved. Open My documents and history to read it, review it and download files."
            st.rerun()
    st.caption("Your original source keeps its uploaded format. The document you create here is a separate output, available as PDF and Word.")
with saved_tab:
    st.subheader("Find a document")
    selected=record_picker(records["items"],key="selected_document",id_field="artifact_id",label="documents")
    if selected is None:
        st.info("Create a document in the first tab. Its saved versions will appear here.")
        st.stop()
    record=api("GET",f"/api/v1/documents/{selected}")
    if record is None:
        st.stop()
    st.divider()
    st.subheader(record["content"]["title"])
    badge(record["status"])
    st.caption(f'Version {record["version"]} · {"Arabic" if record["language"]=="ar" else "English"} · {date_label(record["created_at"])}')
    st.write("**Original sources:** "+", ".join(s["source_file"] for s in record["sources"]))
    read_tab, edit_tab, decision_tab, history_tab=st.tabs(["Read and download","Edit a new version","Review decision","Version history"])
    with read_tab:
        if record["status"] != "approved":
            st.info("This is not an approved final document. Check the content and record a decision in Review decision.")
        for section in record["content"]["sections"]:
            st.markdown("**"+section["heading"]+"**")
            st.write(section["text"])
            st.caption("Sources: "+", ".join(section["source_ids"]))
        st.subheader("Download files")
        if record["status"] in ("pending_review","approved"):
            columns=st.columns(2)
            for col,fmt in zip(columns,("pdf","docx")):
                with col:
                    if st.button("Prepare "+("PDF" if fmt=="pdf" else "Word"),key=selected+"-prepare-"+fmt):
                        data=api("GET",f"/api/v1/documents/{selected}/download/{fmt}",binary=True)
                        if data:
                            st.download_button("Download "+("PDF" if fmt=="pdf" else "Word"),data,
                                file_name=f"andalusia-{selected}.{fmt}",key=selected+fmt,on_click="ignore")
        else:
            st.warning("This version needs changes or was rejected. Make a new version before downloading it.")
    with edit_tab:
        st.caption("Edits preserve the original version and require another review. Every section retains its source citations.")
        with st.form("manual_document_revision_" + selected):
            edited_title = st.text_input("Edited document title", value=record["content"]["title"])
            edited_sections = []
            for i, section in enumerate(record["content"]["sections"]):
                heading = st.text_input(f"Section {i+1} heading", value=section["heading"], key=f"eh-{selected}-{i}")
                text = st.text_area(f"Section {i+1} content", value=section["text"], height=170, key=f"et-{selected}-{i}")
                edited_sections.append({"heading": heading, "text": text, "source_ids": section["source_ids"]})
            edit_reason = st.text_area("Document edit reason", max_chars=2000)
            save_edits = st.form_submit_button("Save edited document as a new draft")
        if save_edits:
            if not edit_reason.strip():
                st.error("Explain the changes before saving.")
            else:
                result = api("POST", "/api/v1/documents", json={"document_type": record["document_type"],
                    "course_ids": [s["course"]["course_id"] for s in record["sources"]],
                    "curriculum_id": (record.get("curriculum") or {}).get("id"), "language": record["language"],
                    "audience": record["audience"], "requester": reviewer, "revision_of": selected,
                    "revision_instructions": edit_reason, "edited_content": {"title": edited_title, "sections": edited_sections}})
                if result:
                    st.session_state["selected_document"] = result["artifact_id"]
                    st.session_state["document_feedback"] = "Edited draft saved as a new version. Review it before approval."
                    st.rerun()

    with decision_tab:
        if record["status"] == "pending_review":
            with st.form("review_" + selected):
                decision = st.radio("Review decision", ["approve", "request_revision", "reject"], horizontal=True, format_func=lambda x: {"approve":"Approve", "request_revision":"Ask for changes", "reject":"Reject"}[x])
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
    with history_tab:
        st.subheader("Versions of this document")
        family=[r for r in records["items"] if r["family_id"]==record["family_id"]]
        for version in sorted(family,key=lambda r:r["version"],reverse=True):
            with st.container(border=True):
                st.markdown(f'**Version {version["version"]} · {version["title"]}**')
                badge(version["status"])
                st.caption(date_label(version["created_at"]))
                st.write("Source files: "+", ".join(version.get("source_files",[])))
                if version["artifact_id"] != selected and st.button("Open version "+str(version["version"]),key="version-"+version["artifact_id"]):
                    st.session_state["selected_document"]=version["artifact_id"];st.rerun()
        st.subheader("What happened to the selected version")
        timeline(record["history"])
        with st.expander("Check the original evidence"):
            for source in record["sources"]:
                st.markdown("**"+source["course"]["title"]+"**")
                st.caption(source["source_file"]+" · "+source["source_id"])
                st.write(source["course"]["description"])
            if st.session_state.get("show_technical_details"):
                st.json(record["sources"])
