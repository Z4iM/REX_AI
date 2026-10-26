"""Offline safety/regression tests. Never call paid Gemini APIs or real ChromaDB."""
import hashlib
import json

import pytest
from fastapi import HTTPException

from backend.app.catalog import catalog_service as store
from backend.app.catalog import approved_index


class FakeCollection:
    def __init__(self):
        self.saved = {}
        self.fail_after_first = False
        self.calls = 0

    def upsert(self, ids, documents, embeddings, metadatas):
        self.calls += 1
        if self.fail_after_first:
            raise RuntimeError("temporary Chroma outage")
        for k, text, meta in zip(ids, documents, metadatas):
            self.saved[k] = (text, meta)

    def get(self, ids, include=None):
        return {"ids": [k for k in ids if k in self.saved]}

    def count(self):
        return len(self.saved)

    def query(self, query_embeddings, n_results, where, include):
        available = [(k, *v) for k, v in self.saved.items() if v[1].get("index_kind") == where["index_kind"]]
        available = available[:n_results]
        return {"ids": [[r[0] for r in available]], "documents": [[r[1] for r in available]],
                "metadatas": [[r[2] for r in available]], "distances": [[0.2] * len(available)]}

    def delete(self, where):
        for k, (text, meta) in list(self.saved.items()):
            if meta["course_id"] == where["course_id"]:
                del self.saved[k]


def fake_embed(texts, query=False):
    return [[0.5] * 768 for _ in texts]


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("REX_CATALOG_DATA_DIR", str(tmp_path / "catalog"))
    content = b"course approved source content"
    digest = hashlib.sha256(content).hexdigest()
    folder = tmp_path / "catalog" / "uploads" / digest
    folder.mkdir(parents=True)
    (folder / "source.md").write_bytes(content)
    review = {
        "upload_id": digest, "source_sha256": digest, "file_type": "md", "filename": "course.md",
        "review_status": "pending_review", "missing_pages": [], "extraction_warnings": [],
        "chunks": [{"chunk_id": "sample1", "text": "Course: Verified Python\nPrerequisites: none",
                    "metadata": {"section": "Prerequisites", "page_number": 2}}],
    }
    (folder / "review.json").write_text(json.dumps(review), encoding="utf-8")
    return digest, folder, review


def valid_approval(**kwargs):
    data = {
        "course_id": "PY-101", "title": "Verified Python", "description": "Verified course description.",
        "level": "Beginner", "training_format": "Online", "price_egp": 2500,
        "duration_hours": 20, "prerequisites": ["Basic computer literacy"],
        "learning_outcomes": ["Use Python"], "reviewer": "Course Admin",
    }
    data.update(kwargs)
    return store.CourseApproval(**data)


def test_unapproved_upload_never_becomes_public(workspace):
    digest, *_ = workspace
    assert store.list_courses() == []
    with pytest.raises(HTTPException) as exc:
        store.get_course("PY-101")
    assert exc.value.status_code == 404
    assert store.list_matching_courses() == []


def test_approved_is_not_published_before_embeddings(workspace):
    digest, *_ = workspace
    r = store.approve_upload(digest, valid_approval())
    assert r["status"] == "approved"
    assert store.list_courses() == []
    assert store.list_matching_courses() == []
    assert store.list_courses(staff=True)[0]["status"] == "approved"


def test_publish_is_gated_and_search_has_citations(workspace):
    digest, *_ = workspace
    store.approve_upload(digest, valid_approval())
    col = FakeCollection()
    result = approved_index.publish_course("PY-101", collection=col, embedder=fake_embed)
    assert result["status"] == "published" and result["indexed_chunks"] == 1
    matches = approved_index.search_approved_courses("Python prerequisites", collection=col, embedder=fake_embed)
    assert len(matches) == 1
    assert matches[0]["source_sha256"] == digest
    assert matches[0]["section"] == "Staff-approved catalog record"
    assert matches[0]["page_number"] is None
    assert "Basic computer literacy" in matches[0]["content"]
    assert "Prerequisites: none" not in matches[0]["content"]
    assert matches[0]["course_id"] == "PY-101"
    assert store.list_matching_courses()[0]["price"] == "2500 EGP"
    assert len(store.course_history("PY-101")) == 2


