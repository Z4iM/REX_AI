"""Sources parsing, Gemini extraction (mocked) and the protected FastAPI endpoints."""
import io
import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .. import router as router_mod
from .. import sources
from ..sources import FolderSource, FileSource, SourceError, parse_date, parse_upload, extract_tenders_from_text


# ---------------------------------------------------------------- parsing
@pytest.mark.parametrize("v,exp", [("2026-11-10", date(2026, 11, 10)), ("2026/11/10", date(2026, 11, 10)),
                                   ("15/12/2026", date(2026, 12, 15)), ("2026-11-10 14:30", date(2026, 11, 10)),
                                   ("1448/05/10", None), ("garbage", None), (None, None), ("", None)])
def test_parse_date(v, exp):
    assert parse_date(v) == exp


def test_iso_dates_are_not_day_month_swapped():
    # regression: dayfirst=True used to turn 2026-11-10 into 11 Oct
    assert parse_date("2026-11-10").month == 11


def test_parse_csv_json_xlsx():
    csv_bytes = "title,issuer\nTraining A,Org\n".encode()
    assert parse_upload("a.csv", csv_bytes)[0]["title"] == "Training A"
    assert parse_upload("a.json", json.dumps({"tenders": [{"title": "B"}]}).encode())[0]["title"] == "B"
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["اسم المنافسة", "الجهة"])
    ws.append(["تدريب", "وزارة"])
    buf = io.BytesIO()
    wb.save(buf)
    assert parse_upload("a.xlsx", buf.getvalue())[0]["اسم المنافسة"] == "تدريب"
    with pytest.raises(SourceError):
        parse_upload("a.pdf", b"x")


def test_folder_source_reads_supported_files_only(tmp_path):
    (tmp_path / "a.csv").write_text("title\nT1\nT2\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore me")
    rows = FolderSource("f", path=str(tmp_path)).fetch()
    assert [r["title"] for r in rows] == ["T1", "T2"] and rows[0]["_file_ref"] == "a.csv#row1"


def test_file_source_missing_file():
    with pytest.raises(SourceError):
        FileSource("x", path="/nonexistent/file.json").fetch()


def test_load_sources_respects_enabled_flag(tmp_path):
    cfg = tmp_path / "s.yaml"
    cfg.write_text("sources:\n  - {name: a, type: folder, path: x, enabled: true}\n"
                   "  - {name: b, type: folder, path: y, enabled: false}\n", encoding="utf-8")
    assert [s.name for s in sources.load_sources(cfg)] == ["a"]
    assert [s.name for s in sources.load_sources(cfg, include_disabled=True)] == ["a", "b"]
    assert [s.name for s in sources.load_sources(cfg, only=["b"])] == ["b"]


def test_default_sources_yaml_is_valid():
    names = [s.name for s in sources.load_sources(include_disabled=True)]
    assert "manual_imports" in names and "gemini_web_discovery" in names


# ---------------------------------------------------------------- robots / web safety
def test_robots_blocks_when_unreachable(monkeypatch):
    sources._robots_cache.clear()

    def boom(*a, **k):
        raise sources.requests.ConnectionError("down")
    monkeypatch.setattr(sources.requests, "get", boom)
    assert sources.robots_allows("https://portal.example/tenders") is False


def test_robots_disallow_rule_respected(monkeypatch):
    sources._robots_cache.clear()
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: SimpleNamespace(
        status_code=200, text="User-agent: *\nDisallow: /private/"))
    assert sources.robots_allows("https://portal.example/private/x") is False
    assert sources.robots_allows("https://portal.example/public/x") is True


def test_html_source_parses_with_selectors(monkeypatch):
    html = """<table class=t><tr><td class=n><a href="/t/5">Digital Skills Training</a></td>
              <td class=a>Ministry Y</td><td class=d>2026-12-01</td></tr></table>"""
    monkeypatch.setattr(sources, "polite_get", lambda url, delay=0: SimpleNamespace(text=html))
    src = sources.HTMLListSource("h", url="https://portal.example/list", item_selector="table.t tr",
                                 fields={"title": "td.n a", "source_url": "td.n a@href", "issuer": "td.a",
                                         "deadline": "td.d"}, default_country="Egypt")
    rows = src.fetch()
    assert rows == [{"title": "Digital Skills Training", "source_url": "https://portal.example/t/5",
                     "issuer": "Ministry Y", "deadline": "2026-12-01"}]


def test_html_source_layout_change_is_an_error(monkeypatch):
    monkeypatch.setattr(sources, "polite_get", lambda url, delay=0: SimpleNamespace(text="<html></html>"))
    with pytest.raises(SourceError):
        sources.HTMLListSource("h", url="https://x.example", item_selector="tr.row", fields={"title": "a"}).fetch()


