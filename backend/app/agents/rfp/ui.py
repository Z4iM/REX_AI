"""
Streamlit view for the RFP agent, written as a function so it can live inside the EXISTING REX AI Streamlit app:

    from app.agents.rfp.ui import render
    render(session_factory=my_factory, authenticated=True)   # host app already authenticated the staff user

Standalone: `streamlit run dashboard.py` (project root) - protect it with RFP_DASHBOARD_PASSWORD.
render() never calls st.set_page_config (the host app owns the page) and prefixes every widget key.
"""
from __future__ import annotations

import hmac
import json
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from . import config, db, service
from . import sources as sources_mod

COUNTRY_LABEL = {"EG": "Egypt", "SA": "Saudi Arabia"}
ASSESS_LABEL = {"likely_eligible": "Likely eligible (unverified)", "unclear": "Unclear",
                "unlikely_eligible": "Unlikely eligible (unverified)"}


def _priority_label(priority, filter_status) -> str:
    verified = filter_status == "accepted"
    if priority == "high":
        return "🔴 Egypt - priority" if verified else "🟠 Egypt - priority for VERIFICATION"
    if priority == "monitor":
        return "🟡 Saudi - monitor" if verified else "🟤 Saudi - needs verification"
    return "⚪ Needs verification"


@st.cache_resource
def _default_factory(url: str):
    return db.get_session_factory(url)


