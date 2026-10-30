import pytest
from backend.app.assistant.leads import list_leads
from backend.app.catalog.catalog_service import catalog_transaction


@pytest.fixture
def completed(catalog_client):
    token = None
    for message in ("Learn Python", "Graduate", "Beginner", "Developer", "Online", "4000 EGP", "5 hours"):
        body = {"message": message, "session_id": token}
        response = catalog_client.post("/api/v1/qualification", json=body)
        assert response.status_code == 200
        token = response.json()["session_id"]
    return token


def test_lead_consent_persistence_authorization_and_deletion(catalog_client, completed, staff_headers):
    path = f"/api/v1/qualification/{completed}/lead"
    payload = {"name": "Test Learner", "email": "learner@example.test", "consent": True}
    first = catalog_client.post(path, json=payload)
    assert first.status_code == 201
    assert len(list_leads()) == 1
    assert catalog_client.post(path, json=payload).json()["lead_id"] == first.json()["lead_id"]
    assert len(list_leads()) == 1
    assert catalog_client.get("/api/v1/catalog/staff/leads").status_code == 401
    assert catalog_client.get("/api/v1/catalog/staff/leads", headers=staff_headers).json()["count"] == 1
    assert catalog_client.delete(path).status_code == 204
    assert list_leads() == []


@pytest.mark.parametrize("body", [
    {"name": "Learner", "email": "learner@example.test", "consent": False},
    {"name": "Learner", "email": "learner@example.test", "consent": 1},
    {"name": "Learner", "email": "learner@example.test"},
    {"name": "Learner", "email": "invalid", "consent": True},
    {"name": "Learner", "consent": True},
    {"name": " ", "phone": "+201001234567", "consent": True},
])
def test_invalid_or_missing_consent_never_saves(catalog_client, completed, body):
    assert catalog_client.post(f"/api/v1/qualification/{completed}/lead", json=body).status_code == 422
    assert list_leads() == []


def test_expiry_and_revoke_after_session_expiry(catalog_client, completed):
    path = f"/api/v1/qualification/{completed}/lead"
    assert catalog_client.post(path, json={"name": "Learner", "phone": "+201001234567", "consent": True}).status_code == 201
    with catalog_transaction() as con:
        con.execute("UPDATE qualification_sessions SET expires_at=0")
    assert catalog_client.delete(path).status_code == 204
    assert list_leads() == []


def test_incomplete_session_cannot_create_lead(catalog_client):
    token = catalog_client.post("/api/v1/qualification", json={"message": "Learn Python"}).json()["session_id"]
    assert catalog_client.post(f"/api/v1/qualification/{token}/lead", json={
        "name": "Learner", "phone": "+201001234567", "consent": True}).status_code == 409


def test_lead_expiry_is_enforced(catalog_client, completed):
    assert catalog_client.post(f"/api/v1/qualification/{completed}/lead", json={
        "name": "Learner", "phone": "+201001234567", "consent": True}).status_code == 201
    with catalog_transaction() as con:
        con.execute("UPDATE learner_leads SET expires_at=0")
    assert list_leads() == []


def test_forget_profile_removes_contact_record(catalog_client, completed):
    assert catalog_client.post(f"/api/v1/qualification/{completed}/lead", json={
        "name": "Learner", "phone": "+201001234567", "consent": True}).status_code == 201
    assert catalog_client.delete(f"/api/v1/qualification/{completed}").status_code == 204
    assert list_leads() == []


def test_deleted_session_cannot_race_a_contact_save(catalog_client, completed, monkeypatch):
    from backend.app.assistant import leads
    from backend.app.assistant.session_store import delete_session
    original = leads.get_session
    def get_then_delete(token):
        result = original(token)
        delete_session(token)
        return result
    monkeypatch.setattr(leads, "get_session", get_then_delete)
    assert catalog_client.post(f"/api/v1/qualification/{completed}/lead", json={
        "name": "Learner", "phone": "+201001234567", "consent": True}).status_code == 404
    assert list_leads() == []
