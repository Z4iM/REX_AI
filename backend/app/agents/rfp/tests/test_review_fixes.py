"""One test group per finding in Problems.docx (P1 = high priority, P2 = medium)."""
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from streamlit.testing.v1 import AppTest

from .. import db, evidence, notifications, router as router_mod, service, sources
from ..rfp_agent import Tender, classify_location, fingerprint, filter_tenders
from ..sources import BaseSource, GeminiSearchSource, SourceError


TODAY = date(2026, 10, 19)
PKG = Path(__file__).parent.parent
ROOT = PKG.parent
APP_FILE = Path(__file__).with_name("_dashboard_app.py")

def raw(**kw):
    base = {"title": "IT Training Program", "issuer": "Ministry X", "country": "Egypt", "deadline": "2026-12-01",
            "source_url": "https://portal.example/t/1"}
    base.update(kw)
    return base


def ingest(session, rows, mode="imported", name="t", **kw):
    return service.ingest_raw(session, rows, name, data_mode=mode, use_gemini=False, today=TODAY, **kw)


def only(session):
    return session.scalars(select(db.Opportunity)).one()


class FakeClient:
    def __init__(self, text=None, error=None, extra=None):
        self.models, self.text, self.error, self.extra = self, text, error, extra or {}

    def generate_content(self, **kw):
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, **self.extra)


# ================================================================ P1-1 source links
class TestSourceUrl:
    def test_missing_url_is_never_stored_as_a_link(self, session):
        ingest(session, [raw(source_url=None)])
        o = only(session)
        assert o.source_url is None and o.import_reference and o.filter_status == "needs_review"

    @pytest.mark.parametrize("bad", ["untrusted_csv#row2", "javascript:alert(1)", "ftp://x.example/a", "http://", "not a url",
                                     "https://exa mple.com/x"])
    def test_invalid_urls_rejected_as_source(self, session, bad):
        ingest(session, [raw(source_url=bad)])
        o = only(session)
        assert o.source_url is None and o.filter_status == "needs_review"
        assert "Invalid source URL ignored" in o.review_reason

    def test_invalid_submission_url_dropped_but_tender_kept(self, session):
        ingest(session, [raw(submission_url="javascript:void(0)")])
        o = only(session)
        assert o.submission_url is None and o.source_url and "Invalid submission URL ignored" in o.review_reason

    def test_valid_urls_kept(self, session):
        ingest(session, [raw(submission_url="https://portal.example/apply/1")])
        o = only(session)
        assert o.source_url == "https://portal.example/t/1" and o.submission_url == "https://portal.example/apply/1"
        assert o.filter_status == "accepted"

    def test_email_does_not_present_import_reference_as_a_link(self, session, monkeypatch):
        sent = []

        class S:
            def __init__(s, *a, **k): pass
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def starttls(s): pass
            def login(s, *a): pass
            def send_message(s, m): sent.append(m)

        monkeypatch.setattr(notifications.smtplib, "SMTP", S)
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("ALERT_EMAILS", "a@x.com")

        class Src(BaseSource):
            def fetch(self): return [raw(source_url=None)]

        service.run_all(session, [Src("f")], use_gemini=False, today=TODAY)
        assert "no verifiable source URL" in sent[0].get_content()


# ================================================================ P1-2 provenance
class TestProvenance:
    def test_input_cannot_override_data_mode(self, session):
        ingest(session, [raw(data_mode="live", source_name="official portal")], mode="search_discovered")
        o = only(session)
        assert o.data_mode == "search_discovered" and o.filter_status == "needs_review"
        assert "verify" in o.review_reason.lower() and o.source_name == "t"

    def test_map_row_ignores_provenance_columns(self):
        assert "data_mode" not in sources.map_row({"title": "x", "data_mode": "live", "source_name": "y"})

    def test_unknown_mode_is_refused(self, session):
        with pytest.raises(ValueError):
            ingest(session, [raw()], mode="verified-by-me")

    def test_llm_extracted_is_always_a_lead(self, session):
        ingest(session, [raw()], mode="llm_extracted")
        assert only(session).filter_status == "needs_review"

    def test_config_cannot_escalate_trust(self):
        assert sources.FolderSource("x", path="imports", data_mode="live").data_mode == "imported"

    def test_search_source_end_to_end_cannot_produce_live_record(self, session):
        payload = json.dumps([{"title": "Training RFP", "issuer": "X", "country": "Egypt", "deadline": "2026-12-01",
                               "source_url": "https://portal.example/a", "data_mode": "live"}])
        src = GeminiSearchSource("g", queries=["q"], client=FakeClient(payload))
        service.run_all(session, [src], use_gemini=False, today=TODAY)
        o = only(session)
        assert o.data_mode == "search_discovered" and o.filter_status == "needs_review"


