"""Gemini embeddings + Chroma indexing with SQLite publish gate.

Do not search or expose chunks just because a Chroma metadata field says 'approved'.
Every retrieval hit is cross-checked against the active approved source checksum in SQLite.
"""
from __future__ import annotations

import hashlib
import os
from typing import Callable

from fastapi import HTTPException

from . import catalog_service as store

COLLECTION_NAME = "rex_courses_approved"
BATCH_SIZE = 8


def _model() -> str:
    return os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")


def _dimensions() -> int:
    val = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    if not 1 <= val <= 3072:
        raise ValueError("Invalid embedding dimension")
    return val


def _collection():
    import chromadb  # lazy import: offline tests may inject an in-memory fake
    client = chromadb.PersistentClient(path=str(store.data_dir() / "chroma"),
                                      settings=chromadb.config.Settings(anonymized_telemetry=False))
    try:
        col = client.get_collection(COLLECTION_NAME, embedding_function=None)
    except chromadb.errors.NotFoundError:
        col = client.create_collection(
            COLLECTION_NAME, embedding_function=None,
            metadata={"embedding_model": _model(), "embedding_dimensions": _dimensions()},
        )
    meta = col.metadata or {}
    if meta.get("embedding_model") != _model() or meta.get("embedding_dimensions") != _dimensions():
        raise RuntimeError("Approved catalog embedding model/dimension mismatch")
    return col


def _embed(texts: list[str], *, query: bool = False) -> list[list[float]]:
    """Real Gemini embeddings; no silent fallback or invented vectors."""
    from google import genai
    from google.genai import types

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=45000))
    contents = [
        types.Content(parts=[types.Part.from_text(
            text=("task: retrieval | query: " if query else "task: retrieval | document: ") + text
        )]) for text in texts
    ]
    response = client.models.embed_content(
        model=_model(), contents=contents,
        config=types.EmbedContentConfig(output_dimensionality=_dimensions()),
    )
    vectors = [x.values for x in (response.embeddings or [])]
    if len(vectors) != len(texts) or any(len(v) != _dimensions() for v in vectors):
        raise RuntimeError("Gemini embedding count or dimensions mismatch")
    return vectors


