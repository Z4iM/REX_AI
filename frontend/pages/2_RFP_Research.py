from backend.app.agents.rfp.sources import parse_upload, SourceError
import streamlit as st
from frontend.ui import api, header, require_staff, done, diagnostics

status = header("Training opportunities", "Faris's RFP agent · Find and review training opportunities in Egypt and Saudi Arabia.")
require_staff()
tab_list, tab_import, tab_alerts = st.tabs(["Opportunities", "Add opportunities", "Alerts & activity"])
with tab_list:
    country = st.selectbox("Country", ["All", "Egypt", "Saudi Arabia"])
    query = st.text_input("Search opportunities")
    params = {"q": query, "limit": 100}
    if country != "All":
        params["country"] = "EG" if country == "Egypt" else "SA"
    result = api("GET", "/api/v1/rfp/opportunities", params=params)
    if result and not result["items"]:
        st.info("No opportunities yet. Import a file in Add opportunities, or use the TA demo examples.")
    for item in (result or {}).get("items", []):
        with st.expander(item["title"]):
            st.write(f'{item["issuer"]} · {item["country_code"]} · Deadline: {item["deadline"] or "Needs verification"}')
            if item["data_mode"] == "synthetic_demo":
                st.warning("Fictional TA example — not a live tender.")
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
            new_status = st.selectbox("Next action", ["new", "reviewing", "applying", "submitted", "dismissed", "expired"],
                                      index=["new", "reviewing", "applying", "submitted", "dismissed", "expired"].index(item["workflow_status"]), key=f'status_{item["id"]}')
            notes = st.text_area("Your review notes", value=item.get("reviewer_notes") or "", key=f'notes_{item["id"]}')
            if st.button("Save opportunity review", key=f'save_{item["id"]}'):
                if api("PATCH", f'/api/v1/rfp/opportunities/{item["id"]}', json={"workflow_status": new_status, "reviewer_notes": notes}):
                    done("Opportunity review saved.")
            diagnostics(item)
with tab_import:
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
            st.error("Choose a valid JSON, CSV, or Excel file with 1 to 200 opportunities, under 10 MB. Use the examples folder as a reference.")
    with st.expander("Search configured sources online"):
        st.write("This searches the sources configured by Faris. Results may need manual verification and API usage may incur costs.")
        if st.button("Run online source search", disabled=bool(status and status["mode"] == "demo")):
            with st.spinner("Checking configured sources..."):
                report = api("POST", "/api/v1/rfp/run", json={"use_gemini": True, "notify": False})
            if report:
                st.success(f'{report["new_count"]} new opportunities found.')
                diagnostics(report, "Source search report")
with tab_alerts:
    result = api("GET", "/api/v1/rfp/notifications")
    for item in (result or {}).get("items", []):
        st.info(item["message"])
    activity = api("GET", "/api/v1/rfp/activity")
    if activity:
        st.subheader("Rejected by the checks")
        st.dataframe(activity["rejected"], hide_index=True, width="stretch")
        diagnostics(activity["runs"], "Source run history")
