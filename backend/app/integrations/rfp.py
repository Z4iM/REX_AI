"""Reuse Faris's services and validation behind the host's staff authentication."""
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from backend.app import runtime
from backend.app.catalog.upload_router import require_catalog_admin
from backend.app.agents.rfp import config, db, service, notifications
from backend.app.agents.rfp.router import build_router


@lru_cache(maxsize=8)
def _factory(url):
    return db.get_session_factory(url)


def session_factory():
    return _factory(config.database_url())()


router = build_router(session_factory=session_factory, auth_dependency=require_catalog_admin)
extra_router = APIRouter(prefix="/api/v1/rfp", tags=["rfp"], dependencies=[Depends(require_catalog_admin)])


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[dict] = Field(min_length=1, max_length=200)
    use_gemini: bool = False


@extra_router.post("/import")
def import_opportunities(body: ImportRequest):
    if not runtime.is_demo() and any("REX_SYNTHETIC_DEMO" in str(item) or item.get("data_mode") == "synthetic_demo"
                                     for item in body.items):
        raise HTTPException(409, "Import synthetic fixtures in Demo mode, not the academy database")
    with session_factory() as session:
        result = service.ingest_raw(session, body.items, "staff_file_import", use_gemini=body.use_gemini,
                                   data_mode="synthetic_demo" if runtime.is_demo() else "imported")
        # Dashboard alerts only. No implicit SMTP or webhook delivery.
        if result.new_opportunities:
            notifications.create_notifications(session, result.new_opportunities)
        return {key: getattr(result, key) for key in (
            "fetched", "new", "needs_review", "rejected", "duplicates", "already_known", "updated", "invalid", "errors")}


@extra_router.get("/activity")
def activity():
    with session_factory() as session:
        rejected = session.scalars(select(db.RejectedTender).order_by(db.RejectedTender.id.desc()).limit(100)).all()
        runs = session.scalars(select(db.SourceRun).order_by(db.SourceRun.id.desc()).limit(50)).all()
        return {"rejected": [{"title": r.title, "reason": r.reason, "data_mode": r.data_mode} for r in rejected],
                "runs": [{"source": r.source_name, "status": r.status, "fetched": r.fetched,
                          "new": r.new_count, "rejected": r.rejected_count} for r in runs]}
