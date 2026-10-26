"""Pipeline + database + notification tests (no network, no API key)."""
import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from .. import db, notifications, service
from ..sources import BaseSource, SourceSkipped

TODAY = date(2026, 10, 19)


def raw(**kw):
    base = {"title": "IT Training Program", "issuer": "Ministry X", "country": "Egypt", "deadline": "2026-12-01",
            "source_url": "https://portal.example/t/1"}
    base.update(kw)
    return base


class FakeGemini:
    def __init__(self, text=None):
        self.models = self
        self.calls = 0
        self.text = text or json.dumps({"summary": "A training tender.", "eligibility_assessment": "unclear",
                                        "eligibility_notes": "Registration unknown."})

    def generate_content(self, **kw):
        self.calls += 1
        return SimpleNamespace(text=self.text)


class ListSource(BaseSource):
    def __init__(self, name, rows=None, error=None, skip=None, **kw):
        super().__init__(name, **kw)
        self.rows, self.error, self.skip = rows or [], error, skip

    def fetch(self):
        if self.skip:
            raise SourceSkipped(self.skip)
        if self.error:
            raise self.error
        return self.rows


# ---------------------------------------------------------------- ingest
def test_demo_data_end_to_end(session, demo_raw):
    r = service.ingest_raw(session, demo_raw, "demo", data_mode="synthetic_demo", use_gemini=False, today=TODAY)
    assert (r.new, r.needs_review, r.rejected, r.duplicates) == (24, 6, 13, 3)
    opps = session.scalars(select(db.Opportunity)).all()
    assert {o.country_code for o in opps if o.filter_status == "accepted"} <= {"EG", "SA"}
    assert all(o.data_mode == "synthetic_demo" for o in opps)
    assert session.scalar(select(func.count()).select_from(db.RejectedTender)) == 13


def test_rerun_is_idempotent(session, demo_raw):
    service.ingest_raw(session, demo_raw, "demo", use_gemini=False, today=TODAY)
    r2 = service.ingest_raw(session, demo_raw, "demo", use_gemini=False, today=TODAY)
    # 24 stored rows + the 3 cross-posted duplicate rows all match stored fingerprints
    assert r2.new == 0 and r2.already_known == 27 and r2.updated == 0   # other URLs are NOT mistaken for updates
    assert session.scalar(select(func.count()).select_from(db.Opportunity)) == 24


def test_priorities(session):
    service.ingest_raw(session, [raw(), raw(title="Digital Transformation Workshops", country="KSA")],
                       "t", use_gemini=False, today=TODAY)
    p = {o.country_code: o.priority for o in session.scalars(select(db.Opportunity))}
    assert p == {"EG": "high", "SA": "monitor"}


def test_default_country_from_source_config(session):
    r = service.ingest_raw(session, [raw(country=None)], "egypt_portal", default_country="Egypt",
                           use_gemini=False, today=TODAY)
    assert r.new == 1 and r.needs_review == 0


def test_missing_country_without_default_needs_review(session):
    r = service.ingest_raw(session, [raw(country=None)], "x", use_gemini=False, today=TODAY)
    assert (r.new, r.needs_review) == (1, 1)
    assert session.scalars(select(db.Opportunity)).one().priority is None


def test_arabic_and_english_columns_mapped(session):
    rows = [{"اسم المنافسة": "برنامج تدريب فني للعاملين", "الجهة": "وزارة الاتصالات", "الدولة": "مصر",
             "آخر موعد لتقديم العروض": "2026-12-20", "الرابط": "https://portal.example/ar/9"}]
    r = service.ingest_raw(session, rows, "ar", use_gemini=False, today=TODAY)
    o = session.scalars(select(db.Opportunity)).one()
    assert r.new == 1 and o.country_code == "EG" and o.deadline == date(2026, 12, 20)


def test_row_without_title_is_invalid_not_a_crash(session):
    r = service.ingest_raw(session, [{"issuer": "x"}, raw()], "x", use_gemini=False, today=TODAY)
    assert r.invalid == 1 and r.new == 1


def test_missing_source_url_is_a_reference_not_a_link(session):
    service.ingest_raw(session, [raw(source_url=None)], "my_file", use_gemini=False, today=TODAY)
    o = session.scalars(select(db.Opportunity)).one()
    assert o.source_url is None and o.import_reference == "my_file#row1"
    assert o.filter_status == "needs_review" and "import reference" in o.review_reason


def test_hijri_deadline_is_not_guessed(session):
    service.ingest_raw(session, [raw(deadline="1448/05/10")], "x", use_gemini=False, today=TODAY)
    o = session.scalars(select(db.Opportunity)).one()
    assert o.deadline is None and o.deadline_status == "unparsed" and o.deadline_raw == "1448/05/10"
    assert o.filter_status == "needs_review"


def test_search_discovered_is_always_needs_review(session):
    r = service.ingest_raw(session, [raw()], "gemini", data_mode="search_discovered", use_gemini=False, today=TODAY)
    o = session.scalars(select(db.Opportunity)).one()
    assert r.needs_review == 1 and o.filter_status == "needs_review" and o.priority == "high"
    assert "verify" in o.review_reason.lower()


