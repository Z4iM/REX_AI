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
    if os.getenv("REX_RETRIEVAL_BACKEND", "gemini") == "sqlite" and collection is None and embedder is None:
        return _publish_local(course, refresh=refresh)
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
            fields.insert(0, "fictional course information for demonstration only.")
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
    if os.getenv("REX_RETRIEVAL_BACKEND", "gemini") == "sqlite" and collection is None and embedder is None:
        return _search_local(query, top_k)
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


def _local_schema(con):
    con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS approved_course_fts USING fts5(
        course_id UNINDEXED, source_sha256 UNINDEXED, approval_revision UNINDEXED, content,
        tokenize='unicode61 remove_diacritics 2')""")


def _local_text(course):
    import json
    fields = ("course_id", "title", "description", "level", "training_format", "price_egp", "duration_hours",
              "department", "prerequisites", "learning_outcomes", "instructor_name", "instructor_bio",
              "schedule", "offers", "target_audience", "career_opportunities", "admission_requirements", "faqs")
    text = "\n".join(k.replace('_', ' ').title() + ": " +
                     (json.dumps(course[k], ensure_ascii=False) if isinstance(course[k], (list, dict)) else str(course[k]))
                     for k in fields if course.get(k) is not None)
    if course.get("data_origin") == "synthetic_demo":
        text = "FICTIONAL DEMONSTRATION ONLY\n" + text
    return text


def _save_local(con, course):
    con.execute("DELETE FROM approved_course_fts WHERE course_id=?", (course["course_id"],))
    con.execute("INSERT INTO approved_course_fts VALUES (?,?,?,?)",
                (course["course_id"], course["source_sha256"], course["reviewed_at"], _local_text(course)))


def _publish_local(course, refresh=False):
    try:
        with store.catalog_transaction() as con:
            _local_schema(con)
            _save_local(con, course)
        store.set_published(course["course_id"], course["upload_id"],
                            expected_reviewed_at=course["reviewed_at"], refresh=refresh)
        return {"course_id": course["course_id"], "status": "published", "indexed_chunks": 1,
                "source_sha256": course["source_sha256"], "retrieval_backend": "sqlite_fts5"}
    except HTTPException:
        raise
    except Exception as exc:
        store.mark_index_failed(course["course_id"], course["upload_id"], type(exc).__name__)
        raise HTTPException(503, "Local publication unavailable; approval retained for retry") from None


def _search_local(query, top_k):
    import re
    aliases = {"بايثون": "Python", "الدورات": "course", "دورات": "course", "الدورة": "course",
               "السعر": "price", "التكلفة": "price", "الرسوم": "price", "المدة": "duration",
               "المدرب": "instructor", "المتطلبات": "prerequisites", "العروض": "offers", "المواعيد": "schedule",
               "courses": "course", "cost": "price", "fees": "price", "teacher": "instructor"}
    words = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
    terms = list(dict.fromkeys(words + [aliases[w.casefold()] for w in words if w.casefold() in aliases]))[:40]
    if not terms:
        return []
    # Index only published staff-verified fields. This also migrates retrieval for
    # previously published Gemini records without unpublishing or reapproving them.
    courses = [store.get_course(c["course_id"], staff=True) for c in store.list_courses()]
    with store.catalog_transaction() as con:
        _local_schema(con)
        for c in courses:
            _save_local(con, c)
        rows = con.execute("SELECT course_id,source_sha256,approval_revision,content,bm25(approved_course_fts) AS rank "
                           "FROM approved_course_fts WHERE approved_course_fts MATCH ? ORDER BY rank LIMIT ?",
                           (' OR '.join('"' + t + '"' for t in terms), top_k)).fetchall()
    results = []
    for row in rows:
        if not store.is_published(row["course_id"], row["source_sha256"], row["approval_revision"]):
            continue
        c = store.get_course(row["course_id"], staff=True)
        review = store.load_upload(c["upload_id"])
        store.require_unrejected_upload(review)
        results.append({"course_id": row["course_id"], "course_title": c["title"], "source_file": review["filename"],
                        "source_sha256": row["source_sha256"], "approval_revision": row["approval_revision"],
                        "section": "Staff-approved catalog record", "content": row["content"],
                        "distance": row["rank"], "page_number": None})
    return results