def test_index_failure_does_not_publish_and_allows_retry(workspace):
    digest, *_ = workspace
    store.approve_upload(digest, valid_approval())
    col = FakeCollection()
    col.fail_after_first = True
    with pytest.raises(HTTPException) as exc:
        approved_index.publish_course("PY-101", collection=col, embedder=fake_embed)
    assert exc.value.status_code == 503
    assert store.get_course("PY-101", staff=True)["status"] == "index_failed"
    assert store.list_courses() == []
    col.fail_after_first = False
    assert approved_index.publish_course("PY-101", collection=col, embedder=fake_embed)["status"] == "published"


def test_withdraw_immediately_hides_even_if_vectors_still_exist(workspace):
    digest, *_ = workspace
    store.approve_upload(digest, valid_approval())
    col = FakeCollection()
    approved_index.publish_course("PY-101", collection=col, embedder=fake_embed)
    store.withdraw_course("PY-101", "Staff")
    # Deliberately skip vector deletion: DB revocation alone must be sufficient.
    assert col.count() == 1
    assert approved_index.search_approved_courses("Python", collection=col, embedder=fake_embed) == []
    assert store.list_courses() == []


def test_block_incomplete_and_unacknowledged_warnings(workspace):
    digest, folder, review = workspace
    review["missing_pages"] = [3]
    review["review_status"] = "blocked_incomplete"
    (folder / "review.json").write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        store.approve_upload(digest, valid_approval())
    assert exc.value.status_code == 409
    review["missing_pages"] = []
    review["review_status"] = "pending_review"
    review["extraction_warnings"] = ["OCR used; verify it"]
    (folder / "review.json").write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(HTTPException):
        store.approve_upload(digest, valid_approval())
    assert store.approve_upload(digest, valid_approval(acknowledge_extraction_warnings=True))["status"] == "approved"


def test_original_document_checksum_must_not_change(workspace):
    digest, folder, _ = workspace
    (folder / "source.md").write_text("Document was modified after upload!")
    with pytest.raises(HTTPException) as exc:
        store.approve_upload(digest, valid_approval())
    assert exc.value.status_code == 409


def test_course_id_collision_requires_prior_withdrawal(workspace, tmp_path):
    digest, _, review = workspace
    store.approve_upload(digest, valid_approval())
    another_source = b"another course source document"
    second = hashlib.sha256(another_source).hexdigest()
    folder = tmp_path / "catalog" / "uploads" / second
    folder.mkdir(parents=True)
    (folder / "source.md").write_bytes(another_source)
    new_manifest = {**review, "upload_id": second, "source_sha256": second}
    (folder / "review.json").write_text(json.dumps(new_manifest), encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        store.approve_upload(second, valid_approval())
    assert exc.value.status_code == 409
    store.withdraw_course("PY-101", "Staff")
    new = store.approve_upload(second, valid_approval(title="Updated Python"))
    assert new["status"] == "approved" and new["title"] == "Updated Python"
    assert store.list_courses() == []


def test_filter_stale_vectors_when_new_version_published(workspace, tmp_path):
    digest, _, review = workspace
    store.approve_upload(digest, valid_approval())
    col = FakeCollection()
    approved_index.publish_course("PY-101", collection=col, embedder=fake_embed)
    store.withdraw_course("PY-101", "Staff")
    another_source = b"an updated source version"
    second = hashlib.sha256(another_source).hexdigest()
    folder = tmp_path / "catalog" / "uploads" / second
    folder.mkdir(parents=True)
    (folder / "source.md").write_bytes(another_source)
    (folder / "review.json").write_text(json.dumps({**review, "upload_id": second,
                                    "source_sha256": second, "filename": "updated.md"}), encoding="utf-8")
    store.approve_upload(second, valid_approval(title="Updated Python"))
    approved_index.publish_course("PY-101", collection=col, embedder=fake_embed)
    result = approved_index.search_approved_courses("Python", top_k=10, collection=col, embedder=fake_embed)
    assert len(result) == 1 and all(r["source_sha256"] == second for r in result)


def test_validation_rejects_invalid_course_id():
    with pytest.raises(ValueError):
        valid_approval(course_id="../../../etc")
