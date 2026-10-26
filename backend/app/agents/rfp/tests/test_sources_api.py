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
