"""Staff curriculum design, review, evidence and immutable revisions."""
import json
import streamlit as st
from frontend.ui import api, header, require_staff, done
from frontend.components import record_picker, timeline, next_step, readable
from backend.app.agents.curriculum.models import CurriculumContent

header("Curriculum studio", "Design a teaching plan from published course sources, then review it before use.")
reviewer = require_staff()
tab_create, tab_review, tab_frameworks = st.tabs(["Design a curriculum", "Review and revise", "Framework references"])
courses = api("GET", "/api/v1/catalog/courses")
saved = api("GET", "/api/v1/curriculum")
frameworks = api("GET", "/api/v1/curriculum/frameworks")
if courses is None or saved is None or frameworks is None:
    st.stop()
labels = {c["course_id"]: f'{c["title"]} ({c["course_id"]})' for c in courses["items"]}
verified = {fw["id"]: fw for fw in frameworks["items"] if fw.get("reviewed_at")}
with tab_create:
    st.info("Start with a published course. Generated modules and activities are proposed teaching content until a reviewer approves them.")
    if not labels:
        st.warning("Publish a reviewed course first. Then return here to design its curriculum.")
    chosen = st.pills("Published source courses", list(labels), format_func=labels.get, selection_mode="multi") or []
    source = next((c for c in courses["items"] if chosen and c["course_id"] == chosen[0]), {})
    with st.form("curriculum_create"):
        subject = st.text_input("What course are you designing?", value=source.get("title", ""), max_chars=500, key="subject-" + ",".join(chosen))
        left, right = st.columns(2)
        with left:
            level = st.radio("Learner level", ["Beginner", "Intermediate", "Advanced"], horizontal=True)
            hours = st.number_input("Total training hours", min_value=1.0, max_value=5000.0, value=float(source.get("duration_hours") or 20), key="hours-" + ",".join(chosen),
                                    help="For one source course, hours must match its published duration. Update and review the course facts first if its duration has changed.")
            language = st.radio("Curriculum language", ["English", "Arabic"], horizontal=True)
        with right:
            audience = st.text_input("Who is this course for?", max_chars=300)
            department = st.text_input("Department", max_chars=200)
            industry = st.text_input("Industry", max_chars=200)
        country = st.radio("Country", ["", "Egypt", "Saudi Arabia"], horizontal=True, format_func=lambda x:x or "Not specified")
        requirements = st.text_area("Teaching goals and practical requirements", max_chars=4000)
        framework = st.selectbox("Optional verified framework", [None, *verified],
                                 format_func=lambda x: "No accreditation comparison" if x is None else verified[x]["name"])
        research = st.form_submit_button("Research approved source topics", disabled=not labels)
        generate = st.form_submit_button("Generate curriculum draft", type="primary", disabled=not labels)
    if research or generate:
        if not chosen or len(chosen)>5 or len(subject.strip()) < 2:
            st.error("Select one to five source courses and enter the course subject.")
        else:
            with st.spinner("Reading the approved sources and preparing the teaching plan..."):
                if research:
                    result = api("POST", "/api/v1/curriculum/research", json={"subject": subject, "course_ids": chosen,
                                "skill_level": level, "industry": industry, "country": country})
                    if result:
                        st.session_state["curriculum_research"] = result
                else:
                    result = api("POST", "/api/v1/curriculum", json={"subject": subject, "course_ids": chosen,
                                "skill_level": level, "duration_hours": hours, "language": language,
                                "target_audience": audience, "department": department, "industry": industry,
                                "country": country, "additional_requirements": requirements,
                                "accreditation_framework_id": framework})
                    if result:
                        st.session_state["curriculum_selected"] = result["id"]
                        done("Curriculum draft saved. Open Review and revise to inspect it and submit it for approval.")
    if st.session_state.get("curriculum_research"):
        with st.container(border=True):
            st.subheader("Topics found in your approved sources")
            readable(st.session_state["curriculum_research"])

