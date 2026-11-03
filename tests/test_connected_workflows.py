import copy
import pytest
from backend.app.agents.curriculum import service as curriculum_service
from backend.app.marketing import service as marketing
from backend.app.documents import service as documents
from backend.app.catalog import catalog_service as catalog, approved_index
from test_curriculum_integration import valid_content


@pytest.fixture
def approved_plan(catalog_client, staff_headers, published_course, monkeypatch):
    monkeypatch.setattr(curriculum_service, "generate_curriculum", lambda *a, **k: valid_content())
    c = catalog_client.post("/api/v1/curriculum", headers=staff_headers,
                           json={"subject": "Python", "course_ids": ["PY-101"]}).json()
    cid = c["id"]
    assert catalog_client.post(f"/api/v1/curriculum/{cid}/submit", headers=staff_headers).status_code == 200
    assert catalog_client.post(f"/api/v1/curriculum/{cid}/review", headers=staff_headers,
                               json={"action": "approve", "reviewer_name": "Reviewer", "notes": "Verified the complete curriculum"}).status_code == 200
    return curriculum_service.get_curriculum(cid)


@pytest.fixture
def campaign_generator(monkeypatch):
    def generate(system, payload):
        return {"title": "Python learning campaign", "strategy": "Reach prospective Python learners and measure qualified admissions enquiries.",
                "channels": [{"channel": c, "variations": ["Explore the published Python course. Contact admissions.",
                                "Learn about Python learning outcomes. Ask admissions for current details."]} for c in payload["channels"]]}
    monkeypatch.setattr(marketing, "generate_json", generate)
    return generate


def campaign_body(plan, **extra):
    return {"course_id": "PY-101", "curriculum_id": plan["id"], "requester": "Author", "audience": "New Python learners",
            "objective": "Generate admissions enquiries", "channels": ["email", "whatsapp", "headline"], **extra}


