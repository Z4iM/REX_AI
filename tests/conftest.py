"""Keep every automated test away from local academy data and credentials."""
import pytest


@pytest.fixture(autouse=True)
def isolated_application_data(tmp_path, monkeypatch):
    monkeypatch.setenv("REX_APP_MODE", "academy")
    monkeypatch.setenv("REX_CATALOG_DATA_DIR", str(tmp_path / "catalog"))
    monkeypatch.setenv("RFP_DATA_DIR", str(tmp_path / "rfp"))
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
