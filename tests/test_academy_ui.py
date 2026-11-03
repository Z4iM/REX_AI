from pathlib import Path
import requests
from streamlit.testing.v1 import AppTest
from test_connected_workflows import approved_plan, campaign_generator
from backend.app.marketing import service as marketing


def test_navigation_curriculum_and_marketing(catalog_client, staff_headers, approved_plan, campaign_generator, monkeypatch):
    def request(method, url, headers, timeout, **kwargs):
        r = catalog_client.request(method, url, headers=headers, **kwargs)
        response = requests.Response()
        response.status_code, response._content, response.url = r.status_code, r.content, url
        return response
    monkeypatch.setattr(requests, "request", request)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "frontend/app.py"), default_timeout=20).run()
    assert not app.exception
    assert any("What would you like to do?" in title.value for title in app.title)
    app.session_state["staff_key"] = staff_headers["X-API-Key"]
    app.session_state["staff_name"] = "UI Reviewer"
    app.switch_page("pages/8_Curriculum.py").run()
    assert not app.exception
    assert any("Curriculum studio" == title.value for title in app.title)
    assert not any(b.label == "Save as a new curriculum draft" for b in app.button)
    next(b for b in app.button if b.label == "Generate curriculum draft").click().run()
    assert not app.exception
    assert app.radio(key="_view_curriculum_view").value == "Review and revise"
    assert any(b.label == "Save as a new curriculum draft" for b in app.button)
    app.switch_page("pages/9_Marketing.py").run()
    assert not app.exception
    next(e for e in app.text_input if e.label == "Who do you want to reach?").set_value("New Python learners")
    next(e for e in app.button if e.label == "Generate campaign draft").click().run()
    assert not app.exception
    assert app.radio(key="_view_campaign_view").value == "Review and export"
    assert any(b.label == "Save campaign review" for b in app.button)
    next(e for e in app.text_area if e.label == "Campaign review reason").set_value("Verified claims and course details")
    next(e for e in app.checkbox if e.label == "I verified course facts, claims, offers and every channel variation").check()
    next(e for e in app.button if e.label == "Save campaign review").click().run()
    assert not app.exception
    assert marketing.list_campaigns()[0]["status"] == "approved"
