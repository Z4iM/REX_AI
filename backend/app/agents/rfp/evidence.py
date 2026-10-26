"""Evidence report for demos / the instructor: what was really found, from where, and how well it is verified.
Built only from the database (run logs + records) so it is reproducible and cannot be hand-edited into a claim."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import db

MODE_TEXT = {
    "imported": "manual import from a file/export (human-collected, NOT autonomous monitoring)",
    "search_discovered": "AI web search lead (unverified)",
    "llm_extracted": "LLM-extracted from pasted text (unverified)",
    "live": "verified live connector",
    "synthetic_demo": "SYNTHETIC DEMO DATA",
}


def build_report(session: Session, include_demo: bool = False) -> tuple[str, list[dict]]:
    opps = [o for o in db.search_opportunities(session, include_expired=True, limit=10000)
            if include_demo or o.data_mode != "synthetic_demo"]
    rows = [{
        "id": o.id, "country": o.country_code, "title": o.title, "issuer": o.issuer,
        "deadline": o.deadline.isoformat() if o.deadline else f"unknown ({o.deadline_status})",
        "source_url": o.source_url or "", "import_reference": o.import_reference or "",
        "origin": o.data_mode, "origin_meaning": MODE_TEXT.get(o.data_mode, o.data_mode),
        "validation": "rules-accepted (still verify on source)" if o.filter_status == "accepted" else "NEEDS VERIFICATION",
        "review_reason": o.review_reason or "", "first_seen": o.first_seen.isoformat(timespec="seconds"),
        "source_name": o.source_name or "",
    } for o in opps]

    def proper(c):  # a properly sourced result = real http(s) source URL + country + not demo
        return [r for r in rows if r["country"] == c and r["source_url"] and r["origin"] != "synthetic_demo"]

    runs = session.scalars(select(db.SourceRun).order_by(db.SourceRun.started_at.desc()).limit(20)).all()
    md = [f"# RFP agent - evidence report", f"Generated: {datetime.now():%Y-%m-%d %H:%M}", "",
          "## Checklist", f"- Egypt result with a real source URL: **{'YES' if proper('EG') else 'NO'}** ({len(proper('EG'))})",
          f"- Saudi Arabia result with a real source URL: **{'YES' if proper('SA') else 'NO'}** ({len(proper('SA'))})",
          f"- Synthetic demo rows included: **{'yes' if include_demo else 'no (excluded)'}**",
          "- Rows from manual imports are human-collected exports, not autonomous real-time monitoring.", "",
          "## Opportunities", "", "| # | Country | Title | Issuer | Deadline | Source URL | Origin | Validation |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['country'] or '?'} | {r['title']} | {r['issuer']} | {r['deadline']} | "
                  f"{r['source_url'] or 'NONE (ref: ' + r['import_reference'] + ')'} | {r['origin_meaning']} | {r['validation']} |")
    md += ["", "## Source run log (latest 20)", "", "| Source | Started | Status | Fetched | New | Rejected | Error |",
           "|---|---|---|---|---|---|---|"]
    for r in runs:
        md.append(f"| {r.source_name} | {r.started_at:%Y-%m-%d %H:%M} | {r.status} | {r.fetched} | {r.new_count} | "
                  f"{r.rejected_count} | {r.error or ''} |")
    return "\n".join(md) + "\n", rows
