import pytest
from backend.app.catalog import metadata_extraction as extraction, catalog_service as store

BASE = "/api/v1/catalog/uploads"
CONTENT = b"""## Python basics
Course ID: PY-101
Description: Learn the verified Python language fundamentals.
Level: Beginner
Training format: Online
Price EGP: 2500
Duration: 20 hours
Learning outcomes: Read Python; Write functions

## Other course
Course ID: OT-101
Description: A second isolated course for multi-course extraction.
Price: 200 USD
"""


@pytest.fixture
def uploaded(catalog_client, staff_headers):
    response = catalog_client.post(BASE, headers=staff_headers, files={"file": ("courses.md", CONTENT)})
    assert response.status_code == 201
    return response.json()["upload_id"]


def test_multiple_courses_extract_without_approval(catalog_client, staff_headers, uploaded):
    response = catalog_client.post(f"{BASE}/{uploaded}/extract-metadata", headers=staff_headers,
                                   json={"reviewer": "Reviewer"})
    assert response.status_code == 200, response.text
    candidates = response.json()["candidates"]
    assert len(candidates) == 2
    assert candidates[0]["fields"]["price_egp"] == 2500
    assert candidates[0]["fields"]["duration_hours"] == 20
    assert candidates[0]["fields"]["learning_outcomes"] == ["Read Python", "Write functions"]
    assert "price_egp" not in candidates[1]["fields"]
    record = store.load_upload(uploaded)
    assert record["approval_status"] == "unapproved"
    assert record["metadata_suggestions"] == response.json()
    assert record["review_history"][-1]["reviewer"] == "Reviewer"
    assert store.list_courses(staff=True) == []


def test_ai_must_return_exact_source_evidence(catalog_client, staff_headers, uploaded, monkeypatch):
    review = store.load_upload(uploaded)
    chunk = review["chunks"][0]
    def fake(system, payload):
        return {"courses": [{"fields": [{"field": "title", "quote": "Imaginary course", "chunk_id": chunk["chunk_id"]}]}]}
    monkeypatch.setattr(extraction, "generate_json", fake)
    response = catalog_client.post(f"{BASE}/{uploaded}/extract-metadata", headers=staff_headers,
                                   json={"reviewer": "Reviewer", "method": "gemini"})
    assert response.status_code == 503
    assert "metadata_suggestions" not in store.load_upload(uploaded)


def test_ai_supported_quote_remains_unapproved(catalog_client, staff_headers, uploaded, monkeypatch):
    chunk = store.load_upload(uploaded)["chunks"][0]
    monkeypatch.setattr(extraction, "generate_json", lambda *args: {"courses": [{"fields": [
        {"field": "course_id", "quote": "PY-101", "chunk_id": chunk["chunk_id"]}]}]})
    response = catalog_client.post(f"{BASE}/{uploaded}/extract-metadata", headers=staff_headers,
                                   json={"reviewer": "Reviewer", "method": "gemini"})
    assert response.status_code == 200
    assert response.json()["review_required"]
    assert response.json()["candidates"][0]["fields"] == {"course_id": "PY-101"}


def test_rejected_and_unauthorized_cannot_extract(catalog_client, staff_headers, uploaded):
    path = f"{BASE}/{uploaded}/extract-metadata"
    assert catalog_client.post(path, json={"reviewer": "Reviewer"}).status_code == 401
    assert catalog_client.post(path, headers=staff_headers, json={"reviewer": " "}).status_code == 422
    store.reject_upload(uploaded, store.DocumentRejection(reviewer="Reviewer", reason="Missing evidence"))
    assert catalog_client.post(path, headers=staff_headers, json={"reviewer": "Reviewer"}).status_code == 409
