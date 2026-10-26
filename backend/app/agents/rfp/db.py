"""SQLite persistence (SQLAlchemy 2.0). SQLite is the source of truth for tenders, alerts, history and run logs."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, case,
                        create_engine, or_, select)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from . import config
from .rfp_agent import Tender, fingerprint

WORKFLOW_STATUSES = ["new", "reviewing", "applying", "submitted", "dismissed", "expired"]
SCHEMA_VERSION = "2"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Meta(Base):
    __tablename__ = "rfp_meta"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tender_id: Mapped[Optional[str]] = mapped_column(String(200))            # official reference, if any
    portal: Mapped[Optional[str]] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    issuer: Mapped[str] = mapped_column(Text)
    country_raw: Mapped[Optional[str]] = mapped_column(String(200))
    country_code: Mapped[Optional[str]] = mapped_column(String(2), index=True)
    country_basis: Mapped[Optional[str]] = mapped_column(String(20))         # explicit | city_mapping
    publication_date: Mapped[Optional[date]] = mapped_column(Date)
    deadline: Mapped[Optional[date]] = mapped_column(Date, index=True)
    deadline_status: Mapped[str] = mapped_column(String(10), default="known")  # known | unknown | unparsed
    deadline_raw: Mapped[Optional[str]] = mapped_column(String(200))           # exactly what the source said
    category: Mapped[Optional[str]] = mapped_column(Text)
    topics: Mapped[Optional[str]] = mapped_column(Text)
    eligibility: Mapped[Optional[str]] = mapped_column(Text)
    submission_url: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)                  # ONLY a validated http(s) page, else NULL
    import_reference: Mapped[Optional[str]] = mapped_column(Text)            # file#row when there is no real URL
    also_seen_at: Mapped[Optional[str]] = mapped_column(Text)                # JSON list of other URLs for this tender
    source_name: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    eligibility_assessment: Mapped[Optional[str]] = mapped_column(String(30))
    eligibility_notes: Mapped[Optional[str]] = mapped_column(Text)
    filter_status: Mapped[str] = mapped_column(String(20), default="accepted")  # accepted | needs_review
    review_reason: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[Optional[str]] = mapped_column(String(10))
    data_mode: Mapped[str] = mapped_column(String(30), default="imported")   # set ONLY by trusted code, never by input
    workflow_status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    notifications: Mapped[list["Notification"]] = relationship(back_populates="opportunity",
                                                                cascade="all, delete-orphan")
    history: Mapped[list["OpportunityHistory"]] = relationship(back_populates="opportunity",
                                                                cascade="all, delete-orphan")


class OpportunityHistory(Base):
    """Audit trail: what changed on a tender when the same record was re-imported."""
    __tablename__ = "opportunity_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), index=True)
    field: Mapped[str] = mapped_column(String(40))
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    source_name: Mapped[Optional[str]] = mapped_column(String(100))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    opportunity: Mapped[Opportunity] = relationship(back_populates="history")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("opportunity_id", "kind", name="uq_notification_once"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"))
    kind: Mapped[str] = mapped_column(String(30))
    # egypt_priority | saudi_monitor (verified-by-rules)  |  egypt_verify | saudi_verify | needs_review (unverified)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    opportunity: Mapped[Opportunity] = relationship(back_populates="notifications")


class SourceRun(Base):
    """One row per source per run - failed sources MUST be recorded (project business rule)."""
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="running")  # ok | failed | skipped
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)


class RejectedTender(Base):
    __tablename__ = "rejected_tenders"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text)
    issuer: Mapped[Optional[str]] = mapped_column(Text)
    country_raw: Mapped[Optional[str]] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    source_name: Mapped[Optional[str]] = mapped_column(String(100))
    data_mode: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------- engine / schema versioning

def _sqlite_file(url: str) -> Optional[Path]:
    if url.startswith("sqlite:///") and ":memory:" not in url:
        return Path(url.replace("sqlite:///", "", 1))
    return None


def _backup_if_old_schema(path: Path) -> Optional[Path]:
    """v1 databases (no rfp_meta table) cannot be upgraded in place: the duplicate key (fingerprint) and several
    columns changed. The file is renamed to *.v1.bak and a fresh database is created; re-import the source files."""
    con = sqlite3.connect(path)
    try:
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    finally:
        con.close()
    if "opportunities" in tables and "rfp_meta" not in tables:
        bak = path.with_name(path.name + f".v1.{utcnow():%Y%m%d%H%M%S}.bak")
        path.rename(bak)
        print(f"[rfp.db] Old (v1) database moved to {bak.name}; a fresh v2 database will be created. Re-import your files.")
        return bak
    return None


def get_session_factory(url: Optional[str] = None) -> sessionmaker:
    url = url or config.database_url()
    path = _sqlite_file(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            _backup_if_old_schema(path)
    engine = create_engine(url, future=True,
                           connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as s:
        if s.get(Meta, "schema_version") is None:
            s.add(Meta(key="schema_version", value=SCHEMA_VERSION))
            s.commit()
    return factory


def recompute_fingerprints(session: Session) -> dict:
    """Re-derive every fingerprint with the CURRENT key definition (use after changing fingerprint() in a populated DB).
    Rows that collapse onto the same new key are merged: the oldest row is kept, later ones are deleted.
    The rejected-tender audit log cannot be recomputed (deadline not stored) and is cleared."""
    rows = session.scalars(select(Opportunity).order_by(Opportunity.id)).all()
    for o in rows:                       # park old values so the UNIQUE constraint cannot collide mid-way
        o.fingerprint = f"tmp-{o.id}"
    session.flush()
    seen: dict[str, int] = {}
    merged = 0
    for o in rows:
        fp = fingerprint(Tender(title=o.title, issuer=o.issuer, country=o.country_raw, deadline=o.deadline,
                                source_url=o.source_url, tender_id=o.tender_id, portal=o.portal))
        if fp in seen:
            session.delete(o)
            merged += 1
        else:
            seen[fp] = o.id
            o.fingerprint = fp
    cleared = len(session.scalars(select(RejectedTender)).all())
    for r in session.scalars(select(RejectedTender)).all():
        session.delete(r)
    session.commit()
    return {"kept": len(seen), "merged_duplicates": merged, "rejected_log_cleared": cleared}


# ---------------------------------------------------------------- queries

def search_opportunities(
    session: Session,
    q: Optional[str] = None,
    country: Optional[str] = None,
    priority: Optional[str] = None,
    workflow_status: Optional[str] = None,
    filter_status: Optional[str] = None,
    assessment: Optional[str] = None,
    data_mode: Optional[str] = None,
    include_expired: bool = False,
    deadline_from: Optional[date] = None,
    deadline_to: Optional[date] = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[Opportunity]:
    """Sorted IN SQL (priority rank, soonest deadline, newest) BEFORE limit/offset, so pagination is correct."""
    stmt = select(Opportunity)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(*[getattr(Opportunity, c).ilike(like) for c in
                                ("title", "issuer", "summary", "category", "topics", "description", "tender_id")]))
    if country:
        stmt = stmt.where(Opportunity.country_code == country)
    if priority:
        stmt = stmt.where(Opportunity.priority == priority)
    if workflow_status:
        stmt = stmt.where(Opportunity.workflow_status == workflow_status)
    elif not include_expired:
        stmt = stmt.where(Opportunity.workflow_status != "expired")
    if filter_status:
        stmt = stmt.where(Opportunity.filter_status == filter_status)
    if assessment:
        stmt = stmt.where(Opportunity.eligibility_assessment == assessment)
    if data_mode:
        stmt = stmt.where(Opportunity.data_mode == data_mode)
    if deadline_from:
        stmt = stmt.where(Opportunity.deadline >= deadline_from)
    if deadline_to:
        stmt = stmt.where(Opportunity.deadline <= deadline_to)
    rank = case((Opportunity.priority == "high", 0), (Opportunity.priority == "monitor", 1), else_=2)
    stmt = stmt.order_by(rank, Opportunity.deadline.is_(None), Opportunity.deadline.asc(), Opportunity.id.desc())
    return list(session.scalars(stmt.limit(limit).offset(offset)))


def mark_expired(session: Session, today: Optional[date] = None) -> int:
    today = today or date.today()
    rows = session.scalars(select(Opportunity).where(
        Opportunity.deadline < today, Opportunity.workflow_status.in_(["new", "reviewing"]))).all()
    for o in rows:
        o.workflow_status = "expired"
    session.commit()
    return len(rows)


def update_workflow(session: Session, opportunity_id: int, status: Optional[str] = None,
                    notes: Optional[str] = None) -> Optional[Opportunity]:
    opp = session.get(Opportunity, opportunity_id)
    if not opp:
        return None
    if status:
        if status not in WORKFLOW_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        opp.workflow_status = status
    if notes is not None:
        opp.reviewer_notes = notes
    session.commit()
    return opp


def delete_demo_data(session: Session) -> int:
    rows = session.scalars(select(Opportunity).where(Opportunity.data_mode == "synthetic_demo")).all()
    for o in rows:
        session.delete(o)
    for r in session.scalars(select(RejectedTender).where(RejectedTender.data_mode == "synthetic_demo")).all():
        session.delete(r)
    session.commit()
    return len(rows)


def to_dict(o: Opportunity) -> dict:
    return {c.name: getattr(o, c.name) for c in Opportunity.__table__.columns}
