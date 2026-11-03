"""Explicit, source-checked handoffs between curriculum, documents and marketing."""
import hashlib
import json
from fastapi import HTTPException


def approved_curriculum(curriculum_id, course_ids):
    from backend.app.agents.curriculum import service
    c = service.get_curriculum(curriculum_id)
    if not c:
        raise HTTPException(404, "Curriculum not found")
    if c["status"] != "approved":
        raise HTTPException(409, "Choose an approved curriculum")
    service.validate_sources(c["source_records"])
    if not set(course_ids).issubset({s["course_id"] for s in c["source_records"]}):
        raise HTTPException(409, "The approved curriculum must reference the selected courses")
    return c


def curriculum_hash(curriculum):
    return hashlib.sha256(json.dumps(curriculum, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_curriculum_snapshot(record):
    snapshot = record.get("curriculum")
    if snapshot:
        current = approved_curriculum(snapshot["id"], [s["course_id"] for s in snapshot["source_records"]])
        if curriculum_hash(current) != curriculum_hash(snapshot):
            raise HTTPException(409, "Curriculum changed; create a new version")
