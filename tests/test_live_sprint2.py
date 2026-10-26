"""Opt-in provider smoke check. Uses temporary synthetic test-only storage."""
import os
import pytest


@pytest.mark.skipif(os.getenv("REX_RUN_LIVE_TESTS") != "1", reason="Explicitly opt in to live Gemini quota usage")
def test_live_publication_retrieval_answer_and_document(published_course):
    from backend.app.catalog import approved_index, approved_answer
    from backend.app.documents import service
    from backend.app.documents.models import GenerationRequest
    # The normal fixture uses a fake index; refresh here creates a REAL isolated
    # Chroma collection using actual Gemini embeddings. No academy DB is touched.
    stage = "publication"
    failure = None
    try:
        result = approved_index.publish_course("PY-101", refresh=True)
        assert result["status"] == "published"
        stage = "grounded_answer"
        answer = approved_answer.answer_approved_question("What is this course called and what is its price?")
        assert answer["sources"] and answer["mode"] == "APPROVED_CATALOG"
        stage = "document_generation"
        service.approve_template("course_description", "Live Test Reviewer")
        artifact = service.generate_document(GenerationRequest(document_type="course_description", course_ids=["PY-101"],
                                                               requester="Live Test Author"))
        assert artifact["status"] == "pending_review"
        assert service.file_path(artifact["artifact_id"], "pdf").is_file()
    except Exception as exc:
        # Do not dump remote payloads, URLs, provider keys or credential-bearing tracebacks.
        failure = f"Live workflow failed at {stage}: {type(exc).__name__}, code={getattr(exc, 'code', None)}; detail={getattr(exc, 'detail', 'provider unavailable') if type(exc).__name__ == 'HTTPException' else 'provider unavailable'}"
    if failure:
        pytest.fail(failure, pytrace=False)


@pytest.mark.skipif(os.getenv("REX_RUN_LIVE_TESTS") != "1", reason="Explicitly opt in to live Gemini quota usage")
def test_live_recommendation_extraction_and_faris_summary(published_course, catalog_client, staff_headers):
    from backend.app.catalog import approved_index, metadata_extraction, catalog_service as store
    from backend.app.assistant.personalized_recommendation import recommend_courses
    from backend.app.agents.rfp.rfp_agent import Tender, summarize_tender
    from test_metadata_extraction import CONTENT
    stage = "publication"
    failure = None
    try:
        approved_index.publish_course("PY-101", refresh=True)
        stage = "recommendation"
        result = recommend_courses({"skill_level": "Beginner", "training_format": "Online", "budget": "3000 EGP",
                                    "background": "Basic computer literacy", "career_goal": "Learn Python"},
                                   "I want to learn Python", "en")
        assert result["status"] == "candidates_found" and result["sources"]
        stage = "metadata_extraction"
        response = catalog_client.post("/api/v1/catalog/uploads", headers=staff_headers,
                                       files={"file": ("live-extraction.md", CONTENT)})
        upload_id = response.json()["upload_id"]
        extracted = metadata_extraction.extract_metadata(upload_id,
            metadata_extraction.ExtractionRequest(reviewer="Live TA Reviewer", method="gemini"))
        assert any(c["fields"].get("course_id") == "PY-101" for c in extracted["candidates"])
        assert store.load_upload(upload_id)["approval_status"] == "unapproved"
        stage = "faris_rfp_summary"
        summary = summarize_tender(Tender(title="REX_SYNTHETIC_DEMO Python training", issuer="Fictional TA organisation",
            country="Egypt", category="IT training", description="Fictional training for ten staff covering Python basics.",
            eligibility="Registered training provider. This is a fictional test and no actual bid exists."))
        assert isinstance(summary["summary"], str) and summary["summary"].strip()
    except Exception as exc:
        failure = f"Live workflow failed at {stage}: {type(exc).__name__}, code={getattr(exc, 'code', None)}; detail={getattr(exc, 'detail', 'provider unavailable') if type(exc).__name__ == 'HTTPException' else 'provider unavailable'}"
    if failure:
        pytest.fail(failure, pytrace=False)
