"""Staff-only approval and publication console for uploaded course documents."""
from __future__ import annotations

import json
import streamlit as st
from frontend.ui import api, header, require_staff
header("Review & publish", "Step 2 of 3 · Check the source, save verified details, then make the course available to learners.")
require_staff()
reviewer = st.session_state["staff_name"]
if message := st.session_state.pop("catalog_review_feedback", None):
    st.success(message)

upload_result = api("GET", "/api/v1/catalog/uploads")
if upload_result is None:
    st.stop()
uploads = upload_result["items"]
if not uploads:
    st.info("No documents have been uploaded. Use the Course Documents page first.")
    st.stop()

st.subheader("1. Select source document")
labels = {u["upload_id"]: f'{u["filename"]} — {u["review_status"]}' for u in uploads}
upload_id = st.selectbox("Uploaded document", list(labels), index=list(labels).index(st.session_state.get("review_upload")) if st.session_state.get("review_upload") in labels else 0, format_func=labels.get)
source = api("GET", f"/api/v1/catalog/uploads/{upload_id}")
if source is None:
    st.stop()
for warning in source["extraction_warnings"]:
    st.warning(warning)
if source["review_status"] == "blocked_incomplete":
    st.error("This document has unreadable pages. Correct and re-upload before approval.")
with st.expander("Review original extracted sections", expanded=False):
    for chunk in source["chunks"]:
        st.markdown(f'**{chunk["metadata"].get("section", "Section")}**')
        st.text(chunk["text"])

rejected = source["review_status"] == "rejected" or source["approval_status"] == "rejected"
if rejected:
    st.error("This document was rejected. Upload a corrected source document for a new review.")
    st.write(f'Rejected by {source.get("rejected_by")} at {source.get("rejected_at")}')
    st.text(source.get("rejection_reason") or "No reason recorded")
with st.expander("Document review history", expanded=rejected):
    history = source.get("review_history", [])
    if not history:
        st.info("No document rejection decisions recorded.")
    for event in history:
        st.write(f'{event["action"]} — {event["reviewer"]} — {event["recorded_at"]}')
        st.text(event.get("reason", ""))

with st.expander("Reject source document", expanded=False):
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

st.subheader("2. Verify structured course information")
st.write("Enter details from the source document. Do not guess missing prices or prerequisites.")
with st.expander("Extract course metadata suggestions"):
    st.caption("Suggestions are unapproved. Select each course separately, inspect its evidence, and verify every field.")
    with st.form("extract_" + upload_id):
        extraction_reviewer = reviewer
        method = st.selectbox("Extraction method", ["deterministic", "gemini"],
                              help="Gemini uses your configured API and may incur costs. Deterministic parsing runs locally.")
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
    level = st.selectbox("Level", levels, index=levels.index(suggested.get("level", "Unknown")))
    delivery = st.selectbox("Training format", formats, index=formats.index(suggested.get("training_format", "Unknown")))
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

st.divider()
st.subheader("3. Publication and withdrawal")
records = api("GET", "/api/v1/catalog/staff/courses")
if records:
    for course in records["items"]:
        with st.expander(f'{course["course_id"]} — {course["title"]} [{course["status"]}]'):
            st.caption("Reviewed source: " + course["source_sha256"][:12])
            st.write(f'**Reviewed by:** {course["reviewer"]}')
            if course["indexing_error"]:
                st.warning(f'Last indexing attempt failed: {course["indexing_error"]}')
            col1, col2 = st.columns(2)
            with col1:
                if course["status"] == "published":
                    if st.button("Refresh search information", key="refresh_" + course["course_id"]):
                        result = api("POST", f'/api/v1/catalog/staff/courses/{course["course_id"]}/refresh-index')
                        if result:
                            st.success("Reviewed course index refreshed.")
                if course["status"] in ("approved", "index_failed"):
                    if st.button("Publish course", key="pub_" + course["course_id"]):
                        with st.spinner("Preparing the course for learner search..."):
                            result = api("POST", f'/api/v1/catalog/staff/courses/{course["course_id"]}/publish')
                        if result:
                            st.success(f'Course published. Learners can now browse it and ask REX about it.')
                            st.rerun()
            with col2:
                user = reviewer
                confirmed = st.checkbox("Confirm withdrawal", key="confirm_" + course["course_id"])
                if st.button("Withdraw course", key="remove_" + course["course_id"],
                             disabled=course["status"] == "withdrawn"):
                    if not confirmed or not user.strip():
                        st.error("Enter the reviewer and confirm withdrawal.")
                    else:
                        result = api("POST", f'/api/v1/catalog/staff/courses/{course["course_id"]}/withdraw',
                                     json={"reviewer": user})
                        if result:
                            st.success("Public access revoked immediately.")
                            st.rerun()
