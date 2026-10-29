import copy
import pytest
import pymupdf
from backend.app.agents.curriculum import service

BASE = "/api/v1/curriculum"


def valid_content():
    return {"title": "Python learning curriculum", "description": "A proposed practical Python learning plan.",
            "objectives": ["Apply Python"], "prerequisites": [], "learning_outcomes": ["Use Python"],
            "modules": [{"module_number": 1, "title": "Python basics", "description": "Learn Python through practice",
                         "topics": ["Variables"], "duration_hours": 20, "learning_outcomes": ["Use Python"], "activities": ["Practice variables"]}],
            "training_hours": 20, "practical_exercises": [{"title": "Variable lab", "description": "Practice assigning variables", "module": "1", "type": "Lab", "duration_hours": 2}],
            "assessments": [{"title": "Python assignment", "type": "Assignment", "weight_percent": 100, "description": "Assess Python skills", "module": "1"}],
            "capstone_project": {"title": "Python project", "description": "Build a Python application", "deliverables": ["Source code"], "evaluation_criteria": ["Correctness"], "duration_hours": 2}}


@pytest.fixture
def curriculum(catalog_client, staff_headers, published_course, monkeypatch):
    monkeypatch.setattr(service, "generate_curriculum", lambda *a, **k: valid_content())
    r = catalog_client.post(BASE, headers=staff_headers, json={"subject": "Python", "course_ids": ["PY-101"], "duration_hours": 20})
    assert r.status_code == 201, r.text
    return r.json()


def test_curriculum_auth_and_validations(catalog_client, staff_headers):
    assert catalog_client.get(BASE).status_code == 401
    assert catalog_client.get(BASE, headers={"X-API-Key": "bad"}).status_code == 401
    for extra in ({"duration_hours": -1}, {"subject": "  "}, {"course_ids": []}):
        body = {"subject": "Python", "course_ids": ["PY-101"], **extra}
        assert catalog_client.post(BASE, headers=staff_headers, json=body).status_code == 422


def test_malformed_ai_is_not_stored(catalog_client, staff_headers, published_course, monkeypatch):
    monkeypatch.setattr(service, "generate_curriculum", lambda *a, **k: {})
    assert catalog_client.post(BASE, headers=staff_headers, json={"subject": "Python", "course_ids": ["PY-101"]}).status_code == 503
    assert catalog_client.get(BASE, headers=staff_headers).json()["items"] == []