with tab_review:
    items = {c["id"]: c for c in saved["items"]}
    if not items:
        st.info("No curricula yet. Use Design a curriculum to create the first draft.")
    else:
        selected = record_picker(list(items.values()),key="curriculum_selected",label="teaching plans")
        if selected is None:
            st.stop()
        c = api("GET", f"/api/v1/curriculum/{selected}")
        if c:
            st.subheader(c["title"])
            a, b, d = st.columns(3)
            a.metric("Review status", c["status"].replace("_", " ").title())
            b.metric("Training hours", c["training_hours"])
            d.metric("Modules", len(c["modules"]))
            st.write(c["description"])
            for label, key in [("Objectives", "objectives"), ("Learning outcomes", "learning_outcomes"), ("Prerequisites", "prerequisites")]:
                with st.container(border=True):
                    st.markdown("**" + label + "**")
                    for line in c[key]:
                        st.write("• " + line)
            for m in c["modules"]:
                with st.container(border=True):
                    st.markdown(f'**Module {m["module_number"]}: {m["title"]} · {m["duration_hours"]} hours**')
                    st.write(m["description"])
                    st.write("Topics: " + "; ".join(m["topics"]))
                    st.write("Outcomes: " + "; ".join(m["learning_outcomes"]))
                    st.write("Activities: " + "; ".join(m["activities"]))
            with st.container(border=True):
                st.markdown("**Practice and assessment**")
                for key in ("practical_exercises", "assessments", "capstone_project"):
                    st.write(key.replace("_", " ").title())
                    entries=c[key] if isinstance(c[key],list) else [c[key]]
                    for entry in entries:
                        st.markdown("**"+entry.get("title", "")+"**")
                        for field,value in entry.items():
                            if field != "title":
                                st.write(field.replace("_"," ").title()+": "+(", ".join(map(str,value)) if isinstance(value,list) else str(value)))
            if c["alignment_report"]:
                st.warning("Proposed alignment only. This is not official accreditation.")
                readable(c["alignment_report"])
            if c["status"] == "draft":
                if st.button("Submit this draft for review", type="primary"):
                    if api("POST", f"/api/v1/curriculum/{selected}/submit"):
                        done("Curriculum submitted for human review.")
                if verified:
                    fw = st.selectbox("Compare with a verified framework", list(verified), format_func=lambda x: verified[x]["name"])
                    if st.button("Run alignment analysis"):
                        with st.spinner("Comparing approved framework criteria..."):
                            if api("POST", f"/api/v1/curriculum/{selected}/alignment", json={"framework_id": fw}):
                                done("Alignment report saved for review.")
            if c["status"] == "pending_review":
                with st.form("curriculum_review"):
                    decision = st.radio("Curriculum decision", ["approve", "request_revision"], format_func=lambda x: x.replace("_", " ").title())
                    notes = st.text_area("Review notes and reason", max_chars=4000)
                    checked = st.checkbox("I checked source facts, hours, assessments and the teaching plan")
                    submit = st.form_submit_button("Save curriculum review", type="primary")
                if submit:
                    if not checked or not notes.strip():
                        st.error("Add review notes and confirm you checked the complete plan.")
                    elif api("POST", f"/api/v1/curriculum/{selected}/review", json={"action": decision, "reviewer_name": reviewer, "notes": notes}):
                        done("Curriculum review saved.")
            with st.expander("Edit the plan and save a new draft revision"):
                st.caption("The existing version is preserved. Changed hours must still add up, and assessment weights must total 100%.")
                with st.form("curriculum_revision"):
                    content = CurriculumContent.model_validate(c).model_dump()
                    content["title"] = st.text_input("Revised title", value=content["title"])
                    content["description"] = st.text_area("Revised course description", value=content["description"])
                    content["objectives"] = st.text_area("Objectives · one per line", value="\n".join(content["objectives"])).splitlines()
                    content["learning_outcomes"] = st.text_area("Learning outcomes · one per line", value="\n".join(content["learning_outcomes"])).splitlines()
                    for i, m in enumerate(content["modules"]):
                        st.markdown(f'**Module {i+1}**')
                        m["title"] = st.text_input("Module title", m["title"], key=f"mt{selected}-{i}")
                        m["description"] = st.text_area("Module description", m["description"], key=f"md{selected}-{i}")
                        m["topics"] = st.text_area("Topics · one per line", "\n".join(m["topics"]), key=f"mp{selected}-{i}").splitlines()
                        m["duration_hours"] = st.number_input("Module hours", min_value=.25, max_value=5000., value=float(m["duration_hours"]), key=f"mh{selected}-{i}")
                    content["training_hours"] = sum(m["duration_hours"] for m in content["modules"])
                    reason = st.text_area("Why are you revising this plan?", max_chars=4000)
                    with st.expander("Advanced: edit exercises, assessments or add modules"):
                        advanced = st.text_area("Complete curriculum JSON (optional override)", value="", height=220,
                                                help="Leave blank to use the fields above. Paste a complete curriculum object to make structural changes.")
                    revise = st.form_submit_button("Save as a new curriculum draft")
                if revise:
                    try:
                        edited = json.loads(advanced) if advanced.strip() else content
                        if len(reason.strip()) < 3:
                            raise ValueError("Explain the revision reason.")
                        CurriculumContent.model_validate(edited)
                        result = api("POST", f"/api/v1/curriculum/{selected}/revise", json={"content": edited, "reviewer_name": reviewer, "reason": reason})
                        if result:
                            st.session_state["curriculum_selected"] = result["id"]
                            done("New draft revision saved. Submit it for a fresh review.")
                    except ValueError as exc:
                        st.error(str(exc))
                st.download_button("Download editable curriculum JSON", json.dumps(content, ensure_ascii=False, indent=2), file_name=f"curriculum-{selected}.json")
            if c["status"] in ("draft", "pending_review", "approved"):
                if st.button("Prepare curriculum PDF", icon=":material/picture_as_pdf:"):
                    data = api("GET", f"/api/v1/curriculum/{selected}/pdf", binary=True)
                    if data:
                        st.download_button("Download curriculum PDF", data, file_name=f"curriculum-{selected}.pdf", mime="application/pdf")
            if c["status"] == "approved":
                st.success("Ready for Document studio and Campaign studio. Both will use this approved version as a source.")
                st.session_state["approved_curriculum_id"] = selected
                st.page_link("pages/5_Document_Generation.py", label="Create training documents", icon=":material/description:")
                st.page_link("pages/9_Marketing.py", label="Create a marketing campaign", icon=":material/campaign:")
            st.subheader("Review history")
            timeline(c["revision_history"])
            with st.expander("Original course sources"):
                for source in c["source_records"]:
                    st.write(source["title"]+" · "+source["course_id"])
                if st.session_state.get("show_technical_details"):
                    st.json(c["source_records"])

