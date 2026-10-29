"""Source review with explicit original formats and separate task tabs."""
import streamlit as st
from frontend.ui import api, header, require_staff
from frontend.components import record_picker, timeline, badge, next_step
header("Review and publish", "Choose a source, check its course facts, then decide when learners can see it.")
require_staff()
reviewer = st.session_state["staff_name"]
if message := st.session_state.pop("catalog_review_feedback", None):
    st.success(message)
result = api("GET", "/api/v1/catalog/uploads")
if result is None:
    st.stop()
uploads = result["items"]
if not uploads:
    next_step("Start with a course file", "Upload a PDF or Word source first. Nothing is published automatically.",
              "pages/3_Course_Documents.py", "Upload a course file")
    st.stop()
st.subheader("Choose an original source")
st.caption("Each card is a separately saved upload. Uploading a PDF does not create Markdown or Word source copies.")
formats = ["All", *sorted({u["file_type"].upper() for u in uploads})]
file_filter = st.pills("File format", formats, default="All", key="source-format") or "All"
filtered = [u for u in uploads if file_filter == "All" or u["file_type"].upper() == file_filter]
upload_id = record_picker(filtered, key="review_upload", id_field="upload_id", title_field="filename", label="source files")
if upload_id is None:
    st.stop()
source = api("GET", f"/api/v1/catalog/uploads/{upload_id}")
if source is None:
    st.stop()
st.divider()
st.subheader(source["filename"])
badge(source["review_status"])
st.caption("Original upload: " + source["file_type"].upper() + " · This is a source file, not a generated training document.")
for warning in source["extraction_warnings"]:
    st.warning(warning)
if source["review_status"] == "blocked_incomplete":
    st.error("Some pages could not be read. Upload a clearer file before approval.")
rejected = source["review_status"] == "rejected" or source["approval_status"] == "rejected"
read_tab, details_tab, publish_tab, history_tab = st.tabs(["1  Read source", "2  Check details", "3  Publish", "History and rejection"])
with read_tab:
    st.write("Compare the extracted text with your original document before saving any course facts.")
    if st.button("Prepare original " + source["file_type"].upper() + " download"):
        data = api("GET", f"/api/v1/catalog/uploads/{upload_id}/original", binary=True)
        if data:
            st.download_button("Download original file", data, file_name=source["filename"])
    for chunk in source["chunks"]:
        with st.container(border=True):
            st.markdown("**" + chunk["metadata"].get("section", "Source text") + "**")
            st.text(chunk["text"])
    st.info("Next: open 2 Check details, verify the fields and save the course.")
