"""Student paths must be empty or grounded in the exact published catalog version."""
from types import SimpleNamespace
import pytest
from backend.app.catalog import approved_answer, approved_index, catalog_service as store
from backend.app.assistant import personalized_recommendation as recommendations
from backend.app.assistant.course_matcher import match_courses
from backend.app.assistant.session_store import get_session
from test_catalog_approval_publication import fake_embed

PROFILE = {"skill_level": "Beginner", "training_format": "Online", "budget": "4000 EGP"}


def test_empty_student_paths_do_not_call_gemini(catalog_client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("An empty catalog must not call an external AI service")
    monkeypatch.setattr(approved_answer.genai, "Client", forbidden)
    assert match_courses(PROFILE) == []
    result = catalog_client.post("/api/v1/chat", json={"message": "Python courses?"})
    assert result.status_code == 200
    assert result.json()["mode"] == "APPROVED_CATALOG" and result.json()["sources"] == []
    assert recommendations.recommend_courses(PROFILE, "Python")["eligible_courses"] == []


def test_matching_and_retrieval_revoke_on_withdrawal(published_course):
    course, col = published_course
    assert match_courses(PROFILE)[0]["course_id"] == "PY-101"
    assert approved_index.search_approved_courses("Python", collection=col, embedder=fake_embed)
    store.withdraw_course("PY-101", "Reviewer")
    assert match_courses(PROFILE) == []
    assert approved_index.search_approved_courses("Python", collection=col, embedder=fake_embed) == []


@pytest.mark.parametrize("invalid", [False, True])
def test_grounded_answers_validate_citations(published_course, monkeypatch, invalid):
    course, col = published_course
    monkeypatch.setattr(approved_answer, "search_approved_courses", lambda *a, **k:
                        approved_index.search_approved_courses("Python", collection=col, embedder=fake_embed))
    fake = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(
        text='{"answer":"Verified Python is available.","source_ids":["' + ("invented" if invalid else "S1") + '"]}')))
    monkeypatch.setattr(approved_answer.genai, "Client", lambda **k: fake)
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test")
    if invalid:
        with pytest.raises(ValueError, match="unknown evidence"):
            approved_answer.answer_approved_question("Python?")
    else:
        assert approved_answer.answer_approved_question("Python?")["sources"][0]["file"] == "fixture.md"


def test_legacy_raw_chunks_are_never_retrieved(published_course):
    course, col = published_course
    col.saved["legacy"] = ("Unreviewed secret course", {"index_kind": "approved_course", "course_id": "PY-101",
                           "source_sha256": course["source_sha256"]})
    result = approved_index.search_approved_courses("course", collection=col, embedder=fake_embed)
    assert len(result) == 1 and "Unreviewed" not in result[0]["content"]
    approved_index.publish_course("PY-101", collection=col, embedder=fake_embed, refresh=True)
    assert store.get_course("PY-101")["status"] == "published"
    assert store.course_history("PY-101")[-1]["action"] == "index_refreshed"


def test_personalized_recommendation_is_grounded(published_course, monkeypatch):
    course, col = published_course
    monkeypatch.setattr(recommendations, "search_approved_courses", lambda *a, **k:
                        approved_index.search_approved_courses("Python", collection=col, embedder=fake_embed))
    fake = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(
        text='{"answer":"The course passes the checked constraints; verify prerequisites.","source_ids":["S1"]}')))
    monkeypatch.setattr(recommendations.genai, "Client", lambda **kw: fake)
    result = recommendations.recommend_courses(PROFILE, "Python")
    assert result["status"] == "candidates_found" and result["mode"] == "APPROVED_CATALOG"
    assert result["sources"][0]["source_sha256"] == course["source_sha256"]


def test_session_survives_new_client_and_can_be_deleted(catalog_client):
    response = catalog_client.post("/api/v1/qualification", json={"message": "Learn Python"})
    token = response.json()["session_id"]
    assert get_session(token).initial_request == "Learn Python"
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as another_process_view:
        result = another_process_view.post("/api/v1/qualification", json={"session_id": token, "message": "Graduate"})
        assert result.status_code == 200 and result.json()["profile"]["background"] == "Graduate"
    assert catalog_client.delete(f"/api/v1/qualification/{token}").status_code == 204
    assert get_session(token) is None


def test_expired_session_unavailable(catalog_client):
    token = catalog_client.post("/api/v1/qualification", json={"message": "Learn Python"}).json()["session_id"]
    with store.catalog_transaction() as con:
        con.execute("UPDATE qualification_sessions SET expires_at=0")
    assert get_session(token) is None


def test_stale_vectors_after_same_upload_reapproval_are_hidden(published_course):
    course, col = published_course
    from test_catalog_approval_publication import valid_approval
    store.withdraw_course("PY-101", "Reviewer")
    store.approve_upload(course["upload_id"], valid_approval(title="Changed course title"))
    approved_index.publish_course("PY-101", collection=col, embedder=fake_embed)
    results = approved_index.search_approved_courses("Python", collection=col, embedder=fake_embed)
    assert len(results) == 1 and results[0]["course_title"] == "Changed course title"


def test_withdrawal_during_answer_generation_discards_response(published_course, monkeypatch):
    course, col = published_course
    monkeypatch.setattr(approved_answer, "search_approved_courses", lambda *a, **k:
                        approved_index.search_approved_courses("Python", collection=col, embedder=fake_embed))
    def generate(**kwargs):
        store.withdraw_course("PY-101", "Reviewer")
        return SimpleNamespace(text='{"answer":"A now stale answer","source_ids":["S1"]}')
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test")
    monkeypatch.setattr(approved_answer.genai, "Client", lambda **kw: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    with pytest.raises(RuntimeError, match="Catalog changed"):
        approved_answer.answer_approved_question("Python?")
