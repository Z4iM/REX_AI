"""Database models and helpers for the Curriculum agent – SQLAlchemy + SQLite."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


DATA_DIR = Path(os.getenv("REX_CURRICULUM_DIR", "data/curriculum"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "curriculum.db"


class Base(DeclarativeBase):
    pass


class Curriculum(Base):
    """A generated or imported curriculum."""
    __tablename__ = "curricula"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core fields
    title = Column(String(500), nullable=False)
    description = Column(Text)
    department = Column(String(200))
    target_audience = Column(String(300))
    skill_level = Column(String(50))             # Beginner / Intermediate / Advanced
    industry = Column(String(200))
    country = Column(String(100))
    language = Column(String(50), default="English")

    # Curriculum structure (stored as JSON text)
    objectives = Column(Text)                     # JSON list of objectives
    prerequisites = Column(Text)                  # JSON list
    learning_outcomes = Column(Text)              # JSON list
    modules = Column(Text)                        # JSON list of module dicts
    training_hours = Column(Float)
    practical_exercises = Column(Text)            # JSON list
    assessments = Column(Text)                    # JSON list
    capstone_project = Column(Text)               # JSON dict

    # Accreditation
    accreditation_framework = Column(String(300))
    alignment_report = Column(Text)               # JSON dict
    alignment_score = Column(Float)               # 0-100
    missing_topics = Column(Text)                 # JSON list

    # Metadata
    data_source = Column(String(500))
    data_source_date = Column(String(100))

    # Review workflow
    status = Column(String(50), default="draft")  # draft / pending_review / revision_requested / approved
    reviewer_name = Column(String(200))
    reviewer_notes = Column(Text)
    revision_history = Column(Text)               # JSON list of revision entries

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class AccreditationFramework(Base):
    """Known accreditation / competency standards for alignment comparison."""
    __tablename__ = "accreditation_frameworks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False, unique=True)
    organization = Column(String(300))
    description = Column(Text)
    country = Column(String(100))
    industry = Column(String(200))
    competencies = Column(Text)      # JSON list of required competency areas
    url = Column(String(500))
    last_updated = Column(String(100))


# ---------- engine / session -------------------------------------------------

def _enable_wal(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
        event.listen(_engine, "connect", _enable_wal)
        Base.metadata.create_all(_engine)
    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory


def get_session() -> Session:
    return get_session_factory()()


# ---------- helpers -----------------------------------------------------------

def to_dict(c: Curriculum) -> dict:
    """Serialize a Curriculum row to a plain dict."""

    def _json(val):
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    return {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "department": c.department,
        "target_audience": c.target_audience,
        "skill_level": c.skill_level,
        "industry": c.industry,
        "country": c.country,
        "language": c.language,
        "objectives": _json(c.objectives),
        "prerequisites": _json(c.prerequisites),
        "learning_outcomes": _json(c.learning_outcomes),
        "modules": _json(c.modules),
        "training_hours": c.training_hours,
        "practical_exercises": _json(c.practical_exercises),
        "assessments": _json(c.assessments),
        "capstone_project": _json(c.capstone_project),
        "accreditation_framework": c.accreditation_framework,
        "alignment_report": _json(c.alignment_report),
        "alignment_score": c.alignment_score,
        "missing_topics": _json(c.missing_topics),
        "data_source": c.data_source,
        "data_source_date": c.data_source_date,
        "status": c.status,
        "reviewer_name": c.reviewer_name,
        "reviewer_notes": c.reviewer_notes,
        "revision_history": _json(c.revision_history),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def search_curricula(
    session: Session,
    *,
    department: str | None = None,
    skill_level: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Curriculum]:
    from sqlalchemy import select, or_

    stmt = select(Curriculum).order_by(Curriculum.updated_at.desc())
    if department:
        stmt = stmt.where(Curriculum.department == department)
    if skill_level:
        stmt = stmt.where(Curriculum.skill_level == skill_level)
    if industry:
        stmt = stmt.where(Curriculum.industry == industry)
    if country:
        stmt = stmt.where(Curriculum.country == country)
    if status:
        stmt = stmt.where(Curriculum.status == status)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(
            Curriculum.title.ilike(pattern),
            Curriculum.description.ilike(pattern),
            Curriculum.department.ilike(pattern),
        ))
    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt).all())