# ================================================================ P1-3 deadlines
class TestDeadlines:
    def test_missing_deadline_is_not_an_open_opportunity(self, session):
        ingest(session, [raw(deadline=None)])
        o = only(session)
        assert o.filter_status == "needs_review" and o.deadline_status == "unknown"
        assert "cannot confirm" in o.review_reason and o.priority == "high"

    def test_alert_for_it_says_verification_not_ready_to_apply(self, session):
        class Src(BaseSource):
            def fetch(self): return [raw(deadline=None)]
        service.run_all(session, [Src("s")], use_gemini=False, today=TODAY)
        n = session.scalars(select(db.Notification)).one()
        assert n.kind == "egypt_verify" and "not confirmed open" in n.message

    def test_known_deadline_provenance_recorded(self, session):
        ingest(session, [raw(deadline="2026-12-01")])
        o = only(session)
        assert (o.deadline_status, o.deadline_raw) == ("known", "2026-12-01")


# ================================================================ P1-4 duplicate key
class TestDuplicateKey:
    def test_same_text_different_country_are_two_opportunities(self, session):
        ingest(session, [raw(country="Egypt", source_url="https://a.example/1"),
                         raw(country="Saudi Arabia", source_url="https://b.example/2")])
        rows = session.scalars(select(db.Opportunity)).all()
        assert sorted(o.country_code for o in rows) == ["EG", "SA"]

    def test_official_id_identifies_the_tender(self):
        a = Tender(title="A", issuer="X", country="Egypt", tender_id="T-1", portal="p.example")
        assert fingerprint(a) == fingerprint(a.model_copy(update={"title": "Renamed", "deadline": date(2027, 1, 1)}))
        assert fingerprint(a) != fingerprint(a.model_copy(update={"portal": "other.example"}))
        assert fingerprint(a) != fingerprint(a.model_copy(update={"country": "Saudi Arabia"}))

    def test_cross_posted_duplicate_keeps_the_other_url(self, session):
        ingest(session, [raw(source_url="https://a.example/1"), raw(source_url="https://mirror.example/9")])
        o = only(session)
        assert o.source_url == "https://a.example/1" and "https://mirror.example/9" in json.loads(o.also_seen_at)

    def test_same_wording_filter_level(self):
        t1 = Tender(title="X Training", issuer="I", country="Egypt", deadline=date(2026, 12, 1), source_url="https://a.example/1")
        t2 = t1.model_copy(update={"country": "KSA", "source_url": "https://b.example/2"})
        assert [r.status for r in filter_tenders([t1, t2], today=TODAY)] == ["accepted", "accepted"]

    def test_fingerprint_migration_merges_collisions(self, session):
        ingest(session, [raw(), raw(title="Another Training Course")])
        a, b = session.scalars(select(db.Opportunity).order_by(db.Opportunity.id)).all()
        b.title = a.title                   # simulate rows that collapse onto one key under the new definition
        b.deadline = a.deadline
        session.commit()
        out = db.recompute_fingerprints(session)
        assert out["merged_duplicates"] == 1 and len(session.scalars(select(db.Opportunity)).all()) == 1

    def test_v1_database_is_backed_up_and_recreated(self, tmp_path):
        path = tmp_path / "old.db"
        con = sqlite3.connect(path)
        con.execute("create table opportunities (id integer primary key, fingerprint text)")
        con.commit()
        con.close()
        factory = db.get_session_factory(f"sqlite:///{path}")
        assert list(tmp_path.glob("old.db.v1.*.bak"))
        with factory() as s:
            assert s.get(db.Meta, "schema_version").value == db.SCHEMA_VERSION