def test_marketing_approval_export_revision(catalog_client, staff_headers, approved_plan, campaign_generator):
    assert catalog_client.get("/api/v1/marketing").status_code == 401
    r = catalog_client.post("/api/v1/marketing", headers=staff_headers, json=campaign_body(approved_plan))
    assert r.status_code == 201, r.text
    campaign = r.json(); cid = campaign["id"]
    assert campaign["status"] == "pending_review"
    assert catalog_client.get(f"/api/v1/marketing/{cid}/export", headers=staff_headers).status_code == 409
    r = catalog_client.post(f"/api/v1/marketing/{cid}/review", headers=staff_headers,
                            json={"decision": "approve", "reviewer": "Reviewer", "reason": "Verified all source facts and claims"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert catalog_client.get(f"/api/v1/marketing/{cid}/export", headers=staff_headers).status_code == 200
    edited = copy.deepcopy(campaign["content"]); edited["title"] = "Reviewed Python campaign wording"
    r = catalog_client.post("/api/v1/marketing", headers=staff_headers,
                            json=campaign_body(approved_plan, revision_of=cid, edited_content=edited, revision_instructions="Improve wording"))
    assert r.status_code == 201 and r.json()["version"] == 2
    assert marketing.get_campaign(cid)["status"] == "approved"
    assert catalog_client.post("/api/v1/marketing", headers=staff_headers,
            json=campaign_body(approved_plan, revision_of=cid, edited_content=edited)).status_code == 409


@pytest.mark.parametrize("bad", [{"channels": []}, {"audience": " "}, {"budget_egp": -1}, {"requester": " "}, {"curriculum_id": 0}])
def test_marketing_invalid_inputs(catalog_client, staff_headers, approved_plan, bad):
    assert catalog_client.post("/api/v1/marketing", headers=staff_headers, json=campaign_body(approved_plan, **bad)).status_code == 422


def test_marketing_rejects_unapproved_plan_and_invalid_ai(catalog_client, staff_headers, published_course, campaign_generator, monkeypatch):
    monkeypatch.setattr(curriculum_service, "generate_curriculum", lambda *a, **k: valid_content())
    plan = catalog_client.post("/api/v1/curriculum", headers=staff_headers, json={"subject": "Python", "course_ids": ["PY-101"]}).json()
    assert catalog_client.post("/api/v1/marketing", headers=staff_headers, json=campaign_body(plan)).status_code == 409
    catalog_client.post(f'/api/v1/curriculum/{plan["id"]}/submit', headers=staff_headers)
    catalog_client.post(f'/api/v1/curriculum/{plan["id"]}/review', headers=staff_headers,
                         json={"action": "approve", "reviewer_name": "Reviewer", "notes": "Verified all sections"})
    monkeypatch.setattr(marketing, "generate_json", lambda *a, **k: {})
    assert catalog_client.post("/api/v1/marketing", headers=staff_headers, json=campaign_body(plan)).status_code == 503
    assert marketing.list_campaigns() == []


def test_marketing_revoked_source_cannot_export(catalog_client, staff_headers, approved_plan, campaign_generator):
    r = catalog_client.post("/api/v1/marketing", headers=staff_headers, json=campaign_body(approved_plan)).json(); cid = r["id"]
    catalog_client.post(f"/api/v1/marketing/{cid}/review", headers=staff_headers,
                        json={"decision": "approve", "reviewer": "Reviewer", "reason": "Verified campaign claims"})
    catalog.withdraw_course("PY-101", "Reviewer")
    assert catalog_client.get(f"/api/v1/marketing/{cid}/export", headers=staff_headers).status_code == 409


@pytest.mark.parametrize("kind", ["curriculum", "facilitator_guide", "presentation_outline", "question_bank", "assessment_rubrics", "capstone_brief", "assessment_plan"])
def test_approved_curriculum_to_document(catalog_client, staff_headers, approved_plan, monkeypatch, kind):
    def generate(system, payload):
        assert payload["approved_curriculum"]["id"] == approved_plan["id"]
        return {"title": "Python teaching material", "sections": [{"heading": title, "text": "Proposed teaching content based on the approved Python curriculum.", "source_ids": ["S1"]}
                for title in payload["template"]["sections"]]}
    monkeypatch.setattr(documents, "generate_json", generate)
    catalog_client.post(f"/api/v1/documents/templates/{kind}/approve", headers=staff_headers, json={"reviewer": "Reviewer"})
    body = {"document_type": kind, "course_ids": ["PY-101"], "requester": "Author", "curriculum_id": approved_plan["id"]}
    r = catalog_client.post("/api/v1/documents", headers=staff_headers, json=body)
    assert r.status_code == 201, r.text
    aid = r.json()["artifact_id"]
    assert r.json()["curriculum"]["id"] == approved_plan["id"]
    assert catalog_client.get(f"/api/v1/documents/{aid}/download/pdf", headers=staff_headers).status_code == 200
    catalog.withdraw_course("PY-101", "Reviewer")
    assert catalog_client.get(f"/api/v1/documents/{aid}/download/pdf", headers=staff_headers).status_code == 409


def test_local_retrieval_existing_publications_and_revocation(published_course, monkeypatch):
    monkeypatch.setenv("REX_RETRIEVAL_BACKEND", "sqlite")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    hits = approved_index.search_approved_courses('Python " OR *', top_k=5)
    assert hits and hits[0]["course_id"] == "PY-101"
    assert "Verified Python" in hits[0]["content"]
    catalog.withdraw_course("PY-101", "Reviewer")
    assert approved_index.search_approved_courses("Python") == []


def test_local_publication_no_remote_embeddings(catalog_client, staff_headers, monkeypatch):
    from test_catalog_approval_publication import valid_approval
    monkeypatch.setenv("REX_RETRIEVAL_BACKEND", "sqlite")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    upload = catalog_client.post("/api/v1/catalog/uploads", headers=staff_headers, files={"file": ("course.md", b"## Python\nA verified teaching source.")}).json()
    catalog.approve_upload(upload["upload_id"], valid_approval())
    assert approved_index.publish_course("PY-101")["status"] == "published"
    assert approved_index.search_approved_courses("Python")[0]["course_id"] == "PY-101"
