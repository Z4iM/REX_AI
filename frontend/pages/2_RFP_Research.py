from backend.app.agents.rfp.sources import parse_upload, SourceError
import streamlit as st
from frontend.ui import api, header, require_staff, done, diagnostics
from frontend.components import record_picker, task_view

# Source IDs accepted by the RFP API; the page can reload independently of backend modules.
RFP_WEB_SOURCES = ("langsearch_web_discovery", "egypt_training_listings", "saudi_etimad_listings")

status = header("Training opportunities", "Find and review training opportunities in Egypt and Saudi Arabia.")
require_staff()
view = task_view("opportunity_view", ["Browse opportunities", "Add opportunities", "Alerts and activity"])
if view == "Browse opportunities":
    country = st.radio("Country", ["All", "Egypt", "Saudi Arabia"], horizontal=True)
    query = st.text_input("Search opportunities")
    params = {"q": query, "limit": 100}
    if country != "All":
        params["country"] = "EG" if country == "Egypt" else "SA"
    result = api("GET", "/api/v1/rfp/opportunities", params=params)
    if result and not result["items"]:
        st.info("No opportunities found. Clear your search or choose Add opportunities to import a file.")
    opportunities=(result or {}).get("items", [])
    selected=record_picker(opportunities,key="opportunity-selected",label="opportunities",searchable=False,
        details=lambda r:r["issuer"]+" · "+r["country_code"]+" · Deadline: "+str(r.get("deadline") or "Check with issuer")) if opportunities else None
    for item in [r for r in opportunities if r["id"]==selected]:
        with st.container(border=True):
            st.subheader(item["title"])
            st.write(f'{item["issuer"]} · {item["country_code"]} · Deadline: {item["deadline"] or "Needs verification"}')
            if item["data_mode"] == "synthetic_demo":
                st.warning("Fictional example — not a live tender.")
            st.write(item.get("summary") or item.get("description") or "No summary provided.")
            priority = {"high": "High priority (Egypt)", "monitor": "Monitor (Saudi Arabia)"}.get(item["priority"], "Priority needs review")
            st.caption(priority + " · " + ("Passed automatic filters" if item["filter_status"] == "accepted" else "Needs staff verification"))
            if item.get("review_reason"):
                st.warning(item["review_reason"])
            if item.get("eligibility"):
                st.write("**Eligibility requirements:** " + item["eligibility"])
            if item.get("eligibility_notes"):
                st.info("AI eligibility opinion — requires staff verification: " + item["eligibility_notes"])
            st.caption("Changing status tracks your work. It does not submit an application.")
            if item.get("source_url") and item["data_mode"] != "synthetic_demo":
                st.link_button("Open original source", item["source_url"])
            new_status = st.radio("Next action", ["new", "reviewing", "applying", "submitted", "dismissed", "expired"], horizontal=True,
                                      index=["new", "reviewing", "applying", "submitted", "dismissed", "expired"].index(item["workflow_status"]), key=f'status_{item["id"]}')
            notes = st.text_area("Your review notes", value=item.get("reviewer_notes") or "", key=f'notes_{item["id"]}')
            if st.button("Save opportunity review", key=f'save_{item["id"]}'):
                if api("PATCH", f'/api/v1/rfp/opportunities/{item["id"]}', json={"workflow_status": new_status, "reviewer_notes": notes}):
                    done("Opportunity review saved.")
            diagnostics(item)
if view == "Add opportunities":
    st.write("Import a JSON, CSV, or Excel export of opportunities. The agent checks countries, deadlines, relevance, and duplicates.")
    uploaded = st.file_uploader("Opportunity file", type=["json", "csv", "xlsx"])
    summarize = st.checkbox("Ask AI to summarize new opportunities", value=False)
    if st.button("Import and check opportunities", disabled=uploaded is None, type="primary"):
        try:
            if uploaded.size > 10 * 1024 * 1024:
                raise ValueError("File too large")
            items = parse_upload(uploaded.name, uploaded.getvalue())
            if not 1 <= len(items) <= 200:
                raise ValueError("Use 1 to 200 records")
            report = api("POST", "/api/v1/rfp/import", json={"items": items, "use_gemini": summarize})
            if report:
                st.success(f'{report["new"]} saved · {report["rejected"]} rejected · {report["duplicates"]} duplicates · {report["already_known"]} already saved')
                diagnostics(report, "Import results")
        except (ValueError, TypeError, SourceError):
            st.error("Choose a valid JSON, CSV, or Excel file with 1 to 200 opportunities and a size of 10 MiB or less.")
    with st.expander("Search public tenders"):
        st.write("Checks LangSearch and public tender directories for Egypt and Saudi Arabia. Verify the original notice before acting.")
        if st.button("Run online source search", disabled=bool(status and status["mode"] == "demo")):
            st.session_state.pop("langsearch_report", None)
            with st.spinner("Checking configured sources..."):
                report = api("POST", "/api/v1/rfp/run", json={"sources": list(RFP_WEB_SOURCES), "use_gemini": False, "notify": False})
            if report:
                st.session_state["langsearch_report"] = report
        if report := st.session_state.get("langsearch_report"):
            sources = report["sources"]
            for source in sources:
                name = source["source"].replace("_", " ").capitalize()
                if source["status"] != "ok":
                    st.warning(f'{name}: {source.get("error") or "Search did not run."}')
                elif "queries_attempted" in source:
                    completed, attempted = source["queries_completed"], source["queries_attempted"]
                    st.caption(f'LangSearch: {completed} of {attempted} searches completed · {source["indexed_results"]} indexed results')
                    if completed < attempted:
                        st.warning("Some LangSearch queries did not complete.")
                else:
                    st.caption(f'{name}: {source.get("fetched", 0)} notices checked')
            checked = sum(source.get("fetched", 0) for source in sources)
            saved, rejected = report["new_count"], report["rejected"]
            st.write(f"**{checked} notices checked · {saved} newly saved · {rejected} rejected**")
            if saved:
                st.success("New opportunities are ready for staff review in Browse opportunities.")
                if st.button("Browse saved opportunities"):
                    st.session_state["opportunity_view"] = "Browse opportunities"
                    st.rerun()
            elif any(source["status"] == "ok" for source in sources):
                st.info("No new opportunities saved. Matching notices may already be saved or may have closed.")
            if rejected and st.button("See why notices were rejected"):
                st.session_state["opportunity_view"] = "Alerts and activity"
                st.rerun()
            diagnostics(report, "Technical search report")
if view == "Alerts and activity":
    result = api("GET", "/api/v1/rfp/notifications")
    if result is not None and not result["items"]:
        st.info("No new alerts. Relevant opportunities appear here after an import or search.")
    for item in (result or {}).get("items", []):
        st.info(item["message"])
    activity = api("GET", "/api/v1/rfp/activity")
    if activity:
        st.subheader("Rejected by the checks")
        if activity["rejected"]:
            st.dataframe(activity["rejected"], hide_index=True, width="stretch")
        else:
            st.caption("No rejected opportunities have been recorded.")
        diagnostics(activity["runs"], "Source run history")
