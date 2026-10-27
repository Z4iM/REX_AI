"""Service layer for the Curriculum Research & Accreditation Alignment Agent.

Orchestrates research, generation, alignment, review, and PDF export.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import db
from .curriculum_agent import compare_accreditation, generate_curriculum, research_topics
from .frameworks import seed_frameworks
from .pdf_generator import generate_curriculum_pdf, save_curriculum_pdf

logger = logging.getLogger(__name__)


# ---------- initialization ---------------------------------------------------

def _ensure_frameworks():
    """Seed default accreditation frameworks on first use."""
    session = db.get_session()
    try:
        count = session.query(db.AccreditationFramework).count()
        if count == 0:
            seed_frameworks(session)
    finally:
        session.close()


_ensure_frameworks()


# ---------- framework queries ------------------------------------------------

def list_frameworks(
    *,
    country: str | None = None,
    industry: str | None = None,
) -> list[dict]:
    session = db.get_session()
    try:
        q = session.query(db.AccreditationFramework)
        if country:
            q = q.filter(db.AccreditationFramework.country == country)
        if industry:
            q = q.filter(db.AccreditationFramework.industry.ilike(f"%{industry}%"))
        rows = q.all()
        result = []
        for fw in rows:
            comps = fw.competencies
            if isinstance(comps, str):
                try:
                    comps = json.loads(comps)
                except (json.JSONDecodeError, TypeError):
                    comps = []
            result.append({
                "id": fw.id,
                "name": fw.name,
                "organization": fw.organization,
                "description": fw.description,
                "country": fw.country,
                "industry": fw.industry,
                "competencies": comps,
                "url": fw.url,
                "last_updated": fw.last_updated,
            })
        return result
    finally:
        session.close()


def get_framework(framework_id: int) -> dict | None:
    session = db.get_session()
    try:
        fw = session.get(db.AccreditationFramework, framework_id)
        if not fw:
            return None
        comps = fw.competencies
        if isinstance(comps, str):
            try:
                comps = json.loads(comps)
            except (json.JSONDecodeError, TypeError):
                comps = []
        return {
            "id": fw.id,
            "name": fw.name,
            "organization": fw.organization,
            "description": fw.description,
            "country": fw.country,
            "industry": fw.industry,
            "competencies": comps,
            "url": fw.url,
            "last_updated": fw.last_updated,
        }
    finally:
        session.close()


# ---------- research ---------------------------------------------------------

def research_curriculum_topics(
    subject: str,
    skill_level: str = "Intermediate",
    industry: str = "",
    country: str = "",
) -> dict:
    """Research topics for a given subject using AI."""
    return research_topics(subject, skill_level, industry, country)


# ---------- curriculum generation & storage ----------------------------------

def create_curriculum(
    subject: str,
    *,
    skill_level: str = "Intermediate",
    target_audience: str = "",
    industry: str = "",
    country: str = "",
    language: str = "English",
    duration_hours: float | None = None,
    department: str = "",
    additional_requirements: str = "",
    accreditation_framework_id: int | None = None,
    research_context: dict | None = None,
) -> dict:
    """Generate a new curriculum and store it in the database."""
    # 1. Generate curriculum via AI
    curriculum_data = generate_curriculum(
        subject,
        skill_level=skill_level,
        target_audience=target_audience,
        industry=industry,
        country=country,
        language=language,
        duration_hours=duration_hours,
        additional_requirements=additional_requirements,
        research_context=research_context,
    )

    # 2. Run accreditation alignment if a framework was selected
    alignment = None
    framework_name = None
    if accreditation_framework_id:
        fw = get_framework(accreditation_framework_id)
        if fw:
            framework_name = fw["name"]
            alignment = compare_accreditation(
                curriculum_data,
                framework_name=fw["name"],
                framework_competencies=fw["competencies"],
                framework_description=fw.get("description", ""),
            )

    # 3. Persist to database
    session = db.get_session()
    try:
        row = db.Curriculum(
            title=curriculum_data.get("title", subject),
            description=curriculum_data.get("description", ""),
            department=department or curriculum_data.get("department", ""),
            target_audience=target_audience or curriculum_data.get("target_audience", ""),
            skill_level=skill_level,
            industry=industry or curriculum_data.get("industry", ""),
            country=country,
            language=language,
            objectives=json.dumps(curriculum_data.get("objectives", []), ensure_ascii=False),
            prerequisites=json.dumps(curriculum_data.get("prerequisites", []), ensure_ascii=False),
            learning_outcomes=json.dumps(curriculum_data.get("learning_outcomes", []), ensure_ascii=False),
            modules=json.dumps(curriculum_data.get("modules", []), ensure_ascii=False),
            training_hours=curriculum_data.get("training_hours"),
            practical_exercises=json.dumps(curriculum_data.get("practical_exercises", []), ensure_ascii=False),
            assessments=json.dumps(curriculum_data.get("assessments", []), ensure_ascii=False),
            capstone_project=json.dumps(curriculum_data.get("capstone_project", {}), ensure_ascii=False),
            accreditation_framework=framework_name,
            alignment_report=json.dumps(alignment, ensure_ascii=False) if alignment else None,
            alignment_score=alignment.get("overall_alignment_score") if alignment else None,
            missing_topics=json.dumps(alignment.get("missing_topics", []), ensure_ascii=False) if alignment else None,
            data_source=curriculum_data.get("data_source", "AI-generated"),
            data_source_date=curriculum_data.get("data_source_date",
                                                  datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            status="draft",
            revision_history=json.dumps([{
                "action": "created",
                "date": datetime.now(timezone.utc).isoformat(),
                "note": "Initial AI-generated curriculum",
            }], ensure_ascii=False),
        )
        session.add(row)
        session.commit()
        return db.to_dict(row)
    finally:
        session.close()


# ---------- CRUD -------------------------------------------------------------

def list_curricula(
    *,
    department: str | None = None,
    skill_level: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    session = db.get_session()
    try:
        rows = db.search_curricula(
            session,
            department=department,
            skill_level=skill_level,
            industry=industry,
            country=country,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
        )
        return [db.to_dict(r) for r in rows]
    finally:
        session.close()


def get_curriculum(curriculum_id: int) -> dict | None:
    session = db.get_session()
    try:
        row = session.get(db.Curriculum, curriculum_id)
        return db.to_dict(row) if row else None
    finally:
        session.close()


# ---------- review workflow --------------------------------------------------

VALID_STATUSES = {"draft", "pending_review", "revision_requested", "approved"}


def submit_for_review(curriculum_id: int) -> dict | None:
    """Move a draft curriculum to pending_review status."""
    session = db.get_session()
    try:
        row = session.get(db.Curriculum, curriculum_id)
        if not row:
            return None
        if row.status not in ("draft", "revision_requested"):
            raise ValueError(f"Cannot submit for review from status '{row.status}'")
        row.status = "pending_review"
        _append_history(row, "submitted_for_review", "Submitted for instructor/admin review")
        session.commit()
        return db.to_dict(row)
    finally:
        session.close()


def review_curriculum(
    curriculum_id: int,
    *,
    action: str,       # "approve" | "request_revision"
    reviewer_name: str,
    notes: str = "",
) -> dict | None:
    """Instructor/admin reviews a curriculum."""
    session = db.get_session()
    try:
        row = session.get(db.Curriculum, curriculum_id)
        if not row:
            return None
        if row.status != "pending_review":
            raise ValueError(f"Can only review curricula in 'pending_review' status (current: '{row.status}')")
        if action == "approve":
            row.status = "approved"
        elif action == "request_revision":
            row.status = "revision_requested"
        else:
            raise ValueError(f"Invalid review action: '{action}'. Use 'approve' or 'request_revision'.")
        row.reviewer_name = reviewer_name
        row.reviewer_notes = notes
        _append_history(row, action, f"Reviewed by {reviewer_name}: {notes}" if notes else f"Reviewed by {reviewer_name}")
        session.commit()
        return db.to_dict(row)
    finally:
        session.close()


def _append_history(row: db.Curriculum, action: str, note: str):
    history = json.loads(row.revision_history or "[]")
    history.append({
        "action": action,
        "date": datetime.now(timezone.utc).isoformat(),
        "note": note,
    })
    row.revision_history = json.dumps(history, ensure_ascii=False)


# ---------- alignment --------------------------------------------------------

def run_alignment(curriculum_id: int, framework_id: int) -> dict | None:
    """Run or re-run accreditation alignment for an existing curriculum."""
    session = db.get_session()
    try:
        row = session.get(db.Curriculum, curriculum_id)
        if not row:
            return None
        fw = get_framework(framework_id)
        if not fw:
            raise ValueError(f"Framework #{framework_id} not found")

        curriculum_data = db.to_dict(row)
        alignment = compare_accreditation(
            curriculum_data,
            framework_name=fw["name"],
            framework_competencies=fw["competencies"],
            framework_description=fw.get("description", ""),
        )
        row.accreditation_framework = fw["name"]
        row.alignment_report = json.dumps(alignment, ensure_ascii=False)
        row.alignment_score = alignment.get("overall_alignment_score")
        row.missing_topics = json.dumps(alignment.get("missing_topics", []), ensure_ascii=False)
        _append_history(row, "alignment_run", f"Alignment checked against {fw['name']}")
        session.commit()
        return {"curriculum": db.to_dict(row), "alignment": alignment}
    finally:
        session.close()


# ---------- PDF export -------------------------------------------------------

def export_pdf(curriculum_id: int) -> bytes | None:
    """Generate and return PDF bytes for a curriculum."""
    session = db.get_session()
    try:
        row = session.get(db.Curriculum, curriculum_id)
        if not row:
            return None
        curriculum_data = db.to_dict(row)
        alignment = None
        if row.alignment_report:
            try:
                alignment = json.loads(row.alignment_report)
            except (json.JSONDecodeError, TypeError):
                pass
        return generate_curriculum_pdf(curriculum_data, alignment)
    finally:
        session.close()
