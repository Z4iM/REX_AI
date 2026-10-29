"""Keep every automated test away from local academy data and credentials."""
import os
import pytest


@pytest.fixture(autouse=True)
def isolated_application_data(tmp_path, monkeypatch):
    monkeypatch.setenv("REX_APP_MODE", "academy")
    monkeypatch.setenv("REX_AI_PROVIDER", "gemini")
    # Empty values also prevent load_dotenv() in lazily imported modules from
    # restoring real local credentials. Live tests explicitly opt in themselves.
    for variable in ("GROQ_API_KEY", "GOOGLE_API_KEY", "SMTP_HOST",
                     "SMTP_PASSWORD", "ALERT_EMAILS", "N8N_WEBHOOK_URL", "REX_MCP_STAFF_KEY"):
        monkeypatch.setenv(variable, "")
    if os.getenv("REX_RUN_LIVE_TESTS") != "1":
        monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("REX_RETRIEVAL_BACKEND", "gemini")
    monkeypatch.setenv("REX_CATALOG_DATA_DIR", str(tmp_path / "catalog"))
    monkeypatch.setenv("RFP_DATA_DIR", str(tmp_path / "rfp"))
    monkeypatch.setenv("REX_CURRICULUM_DIR", str(tmp_path / "curriculum"))
    monkeypatch.delenv("RFP_DATABASE_URL", raising=False)
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "768")


@pytest.fixture
def staff_headers(monkeypatch):
    monkeypatch.setenv("REX_CATALOG_ADMIN_KEY", "isolated-catalog-key")
    return {"X-API-Key": "isolated-catalog-key"}


@pytest.fixture
def catalog_client(staff_headers):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def published_course(catalog_client, staff_headers):
    from backend.app.catalog import catalog_service as store, approved_index
    from test_catalog_approval_publication import FakeCollection, fake_embed, valid_approval
    response = catalog_client.post("/api/v1/catalog/uploads", headers=staff_headers,
                                  files={"file": ("fixture.md", b"## Python\nAn isolated course source.")})
    assert response.status_code == 201
    upload_id = response.json()["upload_id"]
    store.approve_upload(upload_id, valid_approval())
    collection = FakeCollection()
    approved_index.publish_course("PY-101", collection=collection, embedder=fake_embed)
    return store.get_course("PY-101", staff=True), collection