# ================================================================ P1-5 integration
class TestIntegration:
    def test_no_absolute_sibling_imports(self):
        names = "config|db|service|sources|notifications|rfp_agent|router|ui|evidence"
        pat = re.compile(rf"^\s*(import ({names})\b|from ({names}) import)", re.M)
        offenders = [f.name for f in PKG.glob("*.py") if pat.search(f.read_text(encoding="utf-8"))]
        assert offenders == []

    def test_router_mounts_into_a_host_app_with_its_own_auth(self, factory):
        host = FastAPI()

        @host.get("/api/v1/chat")
        def chat():
            return {"ok": True}

        def staff_auth(x_staff: str | None = None):
            if x_staff != "yes":
                raise HTTPException(403, "staff only")

        host.include_router(router_mod.build_router(session_factory=factory, auth_dependency=staff_auth,
                                                    sources_loader=lambda only=None: []))
        c = TestClient(host)
        assert c.get("/api/v1/chat").json() == {"ok": True}                 # host route untouched
        assert c.get("/api/v1/rfp/opportunities").status_code == 403         # host auth is enforced
        assert c.get("/api/v1/rfp/opportunities?x_staff=yes").status_code == 200

    def test_rfp_integrated_with_main_app(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)

        # Main REX AI application must still work.
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Inspect registered API routes.
        paths = app.openapi()["paths"]

        # Existing Course Assistant.
        assert "/api/v1/chat" in paths
        assert "/api/v1/qualification" in paths

        # Integrated RFP Agent.
        assert "/api/v1/rfp/run" in paths
        assert "/api/v1/rfp/opportunities" in paths
        assert "/api/v1/rfp/notifications" in paths

    def test_database_has_its_own_namespaced_env_var(self, monkeypatch):
        from .. import config
        monkeypatch.setenv("DATABASE_URL", "sqlite:///should-not-be-used.db")
        assert "should-not-be-used" not in config.database_url()


# ================================================================ P1-6 evidence
class TestEvidence:
    def test_report_excludes_demo_and_flags_unverified(self, session):
        ingest(session, [raw(country="Egypt"), raw(title="Cloud Training Course", country="Saudi Arabia",
                                                  source_url="https://b.example/2"),
                         raw(title="Cybersecurity Training", source_url=None)])
        ingest(session, [raw(title="Demo only training")], mode="synthetic_demo", name="demo")
        md, rows = evidence.build_report(session)
        assert len(rows) == 3 and all(r["origin"] != "synthetic_demo" for r in rows)
        assert "Egypt result with a real source URL: **YES**" in md and "Saudi Arabia result with a real source URL: **YES**" in md
        assert "NEEDS VERIFICATION" in md and "NOT autonomous" in md
        assert "Demo only training" not in md and "Demo only training" in evidence.build_report(session, True)[0]

    def test_report_says_no_when_there_is_no_real_saudi_result(self, session):
        ingest(session, [raw()])
        assert "Saudi Arabia result with a real source URL: **NO**" in evidence.build_report(session)[0]


# ================================================================ P2-7 update on change
class TestUpdates:
    def test_changed_fields_are_updated_with_history(self, session):
        ingest(session, [raw(description="old text")])
        r = ingest(session, [raw(description="new text", submission_url="https://portal.example/apply")])
        o = only(session)
        assert r.updated == 1 and o.description == "new text" and o.submission_url == "https://portal.example/apply"
        fields = {(h.field, h.old_value, h.new_value) for h in o.history}
        assert ("description", "old text", "new text") in fields

    def test_missing_values_never_erase_data(self, session):
        ingest(session, [raw(description="keep me")])
        ingest(session, [raw(description=None)])
        assert only(session).description == "keep me"

    def test_same_content_is_not_an_update(self, session):
        ingest(session, [raw()])
        assert ingest(session, [raw()]).updated == 0

    def test_lower_trust_source_cannot_overwrite(self, session):
        ingest(session, [raw(description="verified text")])
        ingest(session, [raw(description="AI text")], mode="search_discovered")
        assert only(session).description == "verified text"

    def test_official_id_lets_a_deadline_change_update_the_same_tender(self, session):
        ingest(session, [raw(tender_id="T-7", deadline="2026-12-01")])
        r = ingest(session, [raw(tender_id="T-7", deadline="2026-12-20")])
        o = only(session)
        assert r.updated == 1 and o.deadline == date(2026, 12, 20)
        assert any(h.field == "deadline" for h in o.history)

    def test_learning_the_deadline_later_upgrades_deadline_status(self, session):
        ingest(session, [raw(tender_id="T-8", deadline=None)])
        ingest(session, [raw(tender_id="T-8", deadline="2026-12-20")])
        assert only(session).deadline_status == "known"


