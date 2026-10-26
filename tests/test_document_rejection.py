"""Offline rejection workflow tests with isolated files/SQLite and the real API/UI."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event

import pytest
import requests
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.catalog import approved_index, catalog_service as store
from backend.app.catalog.approval_router import public_router, staff_router
from backend.app.catalog.upload_router import router

BASE = "/api/v1/catalog"
HEADERS = {"X-API-Key": "offline-test-key"}
DECISION = {"reviewer": "  Reviewer One  ", "reason": "  Required syllabus details are missing.  "}
APPROVAL = {"course_id": "TEST-101", "title": "Test course", "description": "Isolated test course description.",
            "reviewer": "Test reviewer"}
SOURCE = b"## Test course\n\nAn isolated source document for rejection workflow tests."


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REX_CATALOG_DATA_DIR", str(tmp_path / "catalog"))
    monkeypatch.setenv("REX_CATALOG_ADMIN_KEY", HEADERS["X-API-Key"])
    app = FastAPI()
    app.include_router(router)
    app.include_router(staff_router)
    app.include_router(public_router)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def upload(client):
    response = client.post(BASE + "/uploads", headers=HEADERS, files={"file": ("test.md", SOURCE)})
    assert response.status_code == 201, response.text
    upload_id = response.json()["upload_id"]
    return upload_id, store.data_dir() / "uploads" / upload_id


def reject(client, upload_id, **kwargs):
    return client.post(f"{BASE}/uploads/{upload_id}/reject", headers=HEADERS,
                       json=kwargs or DECISION)


@pytest.mark.parametrize("status", ["pending_review", "blocked_incomplete"])
def test_rejection_persists_decision_audit_and_original_evidence(client, upload, status):
    upload_id, folder = upload
    path = folder / "review.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    original["review_status"] = status
    original["review_history"] = [{"action": "received", "reviewer": "Uploader", "recorded_at": "earlier"}]
    if status == "blocked_incomplete":
        original["missing_pages"] = [2]
        original["chunks"] = []  # Incomplete evidence must still be rejectable.
    path.write_text(json.dumps(original), encoding="utf-8")

    response = reject(client, upload_id)
    assert response.status_code == 200, response.text
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["review_status"] == saved["approval_status"] == "rejected"
    assert saved["indexing_allowed"] is False
    assert saved["rejected_by"] == DECISION["reviewer"].strip()
    assert saved["rejection_reason"] == DECISION["reason"].strip()
    assert datetime.fromisoformat(saved["rejected_at"]).utcoffset().total_seconds() == 0
    assert saved["review_history"][:-1] == original["review_history"]
    assert saved["review_history"][-1] == {
        "action": "rejected", "reviewer": saved["rejected_by"], "reason": saved["rejection_reason"],
        "recorded_at": saved["rejected_at"], "previous_review_status": status,
    }
    for field in ("chunks", "missing_pages", "extraction_warnings", "source_sha256"):
        assert saved[field] == original[field]
    assert (folder / "source.md").read_bytes() == SOURCE
    assert not list(folder.glob("*.tmp"))
    # New requests must read persisted state, not an in-memory decision.
    detail = client.get(f"{BASE}/uploads/{upload_id}", headers=HEADERS).json()
    for field in response.json():
        assert detail[field] == response.json()[field]
    assert client.get(BASE + "/uploads", headers=HEADERS).json()["items"][0]["review_status"] == "rejected"
    assert store.list_courses(staff=True) == store.list_courses() == []


@pytest.mark.parametrize("body", [
    {}, {"reviewer": "Staff"}, {"reason": "Missing details"},
    {"reviewer": "  ", "reason": "Missing details"}, {"reviewer": "a", "reason": "Missing details"},
    {"reviewer": "x" * 121, "reason": "Missing details"},
    {"reviewer": "Staff", "reason": ""}, {"reviewer": "Staff", "reason": " \n\t "},
    {"reviewer": "Staff", "reason": "x" * 4001}, {"reviewer": "Staff", "reason": None},
    {"reviewer": 123, "reason": "Missing details"}, {"reviewer": "Staff", "reason": ["bad"]},
    {**DECISION, "approval_status": "published"},
])
def test_invalid_payload_does_not_change_manifest(client, upload, body):
    upload_id, folder = upload
    before = (folder / "review.json").read_bytes()
    response = client.post(f"{BASE}/uploads/{upload_id}/reject", headers=HEADERS, json=body)
    assert response.status_code == 422
    assert (folder / "review.json").read_bytes() == before


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_rejection_requires_existing_admin_auth(client, upload, headers):
    upload_id, folder = upload
    before = (folder / "review.json").read_bytes()
    response = client.post(f"{BASE}/uploads/{upload_id}/reject", headers=headers, json=DECISION)
    assert response.status_code == 401
    assert (folder / "review.json").read_bytes() == before


def test_admin_not_configured_fails_closed(client, upload, monkeypatch):
    monkeypatch.delenv("REX_CATALOG_ADMIN_KEY")
    assert reject(client, upload[0]).status_code == 503


@pytest.mark.parametrize("upload_id", ["a" * 64, "invalid-id", "..%2F..%2Fsource"])
def test_unknown_or_invalid_upload_id(client, upload_id):
    assert reject(client, upload_id).status_code == 404


def test_repeated_rejection_and_duplicate_upload_preserve_original_decision(client, upload):
    upload_id, folder = upload
    assert reject(client, upload_id).status_code == 200
    saved = (folder / "review.json").read_bytes()
    assert reject(client, upload_id, reviewer="Other reviewer", reason="New reason").status_code == 409
    duplicate = client.post(BASE + "/uploads", headers=HEADERS,
                            files={"file": ("renamed.md", SOURCE)}).json()
    assert duplicate["already_uploaded"] is True
    assert duplicate["review_status"] == duplicate["approval_status"] == "rejected"
    assert "rejected" in duplicate["message"]
    assert (folder / "review.json").read_bytes() == saved


def test_rejected_upload_cannot_approve_or_publish(client, upload):
    upload_id, _ = upload
    assert reject(client, upload_id).status_code == 200
    response = client.post(f"{BASE}/uploads/{upload_id}/approve", headers=HEADERS, json=APPROVAL)
    assert response.status_code == 409
    assert "Rejected" in response.json()["detail"]
    assert client.post(f"{BASE}/staff/courses/TEST-101/publish", headers=HEADERS).status_code == 404
    assert store.list_courses(staff=True) == []


@pytest.mark.parametrize("status", ["approved", "index_failed", "published"])
def test_linked_courses_protected_until_explicit_withdrawal(client, upload, status):
    upload_id, folder = upload
    store.approve_upload(upload_id, store.CourseApproval(**APPROVAL))
    if status == "index_failed":
        store.mark_index_failed("TEST-101", upload_id, "RuntimeError")
    elif status == "published":
        store.set_published("TEST-101", upload_id)
    manifest_before = (folder / "review.json").read_bytes()
    course_before = store.get_course("TEST-101", staff=True)
    history_before = store.course_history("TEST-101")
    public_before = store.list_courses()
    response = reject(client, upload_id)
    assert response.status_code == 409
    assert "Withdraw every course" in response.json()["detail"]
    assert (folder / "review.json").read_bytes() == manifest_before
    assert store.get_course("TEST-101", staff=True) == course_before
    assert store.course_history("TEST-101") == history_before
    assert store.list_courses() == public_before
    assert store.is_published("TEST-101", upload_id) is (status == "published")

    store.withdraw_course("TEST-101", "Staff")
    assert reject(client, upload_id).status_code == 200
    assert store.get_course("TEST-101", staff=True)["status"] == "withdrawn"
    assert store.list_courses() == []
    assert client.post(f"{BASE}/uploads/{upload_id}/approve", headers=HEADERS, json=APPROVAL).status_code == 409
    assert client.post(f"{BASE}/staff/courses/TEST-101/publish", headers=HEADERS).status_code == 409


def test_all_linked_courses_must_be_withdrawn(client, upload):
    upload_id, _ = upload
    for course_id in ("TEST-101", "TEST-102"):
        store.approve_upload(upload_id, store.CourseApproval(**{**APPROVAL, "course_id": course_id}))
    store.withdraw_course("TEST-101", "Staff")
    assert reject(client, upload_id).status_code == 409
    store.withdraw_course("TEST-102", "Staff")
    assert reject(client, upload_id).status_code == 200


@pytest.mark.parametrize("field", ["review_status", "approval_status"])
def test_publication_rechecks_rejection_before_embeddings_and_final_gate(client, upload, monkeypatch, field):
    upload_id, folder = upload
    store.approve_upload(upload_id, store.CourseApproval(**APPROVAL))
    path = folder / "review.json"
    review = json.loads(path.read_text(encoding="utf-8"))
    # Defense in depth for a legacy/inconsistent approved row referencing a rejected manifest.
    review[field] = "rejected"
    path.write_text(json.dumps(review), encoding="utf-8")

    def forbidden_collection():
        pytest.fail("A rejected document must never reach Chroma or Gemini")

    monkeypatch.setattr(approved_index, "_collection", forbidden_collection)
    assert client.post(f"{BASE}/staff/courses/TEST-101/publish", headers=HEADERS).status_code == 409
    with pytest.raises(HTTPException) as exc:
        store.set_published("TEST-101", upload_id)
    assert exc.value.status_code == 409
    assert store.get_course("TEST-101", staff=True)["status"] == "approved"
    assert store.list_courses() == []


def test_failed_atomic_replace_preserves_original_and_allows_retry(client, upload, monkeypatch):
    upload_id, folder = upload
    before = (folder / "review.json").read_bytes()
    with monkeypatch.context() as patch:
        def fail_replace(*args):
            raise OSError("Simulated disk failure")
        patch.setattr(store.os, "replace", fail_replace)
        response = reject(client, upload_id)
    assert response.status_code == 503
    assert (folder / "review.json").read_bytes() == before
    assert not list(folder.glob("*.tmp"))
    assert reject(client, upload_id).status_code == 200


def test_integrity_failure_does_not_write_decision(client, upload):
    upload_id, folder = upload
    before = (folder / "review.json").read_bytes()
    (folder / "source.md").write_bytes(b"Changed source")
    assert reject(client, upload_id).status_code == 409
    assert (folder / "review.json").read_bytes() == before


@pytest.mark.parametrize("first", ["approve", "reject"])
def test_concurrent_approval_and_rejection_cannot_both_succeed(client, upload, monkeypatch, first):
    upload_id, _ = upload
    entered, release, second_started = Event(), Event(), Event()
    original = store.require_unrejected_upload if first == "approve" else store._write_upload_review

    def pause(*args):
        original(*args)
        entered.set()
        assert release.wait(5), "Timed out waiting to release first decision"

    monkeypatch.setattr(store, "require_unrejected_upload" if first == "approve" else "_write_upload_review", pause)

    def decide(action, second=False):
        if second:
            second_started.set()
        try:
            if action == "approve":
                store.approve_upload(upload_id, store.CourseApproval(**APPROVAL))
            else:
                store.reject_upload(upload_id, store.DocumentRejection(**DECISION))
            return 200
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_result = pool.submit(decide, first)
        try:
            assert entered.wait(5)
            second_result = pool.submit(decide, "reject" if first == "approve" else "approve", True)
            assert second_started.wait(5)
        finally:
            release.set()
        assert first_result.result(timeout=5) == 200
        assert second_result.result(timeout=5) == 409
    assert (store.load_upload(upload_id)["review_status"] == "rejected") is (first == "reject")
    assert len(store.list_courses(staff=True)) == (1 if first == "approve" else 0)


def test_streamlit_reject_form_validates_and_shows_saved_history(client, upload, monkeypatch):
    from streamlit.testing.v1 import AppTest

    def request(method, url, headers, timeout, **kwargs):
        result = client.request(method, url, headers=headers, **kwargs)
        response = requests.Response()
        response.status_code = result.status_code
        response._content = result.content
        response.url = url
        return response

    monkeypatch.setattr(requests, "request", request)
    page = Path(__file__).resolve().parents[1] / "frontend/pages/4_Course_Approvals.py"
    app = AppTest.from_file(str(page)).run()
    app.session_state["staff_key"] = HEADERS["X-API-Key"]
    app.session_state["staff_name"] = "UI Reviewer"
    app.run()
    assert not app.exception

    def element(elements, label):
        return next(e for e in elements if e.label == label)

    element(app.button, "Reject document").click().run()
    assert any("Enter a reviewer" in e.value for e in app.error)
    element(app.text_area, "Rejection reason (required)").set_value("Missing verified learning outcomes")
    element(app.checkbox, "Confirm rejection of this source document").check()
    element(app.button, "Reject document").click().run()
    assert not app.exception
    assert any("Document rejected" in e.value for e in app.success)
    assert element(app.button, "Reject document").disabled
    assert element(app.button, "Save verified course").disabled
    assert any("Missing verified learning outcomes" in e.value for e in app.text)
    assert any("UI Reviewer" in e.value for e in app.markdown)
    saved = store.load_upload(upload[0])
    assert saved["rejected_by"] == "UI Reviewer" and len(saved["review_history"]) == 1
