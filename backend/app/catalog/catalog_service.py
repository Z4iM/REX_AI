"""Persistent staff-approved course registry. SQLite is the authorization source of truth.

A Chroma chunk NEVER becomes student-visible solely by having approval metadata.
Its upload hash and published status must still match this registry.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.app import runtime

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
UPLOAD_RE = re.compile(r"^[a-f0-9]{64}$")
COURSE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{1,49}$")


def data_dir() -> Path:
    return runtime.catalog_dir()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connection():
    path = data_dir() / "catalog.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 15000")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS courses (
        course_id TEXT PRIMARY KEY,
        upload_id TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        title TEXT NOT NULL,
        record_json TEXT NOT NULL,
        status TEXT NOT NULL,
        reviewer TEXT NOT NULL,
        reviewed_at TEXT NOT NULL,
        published_at TEXT,
        indexing_error TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS catalog_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id TEXT NOT NULL,
        action TEXT NOT NULL,
        reviewer TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    )""")
    return con


@contextmanager
def catalog_transaction():
    """Serialize upload decisions and catalog writes across threads/processes."""
    con = _connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.execute("COMMIT")
    except Exception:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


class DocumentRejection(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    reviewer: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=1, max_length=4000)


class CourseApproval(BaseModel):
    """Staff-verified attributes; never inferred from a document or an LLM."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    course_id: str = Field(min_length=2, max_length=50)
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=10, max_length=10000)
    level: Literal["Beginner", "Intermediate", "Advanced"] | None = None
    training_format: Literal["Online", "On-site", "Hybrid"] | None = None
    price_egp: float | None = Field(default=None, ge=0, le=100000000)
    duration_hours: float | None = Field(default=None, gt=0, le=10000)
    department: str | None = Field(default=None, max_length=120)
    instructor_name: str | None = Field(default=None, max_length=120)
    instructor_bio: str | None = Field(default=None, max_length=2000)
    schedule: str | None = Field(default=None, max_length=1000)
    offers: str | None = Field(default=None, max_length=1000)
    target_audience: str | None = Field(default=None, max_length=2000)
    career_opportunities: list[str] = Field(default_factory=list, max_length=30)
    admission_requirements: list[str] = Field(default_factory=list, max_length=30)
    faqs: list[dict[str, str]] = Field(default_factory=list, max_length=30)
    prerequisites: list[str] = Field(default_factory=list, max_length=60)
    learning_outcomes: list[str] = Field(default_factory=list, max_length=100)
    reviewer: str = Field(min_length=2, max_length=120)
    acknowledge_extraction_warnings: bool = False

    @field_validator("course_id")
    @classmethod
    def valid_code(cls, value: str) -> str:
        value = value.upper()
        if not COURSE_RE.fullmatch(value):
            raise ValueError("Course ID must be 2-50 characters: A-Z, 0-9, _, - or .")
        return value

    @field_validator("prerequisites", "learning_outcomes", "career_opportunities", "admission_requirements")
    @classmethod
    def validate_items(cls, items: list[str]) -> list[str]:
        clean = [x.strip() for x in items]
        if any(not x or len(x) > 1000 for x in clean):
            raise ValueError("Each list item must contain 1-1000 characters")
        return clean

    @field_validator("faqs")
    @classmethod
    def validate_faqs(cls, items):
        if any(set(item) != {"question", "answer"} or any(not value.strip() or len(value) > 2000
               for value in item.values()) for item in items):
            raise ValueError("Each FAQ needs a nonempty question and answer, at most 2000 characters each")
        return [{k: v.strip() for k, v in item.items()} for item in items]


def load_upload(upload_id: str, *, require_chunks: bool = True) -> dict:
    if not UPLOAD_RE.fullmatch(upload_id):
        raise HTTPException(404, "Upload not found")
    folder = data_dir() / "uploads" / upload_id
    path = folder / "review.json"
    if not path.is_file():
        raise HTTPException(404, "Upload not found")
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
        suffix = "." + review["file_type"]
        source = folder / ("source" + suffix)
        if not source.is_file():
            raise ValueError("Original source document is missing")
        if review["upload_id"] != upload_id or review["source_sha256"] != upload_id:
            raise ValueError("Upload manifest identity mismatch")
        if hashlib.sha256(source.read_bytes()).hexdigest() != upload_id:
            raise ValueError("Original source file checksum has changed")
        if require_chunks and not review.get("chunks"):
            raise ValueError("Upload contains no reviewable chunks")
        return review
    except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(409, "Uploaded document integrity verification failed") from exc


def require_unrejected_upload(review: dict) -> None:
    if review.get("review_status") == "rejected" or review.get("approval_status") == "rejected":
        raise HTTPException(409, "Rejected documents cannot be approved or published; upload a corrected source")


def _write_upload_review(upload_id: str, review: dict) -> None:
    """Replace status and audit history together, retaining the original on failure."""
    path = data_dir() / "uploads" / upload_id / "review.json"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="review-", suffix=".tmp", delete=False) as file:
            temp_path = Path(file.name)
            json.dump(review, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def reject_upload(upload_id: str, payload: DocumentRejection) -> dict:
    # The manifest holds the upload-level audit so status and event have one atomic write.
    # Share SQLite's writer lock with approval, publication and duplicate uploads.
    with catalog_transaction() as con:
        review = load_upload(upload_id, require_chunks=False)
        require_unrejected_upload(review)
        if review.get("review_status") not in ("pending_review", "blocked_incomplete"):
            raise HTTPException(409, "Only pending or incomplete documents can be rejected")
        linked = con.execute(
            "SELECT 1 FROM courses WHERE upload_id=? AND status!='withdrawn' LIMIT 1",
            (upload_id,),
        ).fetchone()
        if linked:
            raise HTTPException(409, "Withdraw every course linked to this upload before rejecting it")
        now = _now()
        event = {"action": "rejected", "reviewer": payload.reviewer, "reason": payload.reason,
                 "recorded_at": now, "previous_review_status": review["review_status"]}
        updated = {**review, "review_status": "rejected", "approval_status": "rejected",
                   "indexing_allowed": False, "rejected_by": payload.reviewer,
                   "rejected_at": now, "rejection_reason": payload.reason,
                   "review_history": [*review.get("review_history", []), event]}
        try:
            _write_upload_review(upload_id, updated)
        except OSError as exc:
            raise HTTPException(503, "Could not save rejection; please retry") from exc
    return updated


def _to_public(row: sqlite3.Row) -> dict:
    obj = json.loads(row["record_json"])
    obj.setdefault("data_origin", "academy")
    return {**obj, "status": row["status"], "published_at": row["published_at"], "approval_revision": row["reviewed_at"],
            "source_sha256": row["source_sha256"]}


def _to_staff(row: sqlite3.Row) -> dict:
    return {**_to_public(row), "upload_id": row["upload_id"],
            "reviewer": row["reviewer"], "reviewed_at": row["reviewed_at"],
            "indexing_error": row["indexing_error"]}


def _event(con, course_id: str, action: str, reviewer: str):
    con.execute("INSERT INTO catalog_events(course_id, action, reviewer, recorded_at) VALUES(?,?,?,?)",
                (course_id, action, reviewer, _now()))


def approve_upload(upload_id: str, payload: CourseApproval) -> dict:
    data = payload.model_dump(exclude={"reviewer", "acknowledge_extraction_warnings"})
    con = _connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        review = load_upload(upload_id)
        require_unrejected_upload(review)
        if review.get("data_origin", "academy") != runtime.origin():
            raise HTTPException(409, "Source belongs to a different application data mode")
        data["data_origin"] = review.get("data_origin", "academy")
        if review.get("review_status") == "blocked_incomplete" or review.get("missing_pages"):
            raise HTTPException(409, "Incomplete extraction must be corrected and re-uploaded before approval")
        if review.get("extraction_warnings") and not payload.acknowledge_extraction_warnings:
            raise HTTPException(409, "Confirm manual verification of all extraction warnings")
        row = con.execute("SELECT * FROM courses WHERE course_id = ?", (payload.course_id,)).fetchone()
        if row and row["upload_id"] != upload_id and row["status"] != "withdrawn":
            raise HTTPException(409, "Course ID belongs to another upload; withdraw old course first")
        if row and row["status"] == "published":
            raise HTTPException(409, "Withdraw the published course before editing its approval")
        # The new source version cannot be visible before a successful RAG publication.
        con.execute("""INSERT INTO courses(course_id,upload_id,source_sha256,title,record_json,status,reviewer,reviewed_at,published_at,indexing_error)
            VALUES (?,?,?,?,?,'approved',?,?,NULL,NULL)
            ON CONFLICT(course_id) DO UPDATE SET upload_id=excluded.upload_id,source_sha256=excluded.source_sha256,
            title=excluded.title,record_json=excluded.record_json,status='approved',reviewer=excluded.reviewer,
            reviewed_at=excluded.reviewed_at,published_at=NULL,indexing_error=NULL""",
            (payload.course_id, upload_id, upload_id, payload.title, json.dumps(data, ensure_ascii=False),
             payload.reviewer, _now()))
        _event(con, payload.course_id, "approved_for_indexing", payload.reviewer)
        con.execute("COMMIT")
        return get_course(payload.course_id, staff=True)
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def get_course(course_id: str, *, staff: bool = False) -> dict:
    con = _connection()
    try:
        row = con.execute("SELECT * FROM courses WHERE course_id = ?", (course_id.upper(),)).fetchone()
        if not row or (not staff and row["status"] != "published"):
            raise HTTPException(404, "Course not found")
        course = _to_staff(row) if staff else _to_public(row)
        if course.get("data_origin", "academy") != runtime.origin():
            raise HTTPException(404, "Course not found in this data mode")
        return course
    finally:
        con.close()


def list_courses(*, staff: bool = False) -> list[dict]:
    con = _connection()
    try:
        rows = con.execute("SELECT * FROM courses ORDER BY title COLLATE NOCASE").fetchall() if staff else con.execute(
            "SELECT * FROM courses WHERE status = 'published' ORDER BY title COLLATE NOCASE").fetchall()
        return [c for r in rows if (c := (_to_staff(r) if staff else _to_public(r)))["data_origin"] == runtime.origin()]
    finally:
        con.close()


def is_published(course_id: str, source_sha256: str, approval_revision: str | None = None) -> bool:
    con = _connection()
    try:
        row = con.execute("SELECT reviewed_at,record_json FROM courses WHERE course_id = ? AND source_sha256 = ? AND status = 'published'",
                          (course_id, source_sha256)).fetchone()
        return (row is not None and json.loads(row["record_json"]).get("data_origin", "academy") == runtime.origin()
                and (approval_revision is None or row["reviewed_at"] == approval_revision))
    finally:
        con.close()


def set_published(course_id: str, upload_id: str, *, expected_reviewed_at: str | None = None,
                  refresh: bool = False) -> None:
    con = _connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,)).fetchone()
        allowed = ("published",) if refresh else ("approved", "index_failed")
        if (not row or row["upload_id"] != upload_id or row["status"] not in allowed or
                (expected_reviewed_at is not None and row["reviewed_at"] != expected_reviewed_at)):
            raise HTTPException(409, "Course approval changed; cannot publish")
        require_unrejected_upload(load_upload(upload_id))
        con.execute("UPDATE courses SET status='published',published_at=?,indexing_error=NULL WHERE course_id=?",
                    (_now(), course_id))
        _event(con, course_id, "index_refreshed" if refresh else "published", row["reviewer"])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def mark_index_failed(course_id: str, upload_id: str, exception_type: str) -> None:
    con = _connection()
    try:
        con.execute("UPDATE courses SET status='index_failed', indexing_error=? WHERE course_id=? AND upload_id=? AND status IN ('approved','index_failed')",
                    (exception_type, course_id, upload_id))
        con.commit()
    finally:
        con.close()


def withdraw_course(course_id: str, reviewer: str) -> dict:
    if len(reviewer.strip()) < 2:
        raise HTTPException(422, "Reviewer is required")
    con = _connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM courses WHERE course_id = ?", (course_id.upper(),)).fetchone()
        if not row:
            raise HTTPException(404, "Course not found")
        if row["status"] != "withdrawn":
            con.execute("UPDATE courses SET status='withdrawn',published_at=NULL WHERE course_id=?",
                        (course_id.upper(),))
            _event(con, course_id.upper(), "withdrawn", reviewer.strip())
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return get_course(course_id, staff=True)


def course_history(course_id: str) -> list[dict]:
    get_course(course_id, staff=True)
    con = _connection()
    try:
        return [dict(r) for r in con.execute("SELECT action,reviewer,recorded_at FROM catalog_events WHERE course_id=? ORDER BY id",
                                              (course_id.upper(),)).fetchall()]
    finally:
        con.close()


def list_matching_courses() -> list[dict]:
    """Course-matcher adapter: published, staff-verified metadata only."""
    courses = []
    for c in list_courses():
        source = data_dir() / "uploads" / c["source_sha256"] / "review.json"
        filename = "approved course document"
        if source.is_file():
            try:
                filename = json.loads(source.read_text(encoding="utf-8"))["filename"]
            except (ValueError, OSError, KeyError):
                pass
        courses.append({
            "course_id": c["course_id"], "title": c["title"],
            "level": c["level"], "training_format": c["training_format"],
            "price": f"{c['price_egp']:g} EGP" if c["price_egp"] is not None else None,
            "duration": f"{c['duration_hours']:g} hours" if c["duration_hours"] else None,
            "department": c["department"], "description": c["description"],
            "prerequisites": c["prerequisites"], "learning_outcomes": c["learning_outcomes"],
            "source_file": filename,
            "source_sha256": c["source_sha256"],
            "approval_revision": c["approval_revision"],
        })
    return courses
