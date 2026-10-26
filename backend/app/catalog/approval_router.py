"""Staff-only approval, publication and withdrawal API plus public published catalog."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.app.catalog.upload_router import require_catalog_admin
from . import approved_index, catalog_service as store
from .metadata_extraction import ExtractionRequest, extract_metadata

staff_router = APIRouter(prefix="/api/v1/catalog", tags=["catalog-approval"],
                         dependencies=[Depends(require_catalog_admin)])
public_router = APIRouter(prefix="/api/v1/catalog", tags=["course-catalog"])


class WithdrawRequest(BaseModel):
    reviewer: str = Field(min_length=2, max_length=120)


@staff_router.get("/staff/session")
def staff_session():
    return {"authenticated": True}


@staff_router.get("/staff/overview")
def staff_overview():
    from backend.app.catalog.upload_router import list_course_uploads
    from backend.app.documents.service import list_documents
    return {"uploads": list_course_uploads()["items"], "courses": store.list_courses(staff=True),
            "documents": list_documents()}


@staff_router.post("/uploads/{upload_id}/extract-metadata")
def extract_course_metadata(upload_id: str, body: ExtractionRequest):
    return extract_metadata(upload_id, body)


@staff_router.post("/uploads/{upload_id}/reject")
def reject_document(upload_id: str, body: store.DocumentRejection):
    record = store.reject_upload(upload_id, body)
    return {key: record[key] for key in (
        "upload_id", "review_status", "approval_status", "indexing_allowed",
        "rejected_by", "rejected_at", "rejection_reason", "review_history",
    )}


@staff_router.post("/uploads/{upload_id}/approve")
def approve_document(upload_id: str, body: store.CourseApproval):
    return store.approve_upload(upload_id, body)


@staff_router.get("/staff/courses")
def list_staff_courses():
    items = store.list_courses(staff=True)
    return {"count": len(items), "items": items}


@staff_router.get("/staff/leads")
def list_staff_leads():
    from backend.app.assistant.leads import list_leads
    items = list_leads()
    return {"count": len(items), "items": items}


@staff_router.get("/staff/courses/{course_id}/history")
def get_staff_history(course_id: str):
    return {"items": store.course_history(course_id)}


@staff_router.post("/staff/courses/{course_id}/publish")
async def publish_document(course_id: str):
    return await run_in_threadpool(approved_index.publish_course, course_id.upper())


@staff_router.post("/staff/courses/{course_id}/withdraw")
def withdraw_document(course_id: str, body: WithdrawRequest):
    course = store.withdraw_course(course_id, body.reviewer)
    deleted = approved_index.remove_course_vectors(course_id)
    return {"course": course, "vector_cleanup_completed": deleted,
            "access_revoked": True}


@staff_router.post("/staff/courses/{course_id}/refresh-index")
async def refresh_course_index(course_id: str):
    return await run_in_threadpool(approved_index.publish_course, course_id.upper(), refresh=True)


@public_router.get("/courses")
def list_published_courses():
    items = store.list_courses()
    return {"count": len(items), "items": items}


@public_router.get("/courses/{course_id}")
def get_published_course(course_id: str):
    return store.get_course(course_id)
