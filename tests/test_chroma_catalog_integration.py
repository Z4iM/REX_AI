"""Real isolated persistent Chroma/SQLite integration, with offline embeddings."""
import pytest
pytest.importorskip("chromadb", reason="Optional vector backend: install requirements-vector.txt to run this integration")
from backend.app.catalog import approved_index, catalog_service as store
from test_catalog_approval_publication import fake_embed


def test_real_chroma_persistence_retrieval_and_revocation(published_course):
    course, _ = published_course
    result = approved_index.publish_course("PY-101", embedder=fake_embed, refresh=True)
    assert result["indexed_chunks"] == 1
    # Resolve a new collection client through the real persistent-storage path.
    matches = approved_index.search_approved_courses("Python", embedder=fake_embed)
    assert matches[0]["course_id"] == "PY-101"
    assert matches[0]["approval_revision"] == course["reviewed_at"]
    assert (store.data_dir() / "chroma" / "chroma.sqlite3").is_file()
    store.withdraw_course("PY-101", "Integration Reviewer")
    assert approved_index.search_approved_courses("Python", embedder=fake_embed) == []
