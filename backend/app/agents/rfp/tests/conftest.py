import json
from pathlib import Path

import pytest

from .. import db

PKG = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    for k in ("GEMINI_API_KEY", "RFP_API_KEY", "RFP_DASHBOARD_PASSWORD", "RFP_REQUIRE_LOGIN", "SMTP_HOST",
              "ALERT_EMAILS", "N8N_WEBHOOK_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("RFP_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture()
def factory(tmp_path):
    return db.get_session_factory(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture()
def session(factory):
    with factory() as s:
        yield s


@pytest.fixture(scope="session")
def demo_raw():
    return json.loads((PKG / "sample_tenders.json").read_text(encoding="utf-8"))