with details_tab:
    st.subheader("Check the course details")
    st.write("Fill in the basics, compare them with the source, then save. You will publish separately.")
    st.write("Enter details from the source document. Do not guess missing prices or prerequisites.")
    with st.expander("Extract course metadata suggestions"):
        st.caption("Suggestions are unapproved. Select each course separately, inspect its evidence, and verify every field.")
        with st.form("extract_" + upload_id):
            extraction_reviewer = reviewer
            method = st.radio("Extraction method", ["deterministic", "gemini"], horizontal=True,
                              format_func=lambda x: "Read structured fields" if x == "deterministic" else "Ask AI for suggestions",
                              help="AI suggestions use the configured provider. Check every field against the original.")
            extract = st.form_submit_button("Extract suggestions", disabled=rejected)
        if extract:
            if len(extraction_reviewer.strip()) < 2:
                st.error("Enter the reviewer identifier first.")
            elif api("POST", f"/api/v1/catalog/uploads/{upload_id}/extract-metadata", json={
                    "reviewer": extraction_reviewer, "method": method}):
                st.session_state["catalog_review_feedback"] = "Suggestions saved. Verify source evidence before approval."
                st.rerun()

    candidates = (source.get("metadata_suggestions") or {}).get("candidates", [])
    suggested = {}
    candidate_index = -1
    if candidates:
        candidate_index = st.selectbox("Suggested course", range(len(candidates)), format_func=lambda i:
                                       candidates[i]["fields"].get("title", f"Course {i + 1}"))
        candidate = candidates[candidate_index]
        suggested = candidate["fields"]
        with st.expander("Suggestion evidence and missing fields"):
            st.json(candidate)

    with st.form(f"approve_course_{upload_id}_{candidate_index}", clear_on_submit=False):
        course_id = st.text_input("Course ID (unique)", value=suggested.get("course_id", ""), placeholder="DS-101")
        title = st.text_input("Verified course title", value=suggested.get("title", ""))
        description = st.text_area("Verified course description", value=suggested.get("description", ""))
        levels = ["Unknown", "Beginner", "Intermediate", "Advanced"]
        formats = ["Unknown", "Online", "On-site", "Hybrid"]
        level = st.radio("Level", levels, horizontal=True, index=levels.index(suggested.get("level", "Unknown")))
        delivery = st.radio("Training format", formats, horizontal=True, index=formats.index(suggested.get("training_format", "Unknown")))
        price = st.text_input("Price in EGP (leave blank if unknown)", value=str(suggested.get("price_egp", "")))
        hours = st.text_input("Total training hours (leave blank if unknown)", value=str(suggested.get("duration_hours", "")))
        dept = st.text_input("Department (optional)", value=suggested.get("department", ""))
        prerequisites = st.text_area("Prerequisites, one per line (leave blank if unknown)",
                                    value="\n".join(suggested.get("prerequisites", [])))
        outcomes = st.text_area("Learning outcomes, one per line", value="\n".join(suggested.get("learning_outcomes", [])))
        with st.expander("Instructor, schedule, offers and other course details"):
            optional = {}
            for field, label in [("instructor_name", "Instructor name"), ("instructor_bio", "Instructor background"),
                    ("schedule", "Schedule"), ("offers", "Offers"), ("target_audience", "Who this course is for")]:
                optional[field] = st.text_area(label, value=suggested.get(field) or "") or None
            for field, label in [("career_opportunities", "Career opportunities"), ("admission_requirements", "Admission requirements")]:
                optional[field] = [x.strip() for x in st.text_area(label + " (one per line)",
                    value="\n".join(suggested.get(field, []))).splitlines() if x.strip()]
            faq_text = st.text_area("FAQs (one question | answer per line)", value="\n".join(
                x["question"] + " | " + x["answer"] for x in suggested.get("faqs", [])))
        st.caption("Review recorded as: " + reviewer)
        checked = st.checkbox("I checked every extraction warning against the original document")
        confirm = st.checkbox("I verified these course details against the source document")
        approve = st.form_submit_button("Save verified course", disabled=
                                        rejected or source["review_status"] == "blocked_incomplete")

    if approve:
        if rejected:
            st.error("Rejected documents cannot be approved.")
        elif not confirm:
            st.error("Human verification is mandatory before approval.")
        else:
            try:
                faqs = []
                for line in faq_text.splitlines():
                    if not line.strip():
                        continue
                    if "|" not in line:
                        raise ValueError("FAQ needs question | answer")
                    question, answer = line.split("|", 1)
                    faqs.append({"question": question.strip(), "answer": answer.strip()})
                payload = {**optional, "faqs": faqs,
                    "course_id": course_id, "title": title, "description": description,
                    "level": None if level == "Unknown" else level,
                    "training_format": None if delivery == "Unknown" else delivery,
                    "price_egp": float(price) if price.strip() else None,
                    "duration_hours": float(hours) if hours.strip() else None,
                    "department": dept or None,
                    "prerequisites": [x.strip() for x in prerequisites.splitlines() if x.strip()],
                    "learning_outcomes": [x.strip() for x in outcomes.splitlines() if x.strip()],
                    "reviewer": reviewer, "acknowledge_extraction_warnings": checked,
                }
                result = api("POST", f"/api/v1/catalog/uploads/{upload_id}/approve", json=payload)
                if result:
                    st.success("Course saved. Open its publication panel below and select Publish course.")
                    st.rerun()
            except ValueError:
                st.error("Check that price and duration are numbers, and each FAQ has question | answer.")