# ================================================================ P2-8 sorting + pagination
class TestPagination:
    def test_priority_sorting_happens_before_limit(self, session):
        ingest(session, [raw(title="Saudi Training Course", country="Saudi Arabia", source_url="https://s.example/1")])
        ingest(session, [raw(title="Egypt Training Course", country="Egypt", source_url="https://e.example/1")])
        assert db.search_opportunities(session, limit=1)[0].country_code == "EG"
        assert db.search_opportunities(session, limit=1, offset=1)[0].country_code == "SA"
        assert db.search_opportunities(session, limit=1, offset=2) == []

    def test_sort_by_soonest_deadline_and_unknown_last(self, session):
        ingest(session, [raw(title="Late Training A", deadline="2027-03-01", source_url="https://a.example/1"),
                         raw(title="Soon Training B", deadline="2026-11-01", source_url="https://a.example/2"),
                         raw(title="Unknown Training C", deadline=None, source_url="https://a.example/3")])
        assert [o.title for o in db.search_opportunities(session)] == ["Soon Training B", "Late Training A",
                                                                        "Unknown Training C"]

    def test_api_pagination_params(self, factory, monkeypatch):
        monkeypatch.setenv("RFP_API_KEY", "k")
        with factory() as s:
            ingest(s, [raw(title=f"Training Course {i}", source_url=f"https://p.example/{i}") for i in range(5)])
        app = FastAPI()
        app.include_router(router_mod.build_router(session_factory=factory, sources_loader=lambda only=None: []))
        c = TestClient(app)
        r = c.get("/api/v1/rfp/opportunities?limit=2&offset=2", headers={"X-API-Key": "k"}).json()
        assert r["count"] == 2 and r["offset"] == 2
        assert c.get("/api/v1/rfp/opportunities?limit=0", headers={"X-API-Key": "k"}).status_code == 422


# ================================================================ P2-9 locations
class TestLocations:
    @pytest.mark.parametrize("text,kind,code,basis", [
        ("Riyadh", "supported", "SA", "city_mapping"), ("الرياض", "supported", "SA", "city_mapping"),
        ("Cairo", "supported", "EG", "city_mapping"), ("Alexandria, Egypt", "supported", "EG", "explicit"),
        ("Alexandria, USA", "unsupported", None, None), ("Germany", "unsupported", None, None),
        ("Egypt, Germany", "ambiguous", None, None), ("Cairo and Riyadh", "ambiguous", None, None),
        ("Industrial Zone 5", "unknown", None, None), ("مصرف الإسكان", "unknown", None, None),
        ("", "missing", None, None), (None, "missing", None, None)])
    def test_classification(self, text, kind, code, basis):
        assert classify_location(text) == (kind, code, basis)

    def test_city_only_is_accepted_with_visible_basis_and_unknown_is_reviewed(self, session):
        ingest(session, [raw(country="Riyadh", title="Training Course A", source_url="https://a.example/1"),
                         raw(country="Industrial Zone 5", title="Training Course B", source_url="https://a.example/2")])
        by = {o.title: o for o in session.scalars(select(db.Opportunity))}
        assert (by["Training Course A"].country_code, by["Training Course A"].country_basis) == ("SA", "city_mapping")
        assert by["Training Course B"].filter_status == "needs_review" and by["Training Course B"].country_code is None
        assert "Unrecognized location" in by["Training Course B"].review_reason

    def test_country_is_never_inferred_from_the_description(self, session):
        ingest(session, [raw(country=None, description="Based in Riyadh, Saudi Arabia")])
        o = only(session)
        assert o.country_code is None and o.filter_status == "needs_review"

    def test_irrelevant_or_expired_items_with_unknown_country_are_rejected_not_reviewed(self, session):
        r = ingest(session, [raw(country="Industrial Zone 5", title="Road Construction"),
                             raw(country="Industrial Zone 5", title="Old Training", deadline="2026-01-01")])
        assert r.rejected == 2 and r.new == 0


# ================================================================ P2-10 dashboard login
class TestDashboardLogin:
    @pytest.fixture()
    def env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RFP_DATABASE_URL", f"sqlite:///{tmp_path / 'ui.db'}")

    def test_password_gate_hides_everything_until_sign_in(self, env, monkeypatch):
        monkeypatch.setenv("RFP_DASHBOARD_PASSWORD", "s3cret")
        at = AppTest.from_file(str(APP_FILE),default_timeout=60,).run()
        assert not at.exception and len(at.metric) == 0 and not at.tabs
        at.text_input(key="rfp_password").set_value("wrong").run()
        [b for b in at.button if b.key == "rfp_signin"][0].click().run()
        assert len(at.metric) == 0 and any("Wrong password" in e.value for e in at.error)
        at.text_input(key="rfp_password").set_value("s3cret").run()
        [b for b in at.button if b.key == "rfp_signin"][0].click().run()
        assert len(at.metric) == 5

    def test_no_password_shows_local_use_warning(self, env):
        at = AppTest.from_file(str(APP_FILE),default_timeout=60,).run()
        assert any("No dashboard login configured" in w.value for w in at.warning)

    def test_require_login_without_password_refuses_to_render(self, env, monkeypatch):
        monkeypatch.setenv("RFP_REQUIRE_LOGIN", "1")
        at = AppTest.from_file(str(APP_FILE),default_timeout=60,).run()
        assert len(at.metric) == 0 and any("refusing" in e.value for e in at.error)

    def test_embedded_mode_trusts_the_host_apps_auth(self, env, monkeypatch):
        monkeypatch.setenv("RFP_DASHBOARD_PASSWORD", "s3cret")

        def host_page():
            from backend.app.agents.rfp.ui import render
            render(authenticated=True, key_prefix="agent2_")
        at = AppTest.from_function(host_page, default_timeout=60).run()
        assert not at.exception and len(at.metric) == 5