def publish_course(course_id: str, *, collection=None,
                   embedder: Callable[[list[str], bool], list[list[float]]] | None = None,
                   refresh: bool = False) -> dict:
    """Embed a reviewed upload and publish only after every upsert succeeds.

    embedder receives (texts, query=False). Arguments are injectable for offline tests.
    A failed embedding/index never changes a record into 'published'.
    """
    course = store.get_course(course_id, staff=True)
    if course["status"] not in (("published",) if refresh else ("approved", "index_failed")):
        raise HTTPException(409, "Course must be approved but not already published")
    upload_id = course["upload_id"]
    review = store.load_upload(upload_id)
    store.require_unrejected_upload(review)
    emb = embedder or (lambda texts, query=False: _embed(texts, query=query))
    try:
        col = collection if collection is not None else _collection()
        # Include a searchable, human-verified catalog record as well as raw source text.
        # These facts come from the staff approval form, never from generated text.
        fields = [f"Approved course: {course['title']}", f"Course ID: {course_id}",
                  f"Description: {course['description']}"]
        for key, label in (("level", "Level"), ("training_format", "Training format"),
                           ("price_egp", "Price (EGP)"), ("duration_hours", "Duration (hours)"),
                           ("department", "Department")):
            if course.get(key) is not None:
                fields.append(f"{label}: {course[key]}")
        for key, label in (("instructor_name", "Instructor"), ("instructor_bio", "Instructor experience"),
                           ("schedule", "Schedule"), ("offers", "Offers"), ("target_audience", "Target audience")):
            if course.get(key):
                fields.append(f"{label}: {course[key]}")
        for key in ("career_opportunities", "admission_requirements"):
            if course.get(key):
                fields.append(key.replace("_", " ").title() + ": " + "; ".join(course[key]))
        for faq in course.get("faqs", []):
            fields.append(f"FAQ: {faq['question']} Answer: {faq['answer']}")
        if course.get("data_origin") == "synthetic_demo":
            fields.insert(0, "REX_SYNTHETIC_DEMO: fictional course information for TA demonstration only.")
        for key, label in (("prerequisites", "Prerequisites"), ("learning_outcomes", "Learning outcomes")):
            if course.get(key):
                fields.append(f"{label}: " + "; ".join(course[key]))
        metadata_chunk = {
            "chunk_id": "verified-metadata-v1",
            "text": "\n".join(fields),
            "metadata": {"section": "Staff-approved catalog record"},
        }
        # Uploads may contain multiple courses or unreviewed statements. Only the
        # explicitly verified catalog fields are authorized for student retrieval.
        chunks = [metadata_chunk]
        ids = [hashlib.sha256(f"{course_id}|{upload_id}|{course['reviewed_at']}|{c['chunk_id']}".encode()).hexdigest() for c in chunks]
        for offset in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[offset:offset + BATCH_SIZE]
            texts = [c["text"] for c in batch]
            vectors = emb(texts, False)
            if len(vectors) != len(batch) or any(len(v) != _dimensions() for v in vectors):
                raise RuntimeError("Embedding verification failed")
            metadatas = []
            for c in batch:
                meta = c["metadata"]
                md = {
                    "index_kind": "verified_catalog_v2",
                    "course_id": course_id,
                    "course_title": course["title"],
                    "upload_id": upload_id,
                    "source_sha256": upload_id,
                    "approval_revision": course["reviewed_at"],
                    "source_file": review["filename"],
                    "section": meta.get("section", "Document"),
                    "approval_status": "approved",
                }
                if isinstance(meta.get("page_number"), int):
                    md["page_number"] = meta["page_number"]
                metadatas.append(md)
            col.upsert(ids=ids[offset:offset + BATCH_SIZE], documents=texts,
                       embeddings=vectors, metadatas=metadatas)
        # Confirm every indexed chunk was saved before publishing.
        persisted = col.get(ids=ids, include=[])
        if set(persisted["ids"]) != set(ids):
            raise RuntimeError("Chroma did not persist all course chunks")
        store.set_published(course_id, upload_id, expected_reviewed_at=course["reviewed_at"], refresh=refresh)
        return {"course_id": course_id, "status": "published", "indexed_chunks": len(ids),
                "source_sha256": upload_id}
    except HTTPException:
        raise
    except Exception as exc:
        store.mark_index_failed(course_id, upload_id, type(exc).__name__)
        # Avoid exposing API credentials, source text or remote service payloads.
        raise HTTPException(503, f"RAG publication failed ({type(exc).__name__}); approval retained for retry") from exc


def search_approved_courses(query: str, top_k: int = 5, *, collection=None,
                            embedder: Callable[[list[str], bool], list[list[float]]] | None = None) -> list[dict]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query cannot be empty")
    if not 1 <= top_k <= 30:
        raise ValueError("top_k must be 1-30")
    if not store.list_courses():
        return []
    col = collection if collection is not None else _collection()
    if not col.count():
        return []
    emb = embedder or (lambda texts, query=False: _embed(texts, query=query))
    vector = emb([query.strip()], True)
    if len(vector) != 1 or len(vector[0]) != _dimensions():
        raise RuntimeError("Query embedding mismatch")
    results = col.query(query_embeddings=vector, n_results=min(col.count(), max(top_k * 5, 20)),
                        where={"index_kind": "verified_catalog_v2"},
                        include=["documents", "metadatas", "distances"])
    matches = []
    for id_, text, meta, distance in zip(results["ids"][0], results["documents"][0],
                                         results["metadatas"][0], results["distances"][0]):
        if not meta.get("approval_revision") or not store.is_published(
                meta.get("course_id", ""), meta.get("source_sha256", ""), meta["approval_revision"]):
            continue
        matches.append({
            "chunk_id": id_, "course_id": meta["course_id"], "course_title": meta["course_title"],
            "source_file": meta["source_file"], "section": meta["section"],
            "page_number": meta.get("page_number"), "source_sha256": meta["source_sha256"],
            "approval_revision": meta["approval_revision"],
            "distance": float(distance), "content": text,
        })
        if len(matches) >= top_k:
            break
    return matches


def remove_course_vectors(course_id: str, *, collection=None) -> bool:
    """Best-effort cleanup. SQL withdrawal already prevents serving old vectors."""
    try:
        col = collection if collection is not None else _collection()
        col.delete(where={"course_id": course_id.upper()})
        return True
    except Exception:
        return False