def test_gemini_summary_stored_and_only_for_accepted(session):
    g = FakeGemini()
    service.ingest_raw(session, [raw(), raw(title="Other Training", country="Germany")], "x",
                       gemini_client=g, today=TODAY)
    o = session.scalars(select(db.Opportunity)).one()
    assert o.summary == "A training tender." and o.eligibility_assessment == "unclear"
    assert g.calls == 1


# ---------------------------------------------------------------- run_all
def test_failed_source_is_recorded_and_does_not_stop_others(session):
    srcs = [ListSource("bad", error=RuntimeError("boom")), ListSource("good", rows=[raw()]),
            ListSource("nokey", skip="GEMINI_API_KEY is not set")]
    rep = service.run_all(session, srcs, use_gemini=False, today=TODAY)
    runs = {r.source_name: r for r in session.scalars(select(db.SourceRun))}
    assert runs["bad"].status == "failed" and "boom" in runs["bad"].error
    assert runs["good"].status == "ok" and runs["good"].new_count == 1
    assert runs["nokey"].status == "skipped"
    assert rep.totals.new == 1


def test_expired_marked_after_run(session):
    service.ingest_raw(session, [raw(deadline="2026-11-01")], "x", use_gemini=False, today=TODAY)
    assert db.mark_expired(session, today=date(2026, 11, 2)) == 1
    assert session.scalars(select(db.Opportunity)).one().workflow_status == "expired"
    assert db.search_opportunities(session) == []
    assert len(db.search_opportunities(session, include_expired=True)) == 1


# ---------------------------------------------------------------- search / update
def test_search_filters(session, demo_raw):
    service.ingest_raw(session, demo_raw, "demo", data_mode="synthetic_demo", use_gemini=False, today=TODAY)
    assert {o.country_code for o in db.search_opportunities(session, country="SA")} == {"SA"}
    assert all(o.priority == "high" for o in db.search_opportunities(session, priority="high"))
    hits = db.search_opportunities(session, q="cloud")
    assert hits and all("cloud" in (o.title + (o.description or "")).lower() for o in hits)
    assert db.search_opportunities(session, q="تدريب فني")
    assert db.search_opportunities(session, deadline_from=date(2027, 1, 1))
    ordered = db.search_opportunities(session)
    assert ordered[0].priority == "high"          # Egypt first


def test_update_workflow_validates_status(session):
    service.ingest_raw(session, [raw()], "x", use_gemini=False, today=TODAY)
    o = session.scalars(select(db.Opportunity)).one()
    db.update_workflow(session, o.id, "reviewing", "call them Sunday")
    assert (o.workflow_status, o.reviewer_notes) == ("reviewing", "call them Sunday")
    with pytest.raises(ValueError):
        db.update_workflow(session, o.id, "approved-by-ai")
    assert db.update_workflow(session, 9999, "new") is None


def test_delete_demo_data_keeps_real_rows(session, demo_raw):
    service.ingest_raw(session, demo_raw, "demo", data_mode="synthetic_demo", use_gemini=False, today=TODAY)
    service.ingest_raw(session, [raw(title="Real Training Tender 2027")], "real", use_gemini=False, today=TODAY)
    db.delete_demo_data(session)
    left = session.scalars(select(db.Opportunity)).all()
    assert [o.title for o in left] == ["Real Training Tender 2027"]


# ---------------------------------------------------------------- notifications
def test_notifications_created_once_per_new_opportunity(session):
    rep = service.run_all(session, [ListSource("s", rows=[raw(), raw(country="KSA", title="Cloud Training Course")])],
                          use_gemini=False, today=TODAY)
    kinds = sorted(n.kind for n in session.scalars(select(db.Notification)))
    assert kinds == ["egypt_priority", "saudi_monitor"] and rep.notifications_created == 2
    # same data again -> nothing new -> no new alerts
    rep2 = service.run_all(session, [ListSource("s", rows=[raw(), raw(country="KSA", title="Cloud Training Course")])],
                           use_gemini=False, today=TODAY)
    assert rep2.notifications_created == 0
    assert session.scalar(select(func.count()).select_from(db.Notification)) == 2


def test_email_digest_sent_only_when_configured(session, monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg): sent.append(msg)

    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    for k in ("SMTP_HOST", "ALERT_EMAILS"):
        monkeypatch.delenv(k, raising=False)
    rep = service.run_all(session, [ListSource("s", rows=[raw()])], use_gemini=False, today=TODAY)
    assert rep.email_sent is False and sent == []

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("ALERT_EMAILS", "a@x.com, b@x.com")
    rep = service.run_all(session, [ListSource("s2", rows=[raw(title="Second Training Tender")])],
                          use_gemini=False, today=TODAY)
    assert rep.email_sent is True and len(sent) == 1
    body = sent[0].get_content()
    assert "EGYPT - PRIORITY" in body and "https://portal.example/t/1" in body
    assert sent[0]["To"] == "a@x.com, b@x.com"
    assert all(n.email_sent for n in session.scalars(select(db.Notification).where(db.Notification.id > 1)))


def test_email_failure_does_not_crash_pipeline(session, monkeypatch):
    def boom(*a, **k):
        raise OSError("smtp down")
    monkeypatch.setattr(notifications.smtplib, "SMTP", boom)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("ALERT_EMAILS", "a@x.com")
    rep = service.run_all(session, [ListSource("s", rows=[raw()])], use_gemini=False, today=TODAY)
    assert rep.totals.new == 1 and rep.email_sent is False
