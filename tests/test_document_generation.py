"""Real DOCX/PDF files and persistent workflow; only Gemini generation is mocked."""
from io import BytesIO
from pathlib import Path
import json
import pytest
import pymupdf
from docx import Document
from backend.app.documents import service
from backend.app.catalog import catalog_service as store

BASE = "/api/v1/documents"


@pytest.fixture
def generator(monkeypatch):
    def compose(system, payload):
        arabic = payload["language"] == "ar"
        return {"title": "دليل دورة بايثون" if arabic else "Verified Python course document", "sections": [
            {"heading": heading, "text": "تعلم أساسيات بايثون ومراجعة المتطلبات السابقة مع الأكاديمية." if arabic else
             "Verified Python covers the approved learning outcome Use Python. Confirm prerequisites with academy staff.",
             "source_ids": [s["source_id"] for s in payload["sources"]]}
            for heading in (["نظرة عامة", "مخرجات التعلم", "متطلبات المشاركة"] if arabic else payload["template"]["sections"])]}
    monkeypatch.setattr(service, "generate_json", compose)
    return compose


def generate(client, headers, kind="course_description", language="en", **extra):
    assert client.post(f"{BASE}/templates/{kind}/approve", headers=headers,
                       json={"reviewer": "Template Reviewer"}).status_code == 200
    return client.post(BASE, headers=headers, json={"document_type": kind, "course_ids": ["PY-101"],
                       "language": language, "requester": "Staff Author", **extra})