with tab_frameworks:
    st.info("Built-in framework summaries are starting references. Verify the original standard, its version and the criteria before using alignment. No framework listing is an accreditation claim.")
    mapping = {fw["id"]: fw for fw in frameworks["items"]}
    if mapping:
        fid = st.selectbox("Framework reference", list(mapping), format_func=lambda x: mapping[x]["name"])
        fw = mapping[fid]
        st.write(fw["description"])
        st.caption("Verified by " + fw["reviewed_by"] if fw.get("reviewed_by") else "Not verified for alignment")
        with st.form("framework_review"):
            url = st.text_input("Official reference URL", value=fw["url"])
            version = st.text_input("Reference version / update date", value=fw["last_updated"])
            excerpt = st.text_area("Verified source excerpt", value=fw.get("source_excerpt") or "", max_chars=10000)
            criteria = st.text_area("Verified competencies · one per line", value="\n".join(fw["competencies"]), height=180)
            confirmed = st.checkbox("I verified these criteria against the referenced standard")
            approve = st.form_submit_button("Save verified framework reference")
        if approve:
            if not confirmed:
                st.error("Verify the reference before approving it.")
            elif api("POST", f"/api/v1/curriculum/frameworks/{fid}/approve", json={"reviewer_name": reviewer,
                     "source_url": url, "source_version": version, "source_excerpt": excerpt,
                     "competencies": [x.strip() for x in criteria.splitlines() if x.strip()]}):
                done("Framework reference verified and ready for proposed alignment.")