# ================================================================ P2-11 negative paths / integrations
class TestNegativePaths:
    def _run(self, session, client):
        src = GeminiSearchSource("g", queries=["q"], client=client)
        rep = service.run_all(session, [src, ok_source()], use_gemini=False, today=TODAY)
        runs = {r.source_name: r for r in session.scalars(select(db.SourceRun))}
        return rep, runs, src

    def test_search_timeout_is_recorded_and_other_sources_still_run(self, session):
        rep, runs, _ = self._run(session, FakeClient(error=TimeoutError("deadline exceeded")))
        assert runs["g"].status == "failed" and "TimeoutError" in runs["g"].error
        assert runs["ok"].status == "ok" and rep.totals.new == 1

    def test_unparseable_search_output_is_a_recorded_failure(self, session):
        _, runs, _ = self._run(session, FakeClient("Sorry, here are some tenders: ..."))
        assert runs["g"].status == "failed" and "parse" in runs["g"].error.lower()

    def test_empty_search_result_is_ok_not_failed(self, session):
        _, runs, _ = self._run(session, FakeClient("[]"))
        assert runs["g"].status == "ok" and runs["g"].fetched == 0

    def test_stats_capture_time_tokens_and_citations(self):
        um = SimpleNamespace(prompt_token_count=10, candidates_token_count=5, total_token_count=15)
        gm = SimpleNamespace(grounding_chunks=[SimpleNamespace(web=SimpleNamespace(title="etimad.sa", uri="https://x"))])
        payload = json.dumps([{"title": "A", "source_url": "https://tenders.etimad.sa/t/1"},
                              {"title": "B", "source_url": "https://random-blog.example/b"}])
        src = GeminiSearchSource("g", queries=["q"], client=FakeClient(
            payload, extra={"usage_metadata": um, "candidates": [SimpleNamespace(grounding_metadata=gm)]}))
        src.fetch()
        st = src.stats[0]
        assert st["tokens"]["total_token_count"] == 15 and st["grounding_sources"] == ["etimad.sa"]
        assert st["ungrounded_urls"] == ["https://random-blog.example/b"] and st["records"] == 2

    def test_gemini_timeout_is_configurable(self, monkeypatch):
        from .. import config
        monkeypatch.setenv("RFP_GEMINI_TIMEOUT_MS", "1234")
        assert config.gemini_timeout_ms() == 1234



def ok_source():
    class Ok(BaseSource):
        def fetch(self):
            return [raw()]
    return Ok("ok")


# ================================================================ P2-12 verified vs unverified wording
class TestAlertWording:
    def _kinds(self, session, rows, **kw):
        class Src(BaseSource):
            data_mode = kw.get("mode", "imported")
            def fetch(self): return rows
        service.run_all(session, [Src("s")], use_gemini=False, today=TODAY)
        return {n.kind: n.message for n in session.scalars(select(db.Notification))}

    def test_search_lead_gets_verification_alert(self, session):
        msgs = self._kinds(session, [raw()], mode="search_discovered")
        assert list(msgs) == ["egypt_verify"] and "not confirmed open" in msgs["egypt_verify"]
        assert "search_discovered" in msgs["egypt_verify"]

    def test_rule_accepted_gets_priority_alert(self, session):
        assert list(self._kinds(session, [raw()])) == ["egypt_priority"]

    def test_unknown_country_gets_generic_verification_alert(self, session):
        assert list(self._kinds(session, [raw(country="Industrial Zone 5")])) == ["needs_review"]

    def test_saudi_unverified(self, session):
        assert list(self._kinds(session, [raw(country="KSA", deadline=None)])) == ["saudi_verify"]
