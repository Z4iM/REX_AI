"""Explicit opt-in real provider verification; all application state is temporary."""
import os
import pytest
from dotenv import dotenv_values
from pathlib import Path

pytestmark = pytest.mark.skipif(os.getenv("REX_RUN_LIVE_TESTS") != "1", reason="Live AI checks are explicitly opt-in")


def test_live_learner_guidance_and_course_followup(catalog_client, published_course, monkeypatch):
    values = dotenv_values(Path(__file__).resolve().parents[1] / '.env')
    if not values.get('GROQ_API_KEY'):
        pytest.skip('Configure the local provider key before live verification')
    monkeypatch.setenv('GROQ_API_KEY', values['GROQ_API_KEY'])
    monkeypatch.setenv('REX_AI_PROVIDER', 'groq')
    monkeypatch.setenv('REX_RETRIEVAL_BACKEND', 'sqlite')
    hello = catalog_client.post('/api/v1/chat',json={'message':'hello'}).json()
    assert hello['mode'] == 'LEARNER_GUIDANCE' and not hello['sources']
    advice = catalog_client.post('/api/v1/chat',json={'message':'How can I build a realistic study habit alongside a full-time job?'}).json()
    assert advice['mode'] == 'LEARNER_GUIDANCE' and len(advice['answer']) > 40
    result = catalog_client.post('/api/v1/chat',json={
        'message':'How much does it cost?',
        'history':[{'role':'user','content':'I am asking about the published Verified Python course, PY-101.'}]}).json()
    assert result['mode'] == 'APPROVED_CATALOG' and result['sources'], result
    assert all(s['course_id'] == 'PY-101' for s in result['sources'])


def test_live_groq_connected_workflow(catalog_client, staff_headers, published_course, monkeypatch):
    values = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    if not values.get("GROQ_API_KEY"):
        pytest.skip("Save GROQ_API_KEY locally before live verification")
    monkeypatch.setenv("GROQ_API_KEY", values["GROQ_API_KEY"])
    monkeypatch.setenv("REX_AI_PROVIDER", "groq")
    monkeypatch.setenv("REX_RETRIEVAL_BACKEND", "sqlite")
    r = catalog_client.post("/api/v1/curriculum", headers=staff_headers,
        json={"subject": "Python programming foundations", "course_ids": ["PY-101"], "duration_hours": 20,
              "skill_level": "Beginner", "additional_requirements": "Use two modules of 10 hours each. Keep the plan concise, one exercise, one assessment weighted 100 percent and one capstone."})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert catalog_client.post(f"/api/v1/curriculum/{cid}/submit", headers=staff_headers).status_code == 200
    assert catalog_client.post(f"/api/v1/curriculum/{cid}/review", headers=staff_headers,
        json={"action": "approve", "reviewer_name": "Isolated integration reviewer", "notes": "Synthetic test plan verified for connected workflow"}).status_code == 200
    assert catalog_client.get(f"/api/v1/curriculum/{cid}/pdf", headers=staff_headers).status_code == 200
    r = catalog_client.post("/api/v1/marketing", headers=staff_headers,
        json={"course_id": "PY-101", "curriculum_id": cid, "requester": "Isolated integration author",
              "audience": "New learners interested in Python", "objective": "Invite enquiries about verified learning outcomes",
              "channels": ["social_caption", "facebook_instagram", "linkedin", "email", "whatsapp", "headline", "cta"], "language": "ar"})
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert catalog_client.post(f"/api/v1/marketing/{mid}/review", headers=staff_headers,
        json={"decision": "approve", "reviewer": "Isolated integration reviewer", "reason": "Verified against synthetic source records"}).status_code == 200
    assert catalog_client.get(f"/api/v1/marketing/{mid}/export", headers=staff_headers).status_code == 200
    assert catalog_client.post("/api/v1/documents/templates/curriculum/approve", headers=staff_headers,
        json={"reviewer": "Isolated integration reviewer"}).status_code == 200
    r = catalog_client.post("/api/v1/documents", headers=staff_headers,
        json={"document_type": "curriculum", "course_ids": ["PY-101"], "curriculum_id": cid,
              "language": "ar", "requester": "Isolated integration author"})
    assert r.status_code == 201, r.text
    aid = r.json()["artifact_id"]
    assert catalog_client.get(f"/api/v1/documents/{aid}/download/pdf", headers=staff_headers).status_code == 200
    answer = catalog_client.post("/api/v1/chat", json={"message": "What does the verified Python course teach?"})
    assert answer.status_code == 200, answer.text

    from backend.app.assistant.personalized_recommendation import recommend_courses
    recommendation = recommend_courses({"background": "New learner", "skill_level": "Beginner", "career_goal": "Learn Python",
                                         "budget": "3000 EGP", "training_format": "Online"}, "Learn Python", language="ar")
    assert recommendation["status"] == "candidates_found" and recommendation["sources"]
    from backend.app.agents.rfp.rfp_agent import summarize_tender
    from backend.app.agents.rfp.tests.test_rfp_agent import make
    summary = summarize_tender(make())
    assert isinstance(summary["summary"], str) and summary["summary"].strip()