# ---------------------------------------------------------------- Gemini extraction (mocked)
class FakeClient:
    def __init__(self, text):
        self.models, self.text = self, text

    def generate_content(self, **kw):
        return SimpleNamespace(text=self.text)


def test_extract_from_text_adds_source_url():
    out = extract_tenders_from_text("some page text", "https://portal.example/p/1",
                                    client=FakeClient(json.dumps([{"title": "X Training", "country": "Egypt"}])))
    assert out[0]["source_url"] == "https://portal.example/p/1"


def test_extract_handles_fenced_json_and_single_object():
    out = extract_tenders_from_text("t", "https://a.example", client=FakeClient('```json\n{"title":"Y"}\n```'))
    assert out[0]["title"] == "Y"


def test_gemini_search_requires_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(sources.SourceSkipped):
        sources.GeminiSearchSource("g", queries=["q"]).fetch()


def test_gemini_search_drops_records_without_url():
    payload = json.dumps([{"title": "A", "source_url": "https://portal.example/a"}, {"title": "B", "source_url": None},
                          {"title": "C", "source_url": "javascript:alert(1)"}])
    out = sources.GeminiSearchSource("g", queries=["q"], client=FakeClient(payload)).fetch()
    assert [d["title"] for d in out] == ["A"] and "data_mode" not in out[0]
    assert sources.GeminiSearchSource.data_mode == "search_discovered"


# ---------------------------------------------------------------- API
@pytest.fixture()
def client(factory, monkeypatch, demo_raw):
    monkeypatch.setenv("RFP_API_KEY", "secret-123")
    rows = [dict(r) for r in demo_raw[:8]]

    class Src(sources.BaseSource):
        def fetch(self):
            return rows

    app = FastAPI()
    app.include_router(router_mod.build_router(session_factory=factory, sources_loader=lambda only=None: [Src("demo")]))
    return TestClient(app)


H = {"X-API-Key": "secret-123"}


def test_unknown_route_is_404(client):
    assert client.get('/nope').status_code == 404