def _login_gate(kp: str) -> None:
    """Optional password gate for the standalone dashboard. The host app should pass authenticated=True instead."""
    pwd = config.dashboard_password()
    if not pwd:
        if config.require_dashboard_login():
            st.error("RFP_REQUIRE_LOGIN is set but RFP_DASHBOARD_PASSWORD is empty - refusing to show the dashboard.")
            st.stop()
        st.warning("No dashboard login configured (set RFP_DASHBOARD_PASSWORD). Use this dashboard on a trusted "
                   "local machine only - it can edit workflow status and import data.")
        return
    if st.session_state.get(f"{kp}authed"):
        return
    st.title("📑 REX AI - RFP Dashboard")
    entered = st.text_input("Password", type="password", key=f"{kp}password")
    if st.button("Sign in", key=f"{kp}signin"):
        if hmac.compare_digest(entered.encode(), pwd.encode()):
            st.session_state[f"{kp}authed"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    st.stop()


def render(session_factory=None, *, authenticated: bool = False, key_prefix: str = "rfp_") -> None:
    kp = key_prefix
    k = lambda name: f"{kp}{name}"          # noqa: E731
    SessionLocal = session_factory or _default_factory(config.database_url())

    if not authenticated:
        _login_gate(kp)

    def flash(kind: str, text: str):
        st.session_state.setdefault(k("flash"), []).append((kind, text))

    for kind, text in st.session_state.pop(k("flash"), []):
        getattr(st, kind)(text)

    with SessionLocal() as s:
        unread = s.scalar(select(func.count()).select_from(db.Notification)
                          .where(db.Notification.is_read.is_(False))) or 0

    st.title("📑 REX AI - RFP & Tender Opportunities")
    st.caption("Egypt and Saudi Arabia only. Items marked *verification* are leads, **not confirmed open opportunities**. "
               "AI summaries and eligibility notes are unverified - check the source before acting.")

    # ------------------------------------------------------------------ filters
    sb = st.sidebar
    sb.header("RFP search & filters")
    q = sb.text_input("Search (title, issuer, ID, summary...)", key=k("q"))
    country = sb.selectbox("Country", ["All", "Egypt", "Saudi Arabia"], key=k("country"))
    priority = sb.selectbox("Priority", ["All", "high", "monitor"], key=k("priority"))
    wf = sb.selectbox("Workflow status", ["All"] + db.WORKFLOW_STATUSES, key=k("wf"))
    fstat = sb.selectbox("Verification", ["All", "accepted", "needs_review"], key=k("fstat"))
    assess = sb.selectbox("Eligibility opinion", ["All", "likely_eligible", "unclear", "unlikely_eligible"],
                          key=k("assess"))
    mode = sb.selectbox("Data origin", ["All"] + list(service.TRUST_POLICY), key=k("mode"))
    use_dates = sb.checkbox("Filter by deadline range", key=k("use_dates"))
    d_from = d_to = None
    if use_dates:
        d_from = sb.date_input("Deadline from", date.today(), key=k("d_from"))
        d_to = sb.date_input("Deadline to", date(date.today().year + 1, 12, 31), key=k("d_to"))
    show_expired = sb.checkbox("Include expired", key=k("show_expired"))
    page_size = sb.selectbox("Rows per page", [25, 50, 100, 250], index=1, key=k("page_size"))
    page = sb.number_input("Page", min_value=1, value=1, step=1, key=k("page"))

    with SessionLocal() as s:
        rows = db.search_opportunities(
            s, q=q or None, country={"Egypt": "EG", "Saudi Arabia": "SA"}.get(country),
            priority=None if priority == "All" else priority, workflow_status=None if wf == "All" else wf,
            filter_status=None if fstat == "All" else fstat, assessment=None if assess == "All" else assess,
            data_mode=None if mode == "All" else mode, include_expired=show_expired, deadline_from=d_from,
            deadline_to=d_to, limit=int(page_size), offset=(int(page) - 1) * int(page_size))
        all_active = db.search_opportunities(s)
        data = [db.to_dict(o) for o in rows]
        history = {}

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Active leads", len(all_active))
    c2.metric("Egypt - priority", sum(o.priority == "high" for o in all_active))
    c3.metric("Saudi - monitored", sum(o.priority == "monitor" for o in all_active))
    c4.metric("Need verification", sum(o.filter_status == "needs_review" for o in all_active))
    c5.metric("Unread alerts", unread)

    if any(d["data_mode"] == "synthetic_demo" for d in data):
        st.warning("Some rows are **synthetic demo data**, not real tenders.")
    if any(d["data_mode"] in ("search_discovered", "llm_extracted") for d in data):
        st.info("Rows from AI search / LLM extraction are **unverified leads** - verify them on the source page.")

    tab_opps, tab_alerts, tab_run, tab_logs = st.tabs(["Opportunities", f"Alerts ({unread})", "Run & Import", "Logs"])

    # ------------------------------------------------------------------ opportunities
    with tab_opps:
        st.write(f"**{len(data)}** result(s) on this page")
        if data:
            df = pd.DataFrame(data)
            view = pd.DataFrame({
                "ID": df["id"],
                "Priority": [_priority_label(p, f) for p, f in zip(df["priority"], df["filter_status"])],
                "Country": df["country_code"].map(lambda c: COUNTRY_LABEL.get(c, "?")), "Title": df["title"],
                "Issuer": df["issuer"],
                "Deadline": [d if d is not None else "unknown" for d in df["deadline"]],
                "Topics": df["topics"], "Status": df["workflow_status"], "Verification": df["filter_status"],
                "Eligibility (AI, unverified)": df["eligibility_assessment"].map(lambda a: ASSESS_LABEL.get(a, "")),
                "Origin": df["data_mode"],
                "Source": df["source_url"],         # real portal URLs only; import references are never links
                "Import ref": df["import_reference"],
            })
            st.dataframe(view, width="stretch", hide_index=True,
                         column_config={"Source": st.column_config.LinkColumn("Source", display_text="open")})
            st.download_button("⬇️ Export this page (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                               "rfp_opportunities.csv", "text/csv", key=k("export_csv"))

            st.divider()
            labels = {d["id"]: f"#{d['id']} - {d['title'][:80]}" for d in data}
            chosen = st.selectbox("Open an opportunity", list(labels), format_func=labels.get, key=k("chosen"))
            d = next(x for x in data if x["id"] == chosen)
            left, right = st.columns([3, 2])
            with left:
                st.subheader(d["title"])
                if d["filter_status"] == "needs_review":
                    st.warning("**Not verified.** " + (d["review_reason"] or "Needs manual verification."))
                st.write(f"**Issuer:** {d['issuer']}  |  **Country:** "
                         f"{COUNTRY_LABEL.get(d['country_code'], d['country_raw'] or 'unknown')}"
                         + (f" (inferred from city '{d['country_raw']}')" if d["country_basis"] == "city_mapping" else ""))
                dl = d["deadline"] or f"unknown{' (source said: ' + d['deadline_raw'] + ')' if d['deadline_raw'] else ''}"
                st.write(f"**Published:** {d['publication_date'] or 'unknown'}  |  **Deadline:** {dl}")
                st.write(f"**Tender ID:** {d['tender_id'] or '-'}  |  **Topics:** {d['topics'] or '-'}  |  "
                         f"**Source category:** {d['category'] or '-'}")
                st.markdown("**AI summary** (generated, may contain errors)")
                st.write(d["summary"] or "_No summary available._")
                if d["eligibility_assessment"]:
                    st.markdown(f"**Eligibility opinion:** {ASSESS_LABEL.get(d['eligibility_assessment'])} - "
                                f"{d['eligibility_notes'] or ''}")
                st.markdown("**Eligibility requirements (from source)**")
                st.write(d["eligibility"] or "_Not stated._")
                if d["description"]:
                    with st.expander("Description"):
                        st.write(d["description"])
                links = []
                if d["source_url"]:
                    links.append(f"[Source page]({d['source_url']})")
                else:
                    links.append(f"No portal link - import reference: `{d['import_reference']}`")
                if d["submission_url"]:
                    links.append(f"[Submission link]({d['submission_url']})")
                st.markdown("  |  ".join(links))
                if d["also_seen_at"]:
                    st.caption("Also seen at: " + ", ".join(json.loads(d["also_seen_at"])))
                with SessionLocal() as s:
                    hist = s.scalars(select(db.OpportunityHistory).where(db.OpportunityHistory.opportunity_id == chosen)
                                     .order_by(db.OpportunityHistory.changed_at.desc())).all()
                    hist_rows = [(h.changed_at, h.field, h.old_value, h.new_value, h.source_name) for h in hist]
                if hist_rows:
                    with st.expander(f"Change history ({len(hist_rows)})"):
                        st.dataframe(pd.DataFrame(hist_rows, columns=["When", "Field", "Old", "New", "Source"]),
                                     width="stretch", hide_index=True)
            with right:
                st.markdown("**Track this opportunity**")
                new_status = st.selectbox("Workflow status", db.WORKFLOW_STATUSES,
                                          index=db.WORKFLOW_STATUSES.index(d["workflow_status"]),
                                          key=k(f"st_{chosen}"))
                notes = st.text_area("Reviewer notes", d["reviewer_notes"] or "", key=k(f"notes_{chosen}"))
                if st.button("Save", key=k(f"save_{chosen}")):
                    with SessionLocal() as s:
                        db.update_workflow(s, chosen, new_status, notes)
                    st.success("Saved")
                    st.rerun()
        else:
            st.info("No opportunities match. Go to **Run & Import** to load data.")

    # ------------------------------------------------------------------ alerts
    with tab_alerts:
        with SessionLocal() as s:
            notifs = s.scalars(select(db.Notification).order_by(db.Notification.created_at.desc()).limit(100)).all()
            items = [(n.id, n.message, n.is_read, n.created_at, n.email_sent) for n in notifs]
        if not items:
            st.info("No alerts yet. New leads create an alert (Egypt first).")
        else:
            if st.button("Mark all as read", key=k("mark_all")):
                with SessionLocal() as s:
                    for n in s.scalars(select(db.Notification).where(db.Notification.is_read.is_(False))):
                        n.is_read = True
                    s.commit()
                st.rerun()
            for nid, msg, is_read, created, emailed in items:
                st.write(("✅ " if is_read else "🔔 ") + msg + f"  \n<small>{created:%Y-%m-%d %H:%M}"
                         f"{' - emailed' if emailed else ''}</small>", unsafe_allow_html=True)

    # ------------------------------------------------------------------ run & import
    with tab_run:
        st.subheader("1) Run configured sources")
        st.caption("Sources are defined in sources.yaml (manual_imports folder, Gemini web discovery, optional portals).")
        use_g = st.checkbox("Use Gemini for summaries", value=bool(config.gemini_api_key()), key=k("use_g"))
        if st.button("▶️ Run now", key=k("run_now")):
            with st.spinner("Running sources..."), SessionLocal() as s:
                rep = service.run_all(s, sources_mod.load_sources(), use_gemini=use_g)
            t = rep.totals
            flash("success", f"New: {t.new} | needs review: {t.needs_review} | rejected: {t.rejected} | "
                             f"duplicates: {t.duplicates} | updated: {t.updated} | already known: {t.already_known}")
            for e in rep.per_source:
                flash("error" if e["status"] == "failed" else "info" if e["status"] == "skipped" else "write",
                      f"**{e['source']}** - {e['status']}" + (f": {e['error']}" if e["error"] else ""))
            st.rerun()

        st.divider()
        st.subheader("2) Import a file exported from a portal (CSV / XLSX / JSON)")
        up = st.file_uploader("File", type=["csv", "xlsx", "json"], key=k("upload"))
        only_country = st.selectbox("All rows in this file are from",
                                    ["(country column in file)", "Egypt", "Saudi Arabia"], key=k("file_country"))
        if up is not None and st.button("Import file", key=k("import_file")):
            try:
                raws = sources_mod.parse_upload(up.name, up.getvalue())
                with SessionLocal() as s:
                    r = service.ingest_raw(s, raws, f"upload:{up.name}", use_gemini=use_g,
                                           default_country=None if only_country.startswith("(") else only_country)
                flash("success", f"Read {r.fetched} rows - new: {r.new}, needs review: {r.needs_review}, "
                                 f"rejected: {r.rejected}, duplicates: {r.duplicates}, updated: {r.updated}, "
                                 f"already known: {r.already_known}, invalid: {r.invalid}")
            except Exception as e:
                flash("error", f"Import failed: {type(e).__name__}: {e}")
            st.rerun()

        st.divider()
        st.subheader("3) Paste tender text -> extract with Gemini")
        st.caption("Results are stored as unverified leads (LLM-extracted) and always need review.")
        txt = st.text_area("Tender text", height=150, key=k("paste_text"))
        src_url = st.text_input("Source URL of this text (required)", key=k("paste_url"))
        if st.button("Extract & import", key=k("extract_btn")):
            if not txt.strip() or not src_url.startswith(("http://", "https://")):
                st.error("Provide the text and a valid http(s) source URL.")
            else:
                try:
                    raws = sources_mod.extract_tenders_from_text(txt, src_url)
                    with SessionLocal() as s:
                        r = service.ingest_raw(s, raws, "pasted_text", data_mode="llm_extracted", use_gemini=use_g)
                    flash("success", f"Extracted {r.fetched} record(s) - new: {r.new}, needs review: {r.needs_review}, "
                                     f"rejected: {r.rejected}")
                except sources_mod.SourceSkipped as e:
                    flash("error", f"Gemini not available: {e}")
                except Exception as e:
                    flash("error", f"Extraction failed: {type(e).__name__}")
                st.rerun()

        st.divider()
        st.subheader("4) Demo data")
        st.caption("Synthetic records (clearly labeled) to demonstrate filtering. Remove them before real use.")
        cA, cB = st.columns(2)
        if cA.button("Load demo data", key=k("load_demo")):
            demo = json.loads((config.BASE_DIR / "sample_tenders.json").read_text(encoding="utf-8"))
            with SessionLocal() as s:
                r = service.ingest_raw(s, demo, "demo_sample", data_mode="synthetic_demo", use_gemini=False)
            flash("success", f"Loaded demo data - new: {r.new}, rejected: {r.rejected}, needs review: {r.needs_review}")
            st.rerun()
        if cB.button("Remove demo data", key=k("rm_demo")):
            with SessionLocal() as s:
                n = db.delete_demo_data(s)
            flash("success", f"Removed {n} demo opportunities")
            st.rerun()

    # ------------------------------------------------------------------ logs
    with tab_logs:
        with SessionLocal() as s:
            runs = s.scalars(select(db.SourceRun).order_by(db.SourceRun.started_at.desc()).limit(50)).all()
            rej = s.scalars(select(db.RejectedTender).order_by(db.RejectedTender.created_at.desc()).limit(200)).all()
            runs_df = pd.DataFrame([{"Source": r.source_name, "Started": r.started_at, "Status": r.status,
                                     "Fetched": r.fetched, "New": r.new_count, "Rejected": r.rejected_count,
                                     "Error": r.error} for r in runs])
            rej_df = pd.DataFrame([{"Title": r.title, "Issuer": r.issuer, "Country": r.country_raw,
                                    "Reason": r.reason, "Source": r.source_name} for r in rej])
        st.subheader("Source runs (failed sources are recorded)")
        if len(runs_df):
            st.dataframe(runs_df, width="stretch", hide_index=True)
        else:
            st.caption("No runs yet.")
        st.subheader("Rejected by filters")
        if len(rej_df):
            st.dataframe(rej_df, width="stretch", hide_index=True)
        else:
            st.caption("Nothing rejected yet.")
