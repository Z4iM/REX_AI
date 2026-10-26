"""Headless UI smoke tests with Streamlit AppTest."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parent.parent.parent


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("RFP_DATABASE_URL", f"sqlite:///{tmp_path / 'ui.db'}")
    return AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=60).run()


def click(at, key):
    [b for b in at.button if b.key == "rfp_" + key][0].click().run()


def test_loads_empty_without_errors(app):
    assert not app.exception
    assert [m.value for m in app.metric][:1] == ["0"]


def test_demo_load_updates_metrics_and_filters_work(app):
    click(app, "load_demo")
    assert not app.exception
    assert int(app.metric[0].value) > 0
    app.selectbox(key="rfp_country").set_value("Egypt").run()
    assert not app.exception and "result(s)" in app.markdown[0].value
    app.text_input(key="rfp_q").set_value("zzzz-no-match").run()
    assert "**0** result(s)" in app.markdown[0].value


def test_demo_banner_and_removal(app):
    click(app, "load_demo")
    assert any("synthetic demo" in w.value for w in app.warning)
    click(app, "rm_demo")
    assert app.metric[0].value == "0"


def test_paste_requires_url(app):
    app.text_area(key="rfp_paste_text").set_value("some tender text").run()
    click(app, "extract_btn")
    assert any("valid http" in e.value for e in app.error)