@pytest.mark.parametrize("kind", ["course_description", "course_proposal", "participant_guide"])
@pytest.mark.parametrize("language", ["en", "ar"])
def test_three_types_both_languages_real_files_and_approval(catalog_client, staff_headers, published_course, generator, kind, language):
    response = generate(catalog_client, staff_headers, kind, language)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "pending_review" and result["generation_mode"] == "GEMINI_GROUNDED_DRAFT"
    artifact_id = result["artifact_id"]
    assert result["sources"][0]["course"]["source_sha256"] == published_course[0]["source_sha256"]
    for fmt in ("docx", "pdf"):
        download = catalog_client.get(f"{BASE}/{artifact_id}/download/{fmt}", headers=staff_headers)
        assert download.status_code == 200, download.text[:300] if fmt == "docx" else download.status_code
        if fmt == "docx":
            doc = Document(BytesIO(download.content))
            assert any(result["content"]["title"] in p.text for p in doc.paragraphs)
        else:
            with pymupdf.open(stream=download.content, filetype="pdf") as pdf:
                assert len(pdf) >= 1 and all(p.get_text().strip() for p in pdf)
    approved = catalog_client.post(f"{BASE}/{artifact_id}/review", headers=staff_headers,
                                   json={"reviewer": "Staff Reviewer", "decision": "approve", "reason": "Verified all sections against source"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved" and approved.json()["approved_by"] == "Staff Reviewer"
    approved_doc = Document(BytesIO(catalog_client.get(f"{BASE}/{artifact_id}/download/docx", headers=staff_headers).content))
    assert not any("Draft for human review" in p.text for p in approved_doc.paragraphs)
    assert service.get_document(artifact_id)["history"][-1]["action"] == "approved"


def test_template_and_auth_required(catalog_client, staff_headers, published_course, generator):
    assert catalog_client.get(BASE).status_code == 401
    assert catalog_client.get(BASE, headers={"X-API-Key": "bad"}).status_code == 401
    response = catalog_client.post(BASE, headers=staff_headers, json={"document_type": "course_description",
                                   "course_ids": ["PY-101"], "requester": "Staff"})
    assert response.status_code == 409 and "template" in response.json()["detail"]


def test_withdrawn_source_cannot_generate_approve_or_download(catalog_client, staff_headers, published_course, generator):
    artifact = generate(catalog_client, staff_headers).json()
    store.withdraw_course("PY-101", "Staff")
    assert generate(catalog_client, staff_headers).status_code == 409
    artifact_id = artifact["artifact_id"]
    assert catalog_client.get(f"{BASE}/{artifact_id}/download/pdf", headers=staff_headers).status_code == 409
    assert catalog_client.post(f"{BASE}/{artifact_id}/review", headers=staff_headers,
           json={"decision": "approve", "reviewer": "Staff", "reason": "Checked source"}).status_code == 409


@pytest.mark.parametrize("decision,status", [("reject", "rejected"), ("request_revision", "revision_requested")])
def test_review_and_immutable_revisions(catalog_client, staff_headers, published_course, generator, decision, status):
    first = generate(catalog_client, staff_headers).json()
    artifact_id = first["artifact_id"]
    response = catalog_client.post(f"{BASE}/{artifact_id}/review", headers=staff_headers,
               json={"decision": decision, "reviewer": "Reviewer", "reason": "Please improve wording"})
    assert response.json()["status"] == status
    assert catalog_client.get(f"{BASE}/{artifact_id}/download/pdf", headers=staff_headers).status_code == 409
    assert catalog_client.post(f"{BASE}/{artifact_id}/review", headers=staff_headers,
           json={"decision": "approve", "reviewer": "Staff", "reason": "Now approved"}).status_code == 409
    revised = generate(catalog_client, staff_headers, revision_of=artifact_id, revision_instructions="Clarify prerequisites")
    assert revised.status_code == 201, revised.text
    assert revised.json()["version"] == 2 and revised.json()["family_id"] == first["family_id"]
    assert service.get_document(artifact_id)["status"] == status
    assert generate(catalog_client, staff_headers, revision_of=artifact_id).status_code == 409


def test_invalid_ai_citation_is_not_saved(catalog_client, staff_headers, published_course, generator, monkeypatch):
    def bad(system, payload):
        obj = generator(system, payload)
        obj["sections"][0]["source_ids"] = ["UNKNOWN"]
        return obj
    monkeypatch.setattr(service, "generate_json", bad)
    assert generate(catalog_client, staff_headers).status_code == 503
    assert service.list_documents() == []


def test_file_tampering_fails_closed(catalog_client, staff_headers, published_course, generator):
    artifact_id = generate(catalog_client, staff_headers).json()["artifact_id"]
    (store.data_dir() / "generated" / artifact_id / "document.pdf").write_bytes(b"modified")
    assert catalog_client.get(f"{BASE}/{artifact_id}/download/pdf", headers=staff_headers).status_code == 409


def test_render_failure_does_not_register_artifact(catalog_client, staff_headers, published_course, generator, monkeypatch):
    def fail(*args):
        raise OSError("Simulated disk failure")
    monkeypatch.setattr(service, "render_document", fail)
    assert generate(catalog_client, staff_headers).status_code == 503
    assert service.list_documents() == []


def test_curriculum_dependency_is_explicit(catalog_client, staff_headers, published_course):
    response = catalog_client.post(BASE, headers=staff_headers, json={"document_type": "curriculum",
                                   "course_ids": ["PY-101"], "requester": "Staff"})
    assert response.status_code == 409 and "Faris" in response.json()["detail"]


@pytest.mark.parametrize("body", [
    {"requester": " "}, {"course_ids": []}, {"course_ids": ["PY-101", "PY-101"]},
    {"language": "xx"}, {"document_type": "fake"}, {"course_ids": ["../../private"]},
])
def test_invalid_generation_requests(catalog_client, staff_headers, body):
    data = {"document_type": "course_description", "course_ids": ["PY-101"], "requester": "Staff", **body}
    assert catalog_client.post(BASE, headers=staff_headers, json=data).status_code == 422


def test_download_requires_admin_and_valid_identifier(catalog_client, staff_headers, published_course, generator):
    artifact_id = generate(catalog_client, staff_headers).json()["artifact_id"]
    assert catalog_client.get(f"{BASE}/{artifact_id}/download/pdf").status_code == 401
    assert catalog_client.get(f"{BASE}/invalid-id/download/pdf", headers=staff_headers).status_code == 404
    assert catalog_client.get(f"{BASE}/{artifact_id}/download/exe", headers=staff_headers).status_code == 404


def test_document_ui_generate_review_and_download(catalog_client, staff_headers, published_course, generator, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import requests
    def request(method, url, headers, timeout, **kwargs):
        result = catalog_client.request(method, url, headers=headers, **kwargs)
        response = requests.Response()
        response.status_code, response._content, response.url = result.status_code, result.content, url
        return response
    monkeypatch.setattr(requests, "request", request)
    page = Path(__file__).resolve().parents[1] / "frontend/pages/5_Document_Generation.py"
    app = AppTest.from_file(str(page), default_timeout=15).run()
    def element(elements, label):
        return next(e for e in elements if e.label == label)
    app.session_state["staff_key"] = staff_headers["X-API-Key"]
    app.session_state["staff_name"] = "UI Staff"
    app.run()
    element(app.button, "Approve this template version").click().run()
    assert not app.exception
    app.multiselect[0].select("PY-101")
    element(app.button, "Generate document draft").click().run()
    assert not app.exception
    assert len(service.list_documents()) == 1
    element(app.text_area, "Review reason").set_value("Checked all sources and generated files")
    element(app.checkbox, "I checked the complete document and source facts").check()
    element(app.button, "Save review decision").click().run()
    assert not app.exception
    assert service.list_documents()[0]["status"] == "approved"


def test_approval_render_failure_preserves_pending_state(catalog_client, staff_headers, published_course, generator, monkeypatch):
    artifact_id = generate(catalog_client, staff_headers).json()["artifact_id"]
    def fail(*args):
        raise OSError("Simulated approved-copy rendering failure")
    monkeypatch.setattr(service, "render_document", fail)
    response = catalog_client.post(f"{BASE}/{artifact_id}/review", headers=staff_headers,
               json={"decision": "approve", "reviewer": "Reviewer", "reason": "Verified content"})
    assert response.status_code == 503
    assert service.get_document(artifact_id)["status"] == "pending_review"
    assert len(service.get_document(artifact_id)["history"]) == 1