def test_protected_routes_need_key(client):
    assert client.get("/api/v1/rfp/opportunities").status_code == 401
    assert client.get("/api/v1/rfp/opportunities", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/api/v1/rfp/run", json={}).status_code == 401


def test_api_refuses_when_no_key_configured(client, monkeypatch):
    monkeypatch.delenv("RFP_API_KEY", raising=False)
    assert client.get("/api/v1/rfp/opportunities", headers=H).status_code == 503


def test_run_list_get_patch_and_notifications(client):
    r = client.post("/api/v1/rfp/run", headers=H, json={"use_gemini": False}).json()
    assert r["new_count"] > 0 and "updated" in r and r["sources"][0]["status"] == "ok"
    items = client.get("/api/v1/rfp/opportunities", headers=H).json()["items"]
    assert items and all(i["country_code"] in ("EG", "SA", None) for i in items)
    eg = client.get("/api/v1/rfp/opportunities?country=EG", headers=H).json()["items"]
    assert eg and all(i["country_code"] == "EG" for i in eg)
    assert client.get("/api/v1/rfp/opportunities?country=DE", headers=H).status_code == 422
    oid = items[0]["id"]
    assert client.get(f"/api/v1/rfp/opportunities/{oid}", headers=H).status_code == 200
    p = client.patch(f"/api/v1/rfp/opportunities/{oid}", headers=H, json={"workflow_status": "reviewing"})
    assert p.json()["workflow_status"] == "reviewing"
    assert client.patch(f"/api/v1/rfp/opportunities/{oid}", headers=H, json={"workflow_status": "nope"}).status_code == 422
    assert client.get("/api/v1/rfp/opportunities/99999", headers=H).status_code == 404
    assert client.get(f"/api/v1/rfp/opportunities/{oid}/history", headers=H).status_code == 200
    assert client.get("/api/v1/rfp/notifications", headers=H).json()["count"] > 0
    # second run: nothing new
    assert client.post("/api/v1/rfp/run", headers=H, json={"use_gemini": False}).json()["new_count"] == 0


def test_langsearch_runs_existing_filters_and_keeps_results_unverified(session, monkeypatch):
    from .. import db, service

    def page(id, country, deadline):
        return {
            "url": f"https://www.ungm.org/Public/Notice/{id}",
            "datePublished": "2099-12-01",
            "text": (
                "Professional staff training\n\nTest issuer\n\nProfessional staff training Request for proposal"
                f"\nReference: TEST-{id}\nBeneficiary countries or territories: {country}"
                f"\nPublished on: 01-Oct-2026\nDeadline on: {deadline} 14:00"
                "\nDescription\nDeliver software training and professional development for staff."
            ),
        }

    egypt = page(1, "Egypt", "20-Nov-2026")
    async def search(self, key):
        return [egypt, egypt, page(2, "Saudi Arabia", "20-Nov-2026"),
                page(3, "Egypt", "20-Oct-2026"), page(4, "Germany", "20-Nov-2026"),
                {**egypt, "url": "https://ungm.org.example.invalid/Public/Notice/5"}]

    monkeypatch.setenv("LANGSEARCH_API_KEY", "isolated-test-key")
    monkeypatch.setattr(sources.LangSearchSource, "_search", search)
    source = sources.load_sources(only=[sources.LANGSEARCH_SOURCE])[0]
    result = service.run_all(session, [source], today=date(2026, 11, 3), use_gemini=False, notify=False)
    assert result.totals.fetched == 4
    assert result.totals.new == 2
    assert result.totals.rejected == 2
    rows = db.search_opportunities(session, include_expired=True)
    assert {row.country_code for row in rows} == {"EG", "SA"}
    assert all(row.filter_status == "needs_review" for row in rows)
    assert all(row.publication_date == date(2026, 10, 1) for row in rows)


def test_langsearch_skips_without_key_and_sanitizes_transport_error(monkeypatch):
    source = sources.LangSearchSource("test")
    monkeypatch.delenv("LANGSEARCH_API_KEY", raising=False)
    with pytest.raises(sources.SourceSkipped, match="LANGSEARCH_API_KEY"):
        source.fetch()
    monkeypatch.setenv("LANGSEARCH_API_KEY", "isolated-test-key")

    async def fail(key):
        raise RuntimeError(key)

    monkeypatch.setattr(source, "_search", fail)
    with pytest.raises(SourceError, match="LangSearch web search failed") as error:
        source.fetch()
    assert "isolated-test-key" not in str(error.value)


def test_etimad_uses_offer_deadline_and_execution_country():
    result = {
        "url": "https://tenders.etimad.sa/Tender/OpenTenderDetailsReportForVisitor?tenderIdString=sample",
        "text": (
            "الجهة الحكومية | Test agency\nالمعلومات الأساسية | إسم المنافسة: Professional training"
            "\nرقم المنافسة: 26/59\nالغاية من المنافسة | Training for staff"
            "\nاخر موعد لإستلام استفسارات الموردين | التاريخ: 15/05/1448\nالموافق: 26/10/2026"
            "\nاخر موعد لإستلام العروض | التاريخ: 16/05/1448\nالموافق: 20/11/2026"
            "\nمكان التنفيذ | داخل المملكة"
        ),
    }
    parsed = sources._other_public_notice(result)
    assert parsed["country"] == "Saudi Arabia"
    assert parsed["deadline"] == date(2026, 11, 20)
    assert parsed["tender_id"] == "26/59"
    assert sources._other_public_notice({**result, "text": result["text"].replace("داخل المملكة", "خارج المملكة")}) is None
    assert sources._other_public_notice({**result, "url": result["url"].replace("etimad.sa", "etimad.sa.example.invalid")}) is None
    assert sources._other_public_notice({**result, "text": result["text"].replace("20/11/2026", "")}) is None


def test_public_training_directories_discover_open_leads(session, monkeypatch):
    from .. import service
    egypt = """<div itemtype="http://schema.org/Event">
    <p itemprop="description">Staff training in digital skills</p><p itemprop="location">Egypt</p>
    <p itemprop="endDate">18 Nov 2026</p><a itemprop="url" href="https://www.globaltenders.com/tender-detail/test">Open</a></div>"""
    saudi = """<table><tr><td class="t-title"><span>Training for employees</span><small>Ref. 261139000552</small></td>
    <td class="t-entity">Public agency</td><td class="t-close"><time datetime="2026-11-07T06:59:00.000Z"></time></td>
    <td class="t-link"><a href="https://tenders.etimad.sa/Tender/DetailsForVisitor?STenderId=example%3D">Notice</a></td></tr></table>"""
    egypt += egypt.replace("Staff training in digital skills", "Supply of training uniforms").replace("/test", "/supplies")
    bodies = dict(zip(sources.PUBLIC_RFP_LISTINGS.values(), (egypt, saudi)))
    monkeypatch.setattr(sources, "polite_get", lambda url: SimpleNamespace(content=bodies[url].encode()))
    result = service.run_all(session, sources.load_sources(only=list(sources.PUBLIC_RFP_LISTINGS)),
                             today=date(2026, 11, 3), use_gemini=False, notify=False)
    assert result.totals.new == 2, result.per_source
    assert {r.country_code for r in result.totals.new_opportunities} == {"EG", "SA"}
    assert all(r.filter_status == "needs_review" for r in result.totals.new_opportunities)


def test_ungm_implementing_partner_notice_is_readable():
    page = {"url": "https://www.ungm.org/Public/Notice/123",
            "text": "Vocational training\nILO\nVocational training Call for implementing partners\nReference: 123"
                    "\nBeneficiary countries or territories: Egypt\nDeadline on: 15-Nov-2026 16:00\nDescription\nTraining"}
    assert sources._ungm_notice(page)["deadline"] == date(2026, 11, 15)
