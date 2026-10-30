"""
FastAPI APIRouter for the RFP agent - include it in the existing REX AI backend:

    from app.agents.rfp.router import build_router
    app.include_router(build_router(auth_dependency=require_staff))      # host app's own staff auth
    # routes: /api/v1/rfp/...

Default auth (when no auth_dependency is given) is a shared secret in header  X-API-Key = RFP_API_KEY  (used by n8n).
If RFP_API_KEY is not set the default auth refuses every request (secure by default).
"""
from __future__ import annotations

import hmac
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from . import config, db, service
from . import sources as sources_mod


class RunRequest(BaseModel):
    sources: Optional[list[str]] = None     # names from sources.yaml; None = all enabled
    use_gemini: bool = True
    notify: bool = False


class UpdateRequest(BaseModel):
    workflow_status: Optional[str] = None
    reviewer_notes: Optional[str] = None


def default_api_key_auth(x_api_key: Optional[str] = Header(default=None)):
    expected = config.rfp_api_key()
    if not expected:
        raise HTTPException(503, "RFP_API_KEY is not configured on the server")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid or missing API key")


def build_router(session_factory=None, sources_loader: Optional[Callable] = None,
                 auth_dependency: Optional[Callable] = None, prefix: str = "/api/v1/rfp") -> APIRouter:
    factory = session_factory or db.get_session_factory()
    load = sources_loader or sources_mod.load_sources
    auth = auth_dependency or default_api_key_auth
    router = APIRouter(prefix=prefix, tags=["rfp"], dependencies=[Depends(auth)])

    def get_session():
        with factory() as s:
            yield s

    @router.post("/run")
    def run(req: RunRequest, session=Depends(get_session)):
        from backend.app import runtime
        if runtime.is_demo():
            raise HTTPException(409, "Use the fictional tender examples in Demo setup; online searches run in academy mode")
        srcs = load(only=req.sources) if req.sources else load()
        rep = service.run_all(session, srcs, use_gemini=req.use_gemini, notify=req.notify)
        t = rep.totals
        return {
            "new_count": t.new, "needs_review": t.needs_review, "rejected": t.rejected, "duplicates": t.duplicates,
            "already_known": t.already_known, "updated": t.updated, "invalid": t.invalid,
            "notifications_created": rep.notifications_created, "email_sent": rep.email_sent,
            "webhook_sent": rep.webhook_sent, "expired_marked": rep.expired_marked, "sources": rep.per_source,
            "new_items": [{"id": o.id, "title": o.title, "country": o.country_code, "priority": o.priority,
                           "verified": o.filter_status == "accepted", "deadline_status": o.deadline_status,
                           "deadline": o.deadline.isoformat() if o.deadline else None,
                           "source_url": o.source_url, "import_reference": o.import_reference}
                          for o in t.new_opportunities],
        }

    @router.get("/opportunities")
    def list_opportunities(q: Optional[str] = None, country: Optional[str] = Query(None, pattern="^(EG|SA)$"),
                           priority: Optional[str] = None, workflow_status: Optional[str] = None,
                           filter_status: Optional[str] = None, include_expired: bool = False,
                           limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0),
                           session=Depends(get_session)):
        rows = db.search_opportunities(session, q=q, country=country, priority=priority,
                                       workflow_status=workflow_status, filter_status=filter_status,
                                       include_expired=include_expired, limit=limit, offset=offset)
        return {"count": len(rows), "limit": limit, "offset": offset, "items": [db.to_dict(o) for o in rows]}

    @router.get("/opportunities/{opp_id}")
    def get_opportunity(opp_id: int, session=Depends(get_session)):
        o = session.get(db.Opportunity, opp_id)
        if not o:
            raise HTTPException(404, "Opportunity not found")
        return db.to_dict(o)

    @router.get("/opportunities/{opp_id}/history")
    def get_history(opp_id: int, session=Depends(get_session)):
        if not session.get(db.Opportunity, opp_id):
            raise HTTPException(404, "Opportunity not found")
        rows = session.scalars(select(db.OpportunityHistory).where(db.OpportunityHistory.opportunity_id == opp_id)
                               .order_by(db.OpportunityHistory.changed_at)).all()
        return {"items": [{"field": h.field, "old": h.old_value, "new": h.new_value, "source": h.source_name,
                           "changed_at": h.changed_at.isoformat()} for h in rows]}

    @router.patch("/opportunities/{opp_id}")
    def patch_opportunity(opp_id: int, body: UpdateRequest, session=Depends(get_session)):
        try:
            o = db.update_workflow(session, opp_id, body.workflow_status, body.reviewer_notes)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if not o:
            raise HTTPException(404, "Opportunity not found")
        return db.to_dict(o)

    @router.get("/notifications")
    def notifications(unread_only: bool = True, session=Depends(get_session)):
        stmt = select(db.Notification).order_by(db.Notification.created_at.desc()).limit(200)
        if unread_only:
            stmt = stmt.where(db.Notification.is_read.is_(False))
        rows = session.scalars(stmt).all()
        return {"count": len(rows), "items": [{"id": n.id, "kind": n.kind, "message": n.message,
                                                "opportunity_id": n.opportunity_id,
                                                "created_at": n.created_at.isoformat()} for n in rows]}

    return router
