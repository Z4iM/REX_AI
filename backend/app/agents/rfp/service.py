"""
Pipeline: fetch -> normalize -> already stored? (update-on-change) -> Python filters -> Gemini summary -> store -> alerts.
Accept/reject is deterministic Python (rfp_agent.filter_tenders). Gemini only summarizes.

PROVENANCE RULE: `data_mode` is passed by TRUSTED code (the source adapter / dashboard action). It is never read
from imported rows or LLM output. TRUST_POLICY decides which modes are forced into 'needs_review'.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from urllib.parse import urlparse

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import notifications
from .db import Opportunity, OpportunityHistory, RejectedTender, SourceRun, mark_expired, utcnow
from .rfp_agent import (Tender, canonical_url, classify_topics, filter_tenders, fingerprint, summarize_tender,
                        valid_http_url)
from .sources import BaseSource, SourceSkipped, map_row, parse_date

TRUST_POLICY = {
    "imported":          {"force_review": False, "reason": None},
    "live":              {"force_review": False, "reason": None},   # reserved for future VERIFIED connectors
    "synthetic_demo":    {"force_review": False, "reason": None},
    "search_discovered": {"force_review": True,
                          "reason": "Discovered via AI web search - open the source page and verify before acting"},
    "llm_extracted":     {"force_review": True,
                          "reason": "Fields extracted by an LLM from pasted text - verify against the original"},
}


@dataclass
class IngestResult:
    fetched: int = 0
    new: int = 0
    needs_review: int = 0
    rejected: int = 0
    duplicates: int = 0
    already_known: int = 0
    updated: int = 0
    invalid: int = 0
    errors: list[str] = field(default_factory=list)
    new_opportunities: list[Opportunity] = field(default_factory=list)


@dataclass
class RunReport:
    per_source: list[dict] = field(default_factory=list)
    totals: IngestResult = field(default_factory=IngestResult)
    notifications_created: int = 0
    email_sent: bool = False
    webhook_sent: bool = False
    expired_marked: int = 0


@dataclass
class Prep:
    tender: Tender
    import_reference: Optional[str]
    notes: list[str]
    no_source_url: bool
    deadline_status: str
    deadline_raw: Optional[str]


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").lower().strip())


def _clean(v) -> Optional[str]:
    return str(v).strip() if v not in (None, "") and str(v).strip() else None


def _prepare(raw: dict, source_name: str, idx: int, default_country: Optional[str]) -> Prep:
    r = map_row(raw)
    if not r.get("title"):
        raise ValueError("missing title")
    notes: list[str] = []

    src = _clean(r.get("source_url"))
    import_ref = None
    if valid_http_url(src):
        source_url, no_url = src, False
    else:
        source_url, no_url = None, True
        import_ref = _clean(raw.get("_file_ref")) or f"{source_name}#row{idx + 1}"
        notes.append("Invalid source URL ignored" if src else "No source URL")
        notes.append(f"only an import reference ({import_ref}), not a portal link")

    sub = _clean(r.get("submission_url"))
    if sub and not valid_http_url(sub):
        notes.append("Invalid submission URL ignored")
        sub = None

    dl_raw = _clean(r.get("deadline"))
    deadline = parse_date(dl_raw)
    if deadline:
        dl_status = "known"
    elif dl_raw:
        dl_status = "unparsed"
        notes.append(f"Deadline '{dl_raw}' could not be parsed (e.g. Hijri) - verify manually")
    else:
        dl_status = "unknown"

    host = (urlparse(source_url).hostname or "").lower() if source_url else ""
    country = _clean(r.get("country")) or _clean(default_country)
    t = Tender(
        title=str(r["title"]).strip(), issuer=_clean(r.get("issuer")) or "Unknown issuer", country=country,
        publication_date=parse_date(r.get("publication_date")), deadline=deadline,
        category=_clean(r.get("category")), eligibility=_clean(r.get("eligibility")), submission_url=sub,
        source_url=source_url, description=_clean(r.get("description")),
        tender_id=_clean(r.get("tender_id")), portal=host or source_name)
    return Prep(t, import_ref, notes, no_url, dl_status, dl_raw)


# ---------------------------------------------------------------- already-known handling

def _add_alt_url(opp: Opportunity, url: Optional[str]) -> None:
    c = canonical_url(url)
    if not c or c == canonical_url(opp.source_url):
        return
    urls = json.loads(opp.also_seen_at or "[]")
    if c not in [canonical_url(u) for u in urls]:
        urls.append(url)
        opp.also_seen_at = json.dumps(urls)


_TEXT_FIELDS = ("title", "issuer", "category", "eligibility", "description")


def _refresh_known(session: Session, opp: Opportunity, p: Prep, source_name: str, data_mode: str) -> bool:
    """Same tender seen again. Returns True if stored data changed (history rows are written)."""
    t = p.tender
    opp.last_seen = utcnow()
    same_page = (not t.source_url or canonical_url(t.source_url) == canonical_url(opp.source_url)
                 or bool(t.tender_id))
    if opp.data_mode != data_mode or not same_page:
        _add_alt_url(opp, t.source_url)      # another sighting / lower or different trust: never overwrites
        return False

    changed = False

    def apply(fieldname, new):
        nonlocal changed
        old = getattr(opp, fieldname)
        session.add(OpportunityHistory(opportunity_id=opp.id, field=fieldname,
                                       old_value=None if old is None else str(old), new_value=str(new),
                                       source_name=source_name))
        setattr(opp, fieldname, new)
        changed = True

    for f in _TEXT_FIELDS:
        new = getattr(t, f)
        if new and _norm(new) != _norm(getattr(opp, f)):
            apply(f, new)
    for f in ("deadline", "publication_date", "submission_url"):
        new = getattr(t, f)
        if new and new != getattr(opp, f):
            apply(f, new)
    if t.source_url and canonical_url(t.source_url) != canonical_url(opp.source_url):
        if opp.source_url:
            _add_alt_url(opp, opp.source_url)
        apply("source_url", t.source_url)
        opp.import_reference = None
    if t.deadline and opp.deadline_status != "known":
        opp.deadline_status, opp.deadline_raw = "known", p.deadline_raw
    if changed:
        opp.updated_at = utcnow()
    return changed


# ---------------------------------------------------------------- ingest

def ingest_raw(session: Session, raws: list[dict], source_name: str, *, default_country: Optional[str] = None,
               data_mode: str = "imported", use_gemini: bool = True, gemini_client=None,
               today: Optional[date] = None, max_summaries: int = 50) -> IngestResult:
    if data_mode not in TRUST_POLICY:
        raise ValueError(f"Unknown data_mode '{data_mode}' (allowed: {', '.join(TRUST_POLICY)})")
    policy = TRUST_POLICY[data_mode]
    res = IngestResult(fetched=len(raws))

    prepared: list[Prep] = []
    for i, raw in enumerate(raws):
        try:
            prepared.append(_prepare(raw, source_name, i, default_country))
        except (ValidationError, ValueError) as e:
            res.invalid += 1
            res.errors.append(f"row {i + 1}: {type(e).__name__}")

    fps = [fingerprint(p.tender) for p in prepared]
    existing = {o.fingerprint: o for o in session.scalars(
        select(Opportunity).where(Opportunity.fingerprint.in_(fps or [""])))}
    fresh: list[Prep] = []
    for p, fp in zip(prepared, fps):
        if fp in existing:
            res.already_known += 1
            if _refresh_known(session, existing[fp], p, source_name, data_mode):
                res.updated += 1
        else:
            fresh.append(p)

    by_tender = {id(p.tender): p for p in fresh}
    processed = filter_tenders([p.tender for p in fresh], today=today)
    summaries_left = max_summaries

    for fp_res in processed:
        p = by_tender[id(fp_res.tender)]
        t = fp_res.tender
        if fp_res.status == "rejected":
            if fp_res.reason == "Duplicate opportunity":
                res.duplicates += 1
                twin = session.scalar(select(Opportunity).where(Opportunity.fingerprint == fp_res.fingerprint))
                if twin:
                    _add_alt_url(twin, t.source_url)
                continue
            res.rejected += 1
            if not session.scalar(select(RejectedTender.id).where(RejectedTender.fingerprint == fp_res.fingerprint)):
                session.add(RejectedTender(fingerprint=fp_res.fingerprint, title=t.title, issuer=t.issuer,
                                           country_raw=t.country, reason=fp_res.reason, source_name=source_name,
                                           data_mode=data_mode))
            continue

        summary = assess = notes = None
        if use_gemini and fp_res.country_code and summaries_left > 0:
            s = summarize_tender(t, client=gemini_client)
            summary, assess, notes = s["summary"], s["eligibility_assessment"], s["eligibility_notes"]
            summaries_left -= 1

        status = fp_res.status
        reasons = [fp_res.reason] if fp_res.reason else []
        if policy["force_review"]:
            status = "needs_review"
            reasons.append(policy["reason"])
        if p.no_source_url:
            status = "needs_review"
        reasons += [n for n in p.notes if n not in reasons]

        opp = Opportunity(
            fingerprint=fp_res.fingerprint, tender_id=t.tender_id, portal=t.portal, title=t.title, issuer=t.issuer,
            country_raw=t.country, country_code=fp_res.country_code, country_basis=fp_res.country_basis,
            publication_date=t.publication_date, deadline=t.deadline, deadline_status=p.deadline_status,
            deadline_raw=p.deadline_raw, category=t.category, topics=", ".join(classify_topics(t)) or None,
            eligibility=t.eligibility, submission_url=t.submission_url, source_url=t.source_url,
            import_reference=p.import_reference, source_name=source_name, description=t.description,
            summary=summary, eligibility_assessment=assess, eligibility_notes=notes, filter_status=status,
            review_reason="; ".join(reasons) or None, priority=fp_res.priority, data_mode=data_mode)
        session.add(opp)
        session.flush()
        res.new_opportunities.append(opp)
        res.new += 1
        if status == "needs_review":
            res.needs_review += 1
    session.commit()
    return res


def _merge(total: IngestResult, r: IngestResult) -> None:
    for f in ("fetched", "new", "needs_review", "rejected", "duplicates", "already_known", "updated", "invalid"):
        setattr(total, f, getattr(total, f) + getattr(r, f))
    total.errors += r.errors
    total.new_opportunities += r.new_opportunities


def run_all(session: Session, sources: list[BaseSource], *, use_gemini: bool = True, notify: bool = True,
            gemini_client=None, today: Optional[date] = None) -> RunReport:
    report = RunReport()
    for src in sources:
        run = SourceRun(source_name=src.name)
        session.add(run)
        session.commit()
        entry = {"source": src.name, "status": "ok", "error": None}
        try:
            raws = src.fetch()
            r = ingest_raw(session, raws, src.name, default_country=src.default_country, data_mode=src.data_mode,
                           use_gemini=use_gemini, gemini_client=gemini_client, today=today)
            run.fetched, run.new_count, run.rejected_count = r.fetched, r.new, r.rejected
            run.status = "ok"
            _merge(report.totals, r)
            entry.update(fetched=r.fetched, new=r.new, rejected=r.rejected, updated=r.updated)
        except SourceSkipped as e:
            run.status, run.error = "skipped", str(e)
            entry.update(status="skipped", error=str(e))
        except Exception as e:      # a failing source must never stop the others - but it IS recorded
            session.rollback()
            msg = f"{type(e).__name__}: {str(e)[:300]}"
            run.status, run.error = "failed", msg
            entry.update(status="failed", error=msg)
        run.finished_at = utcnow()
        session.add(run)
        session.commit()
        report.per_source.append(entry)

    report.expired_marked = mark_expired(session, today)
    if notify and report.totals.new_opportunities:
        notifs = notifications.create_notifications(session, report.totals.new_opportunities)
        report.notifications_created = len(notifs)
        report.email_sent = notifications.send_email_digest(session, notifs)
        report.webhook_sent = notifications.post_webhook(notifs)
    return report