with publish_tab:
    st.subheader("Make this course visible to learners")
    records = api("GET", "/api/v1/catalog/staff/courses")
    related = [c for c in (records or {}).get("items", []) if c["upload_id"] == upload_id]
    if not related:
        st.info("No verified course is linked to this file yet. Complete 2 Check details first.")
    for course in related:
        with st.container(border=True):
            st.subheader(course["title"])
            st.caption("Course " + course["course_id"] + " · Checked by " + course["reviewer"])
            badge(course["status"])
            if course["indexing_error"]:
                st.warning("The last publishing attempt needs attention: " + course["indexing_error"])
            if course["status"] in ("approved", "index_failed"):
                st.write("The details are checked. Publishing makes them available in the course library and learner chat.")
                if st.button("Publish course", key="pub_" + course["course_id"], type="primary"):
                    if api("POST", f'/api/v1/catalog/staff/courses/{course["course_id"]}/publish'):
                        st.session_state["catalog_review_feedback"] = "Course published. Learners can now find it."
                        st.rerun()
            if course["status"] == "published":
                st.page_link("pages/1_Course_Catalog.py", label="See what learners see", icon=":material/visibility:")
                with st.expander("Update search information"):
                    if st.button("Refresh search information", key="refresh_" + course["course_id"]):
                        if api("POST", f'/api/v1/catalog/staff/courses/{course["course_id"]}/refresh-index'):
                            st.success("Search information refreshed.")
            if course["status"] != "withdrawn":
                with st.expander("Hide this course from learners"):
                    st.write("Withdrawal also blocks dependent materials when their source is no longer valid.")
                    confirmed = st.checkbox("Confirm withdrawal", key="confirm_" + course["course_id"])
                    if st.button("Withdraw course", key="remove_" + course["course_id"]):
                        if not confirmed:
                            st.error("Confirm withdrawal before continuing.")
                        elif api("POST", f'/api/v1/catalog/staff/courses/{course["course_id"]}/withdraw', json={"reviewer":reviewer}):
                            st.session_state["catalog_review_feedback"] = "Course hidden from learners."
                            st.rerun()
with history_tab:
    st.subheader("Source decisions")
    if rejected:
        st.error("This document was rejected. Upload a corrected source document for a new review.")
        st.write(f'Rejected by {source.get("rejected_by")} at {source.get("rejected_at")}')
        st.text(source.get("rejection_reason") or "No reason recorded")
    with st.container():
        history = source.get("review_history", [])
        timeline(history)
    for course in related:
        st.markdown("**Course decisions · " + course["title"] + "**")
        audit = api("GET", f'/api/v1/catalog/staff/courses/{course["course_id"]}/history')
        if audit:
            timeline(audit["items"])

    with st.container(border=True):
        st.subheader("Reject this source")
        st.caption("Withdraw all courses linked to this source before rejecting it. "
                   "Rejection preserves the original document and its review history.")
        with st.form("reject_document_" + upload_id):
            rejection_reviewer = reviewer
            rejection_reason = st.text_area("Rejection reason (required)", max_chars=4000)
            reject_confirmed = st.checkbox("Confirm rejection of this source document")
            reject = st.form_submit_button(
                "Reject document", disabled=rejected or source["review_status"] not in
                ("pending_review", "blocked_incomplete"),
            )
        if reject:
            if len(rejection_reviewer.strip()) < 2 or not rejection_reason.strip() or not reject_confirmed:
                st.error("Enter a reviewer identifier (at least 2 characters), a rejection reason, and confirm rejection.")
            else:
                result = api("POST", f"/api/v1/catalog/uploads/{upload_id}/reject", json={
                    "reviewer": rejection_reviewer.strip(), "reason": rejection_reason.strip(),
                })
                if result:
                    st.session_state["catalog_review_feedback"] = "Document rejected. Decision and reason saved in its review history."
                    st.rerun()