def test_approval_immutable_and_revision(catalog_client, staff_headers, curriculum):
    cid = curriculum["id"]
    assert catalog_client.post(f"{BASE}/{cid}/submit", headers=staff_headers).status_code == 200
    assert catalog_client.post(f"{BASE}/{cid}/review", headers=staff_headers,
                               json={"action": "approve", "reviewer_name": "  ", "notes": "Checked"}).status_code == 422
    r = catalog_client.post(f"{BASE}/{cid}/review", headers=staff_headers,
                            json={"action": "approve", "reviewer_name": "Reviewer", "notes": "Checked source and teaching plan"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    fw = catalog_client.get(f"{BASE}/frameworks", headers=staff_headers).json()["items"][0]
    r = catalog_client.post(f"{BASE}/{cid}/alignment", headers=staff_headers, json={"framework_id": fw["id"]})
    assert r.status_code == 409
    content = valid_content(); content["title"] = "Revised Python learning curriculum"
    revised = catalog_client.post(f"{BASE}/{cid}/revise", headers=staff_headers,
                                  json={"content": content, "reviewer_name": "Reviewer", "reason": "Improve title"})
    assert revised.status_code == 201, revised.text
    assert revised.json()["id"] != cid and revised.json()["status"] == "draft"
    assert service.get_curriculum(cid)["status"] == "approved"


def test_revision_requested_requires_new_version(catalog_client, staff_headers, curriculum):
    cid = curriculum["id"]
    catalog_client.post(f"{BASE}/{cid}/submit", headers=staff_headers)
    catalog_client.post(f"{BASE}/{cid}/review", headers=staff_headers,
                         json={"action": "request_revision", "reviewer_name": "Reviewer", "notes": "Improve the plan"})
    assert catalog_client.post(f"{BASE}/{cid}/submit", headers=staff_headers).status_code == 422
    assert catalog_client.get(f"{BASE}/{cid}/pdf", headers=staff_headers).status_code == 409


def test_source_revocation_blocks_approval_and_export(catalog_client, staff_headers, curriculum):
    from backend.app.catalog import catalog_service as store
    cid = curriculum["id"]
    store.withdraw_course("PY-101", "Reviewer")
    assert catalog_client.post(f"{BASE}/{cid}/submit", headers=staff_headers).status_code == 409
    assert catalog_client.get(f"{BASE}/{cid}/pdf", headers=staff_headers).status_code == 409


def test_arabic_pdf_and_demo_storage(catalog_client, staff_headers, curriculum, monkeypatch, tmp_path):
    from backend.app import runtime
    from backend.app.agents.curriculum.pdf_generator import generate_curriculum_pdf
    c = copy.deepcopy(curriculum); c.update(title="مقدمة البرمجة", language="Arabic")
    with pymupdf.open(stream=generate_curriculum_pdf(c), filetype="pdf") as pdf:
        assert len(pdf) and any((0x600 <= ord(ch) <= 0x6ff or 0xfb50 <= ord(ch) <= 0xfeff) for ch in "".join(p.get_text() for p in pdf))
    academy = runtime.curriculum_dir()
    monkeypatch.setenv("REX_APP_MODE", "demo"); monkeypatch.setenv("REX_DEMO_DATA_DIR", str(tmp_path / "demo"))
    assert runtime.curriculum_dir() != academy
    assert service.list_curricula() == []


def test_assessment_and_hours_consistency():
    from backend.app.agents.curriculum.models import CurriculumContent
    from pydantic import ValidationError
    for key in ("assessments", "modules"):
        c = valid_content()
        c[key][0]["weight_percent" if key == "assessments" else "duration_hours"] = 5
        with pytest.raises(ValidationError):
            CurriculumContent.model_validate(c)


def test_verified_alignment_and_concurrent_review(catalog_client, staff_headers, curriculum, monkeypatch):
    fw = catalog_client.get(f"{BASE}/frameworks", headers=staff_headers).json()["items"][0]
    fid, cid = fw["id"], curriculum["id"]
    assert catalog_client.post(f"{BASE}/{cid}/alignment", headers=staff_headers, json={"framework_id": fid}).status_code == 409
    payload = {"reviewer_name": "Framework Reviewer", "source_url": "https://example.test/verified-standard",
               "source_version": "Test edition 2026", "source_excerpt": "Synthetic test framework requiring programming practice.",
               "competencies": ["Programming practice"]}
    assert catalog_client.post(f"{BASE}/frameworks/{fid}/approve", headers=staff_headers, json=payload).status_code == 200
    def align(*a, **k):
        return {"framework_name": fw["name"], "overall_alignment_score": 80, "summary": "Proposed practice alignment",
                "competency_alignment": [{"competency": "Programming practice", "status": "partially_aligned",
                    "curriculum_coverage": "Python module", "gaps": "Further practice", "recommendation": "Add practice"}],
                "missing_topics": [], "strengths": ["Programming lab"], "recommendations": ["More practice"],
                "disclaimer": "Accredited!"}
    monkeypatch.setattr(service, "compare_accreditation", align)
    r = catalog_client.post(f"{BASE}/{cid}/alignment", headers=staff_headers, json={"framework_id": fid})
    assert r.status_code == 200, r.text
    assert "does not confer" in r.json()["alignment"]["disclaimer"]
    assert r.json()["alignment"]["framework_snapshot"]["reviewed_by"] == "Framework Reviewer"
    def concurrent(*a, **k):
        service.submit_for_review(cid)
        return align()
    monkeypatch.setattr(service, "compare_accreditation", concurrent)
    assert catalog_client.post(f"{BASE}/{cid}/alignment", headers=staff_headers, json={"framework_id": fid}).status_code == 409
    assert service.get_curriculum(cid)["status"] == "pending_review"
