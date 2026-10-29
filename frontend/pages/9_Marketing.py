"""Campaign creation and human review with traceable curriculum handoffs."""
import json
import streamlit as st
from frontend.ui import api, header, require_staff, done
from frontend.components import record_picker, timeline

header("Campaign studio", "Turn approved courses and curricula into reviewed, multi-channel marketing content.")
reviewer = require_staff()
create, review = st.tabs(["Create a campaign", "Review and export"])
courses = api("GET", "/api/v1/catalog/courses")
curricula = api("GET", "/api/v1/curriculum", params={"status": "approved"})
campaigns = api("GET", "/api/v1/marketing")
if courses is None or curricula is None or campaigns is None:
    st.stop()
course_labels = {c["course_id"]: f'{c["title"]} ({c["course_id"]})' for c in courses["items"]}
approved = {c["id"]: c for c in curricula["items"]}
names = {"social_caption": "Social media captions", "facebook_instagram": "Facebook / Instagram ads",
         "linkedin": "LinkedIn posts", "email": "Email marketing", "whatsapp": "WhatsApp messages",
         "headline": "Campaign headlines", "cta": "Calls to action"}
with create:
    st.info("Campaigns use published facts and an approved teaching plan. Generated content stays a draft until reviewed. Sending and publishing remain manual.")
    if not approved or not course_labels:
        st.warning("Publish a course and approve its curriculum before creating a campaign.")
        st.page_link("pages/8_Curriculum.py", label="Open curriculum studio", icon=":material/account_tree:")
    else:
        options = list(approved)
        preferred = st.session_state.get("approved_curriculum_id")
        curriculum_id = st.radio("Approved curriculum", options, index=options.index(preferred) if preferred in options else 0,
                                     format_func=lambda x: f'#{x} · {approved[x]["title"]}')
        valid_codes = [s["course_id"] for s in approved[curriculum_id]["source_records"] if s["course_id"] in course_labels]
        with st.form("campaign_create"):
            course_id = st.radio("Course to promote", valid_codes, format_func=course_labels.get)
            audience = st.text_input("Who do you want to reach?", max_chars=400)
            objective = st.text_area("Campaign goal", value="Help prospective learners understand the course and contact admissions.", max_chars=1000)
            language = st.radio("Campaign language", ["en", "ar"], horizontal=True, format_func=lambda x: "English" if x == "en" else "Arabic")
            channels = st.pills("Channels", list(names), default=list(names), selection_mode="multi", format_func=names.get)
            budget = st.number_input("Planning budget in EGP (optional)", min_value=0., max_value=10000000., value=0.)
            generate = st.form_submit_button("Generate campaign draft", type="primary", disabled=not valid_codes)
        if generate:
            if len(audience.strip()) < 3 or not channels:
                st.error("Describe the audience and choose at least one channel.")
            else:
                with st.spinner("Preparing campaign variations from approved information..."):
                    result = api("POST", "/api/v1/marketing", json={"course_id": course_id, "curriculum_id": curriculum_id,
                        "requester": reviewer, "audience": audience, "objective": objective, "language": language,
                        "channels": channels, "budget_egp": budget or None})
                if result:
                    st.session_state["campaign_selected"] = result["id"]
                    done("Campaign draft saved. Open Review and export to check its claims and approve it.")
with review:
    records = {r["id"]: r for r in campaigns["items"]}
    if not records:
        st.info("No campaign drafts yet. Create a campaign after approving a curriculum.")
    else:
        selected=record_picker(list(records.values()),key="campaign_selected",label="campaigns")
        if selected is None:
            st.stop()
        record = api("GET", "/api/v1/marketing/" + selected)
        if record:
            st.subheader(record["content"]["title"])
            st.caption(f'{record["status"].replace("_", " ").title()} · Version {record["version"]} · {record["course"]["title"]}')
            st.write(record["content"]["strategy"])
            for channel in record["content"]["channels"]:
                with st.container(border=True):
                    st.markdown("**"+names[channel["channel"]]+"**")
                    for i, text in enumerate(channel["variations"], 1):
                        st.markdown(f"**Variation {i}**")
                        st.write(text)
            if record["status"] == "pending_review":
                with st.form("campaign_review"):
                    decision = st.radio("Campaign review decision", ["approve", "request_revision", "reject"], horizontal=True, format_func=lambda x: x.replace("_", " ").title())
                    reason = st.text_area("Campaign review reason", max_chars=4000)
                    confirmed = st.checkbox("I verified course facts, claims, offers and every channel variation")
                    save = st.form_submit_button("Save campaign review", type="primary")
                if save:
                    if not confirmed or len(reason.strip()) < 3:
                        st.error("Explain the decision and confirm the review.")
                    elif api("POST", f"/api/v1/marketing/{selected}/review", json={"reviewer": reviewer, "decision": decision, "reason": reason}):
                        done("Campaign review saved.")
            with st.expander("Edit content and create a new revision"):
                with st.form("campaign_revision"):
                    content = {"title": st.text_input("Campaign title", value=record["content"]["title"]),
                               "strategy": st.text_area("Campaign strategy", value=record["content"]["strategy"]), "channels": []}
                    for channel in record["content"]["channels"]:
                        texts = [st.text_area(f'{names[channel["channel"]]} · variation {i+1}', value=t,
                                 key=f'{selected}-{channel["channel"]}-{i}') for i, t in enumerate(channel["variations"])]
                        content["channels"].append({"channel": channel["channel"], "variations": texts})
                    instructions = st.text_area("What changed in this revision?", max_chars=4000)
                    revise = st.form_submit_button("Save revised campaign draft")
                if revise:
                    if not instructions.strip():
                        st.error("Describe the revision before saving.")
                    else:
                        result = api("POST", "/api/v1/marketing", json={"course_id": record["course"]["course_id"],
                            "curriculum_id": record["curriculum"]["id"], "requester": reviewer, "audience": record["audience"],
                            "objective": record["objective"], "language": record["language"],
                            "channels": [c["channel"] for c in content["channels"]], "revision_of": selected,
                            "revision_instructions": instructions, "edited_content": content})
                        if result:
                            st.session_state["campaign_selected"] = result["id"]
                            done("Revised campaign saved as a new draft. The previous version is preserved.")
            if record["status"] == "approved":
                data = api("GET", f"/api/v1/marketing/{selected}/export", binary=True)
                if data:
                    st.download_button("Download approved campaign", data, file_name=f"campaign-{selected}.json", mime="application/json", icon=":material/download:")
                    st.caption("Use the approved content in your chosen channel. REX does not send messages or publish posts automatically.")
            st.subheader("Review history")
            timeline(record["history"])
            with st.expander("Original course and teaching plan"):
                st.write(record["course"]["title"])
                st.caption("Teaching plan #"+str(record["curriculum"]["id"]))
                if st.session_state.get("show_technical_details"):
                    st.json(record["course"])
