"""FastAPI router for the Curriculum Research & Accreditation Alignment Agent.

Endpoints:
    GET  /api/v1/curriculum/frameworks         – list accreditation frameworks
    GET  /api/v1/curriculum/frameworks/{id}     – single framework details
    POST /api/v1/curriculum/research            – AI topic research
    POST /api/v1/curriculum                     – generate a new curriculum
    GET  /api/v1/curriculum                     – list stored curricula (with filters)
    GET  /api/v1/curriculum/{id}                – single curriculum detail
    POST /api/v1/curriculum/{id}/submit         – submit for review
    POST /api/v1/curriculum/{id}/review         – approve / request revision
    POST /api/v1/curriculum/{id}/alignment      – run accreditation alignment
    GET  /api/v1/curriculum/{id}/pdf            – download professional PDF
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from typing import Literal
from backend.app.catalog.upload_router import require_catalog_admin
from .models import CurriculumContent, Statement

from . import service


# ---- request / response models ----

class ResearchRequest(BaseModel):
    course_ids: list[str] = Field(min_length=1, max_length=5)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    subject: str = Field(min_length=2, max_length=500)
    skill_level: Literal["Beginner", "Intermediate", "Advanced"] = "Intermediate"
    industry: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=100)


class CreateCurriculumRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    subject: str = Field(min_length=2, max_length=500)
    skill_level: Literal["Beginner", "Intermediate", "Advanced"] = "Intermediate"
    target_audience: str = Field(default="", max_length=300)
    industry: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=100)
    language: Literal["English", "Arabic"] = "English"
    duration_hours: Optional[float] = Field(default=None, gt=0, le=5000)
    department: str = Field(default="", max_length=200)
    additional_requirements: str = Field(default="", max_length=4000)
    accreditation_framework_id: Optional[int] = Field(default=None, ge=1)
    course_ids: list[str] = Field(min_length=1, max_length=5)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    action: str = Field(pattern="^(approve|request_revision)$")
    reviewer_name: str = Field(min_length=2, max_length=200)
    notes: str = Field(min_length=1, max_length=4000)


class AlignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    framework_id: int = Field(ge=1)


class FrameworkReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reviewer_name: str = Field(min_length=2, max_length=200)
    source_url: HttpUrl
    source_version: str = Field(min_length=2, max_length=100)
    source_excerpt: str = Field(min_length=20, max_length=10000)
    competencies: list[Statement] = Field(min_length=1, max_length=100)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reviewer_name: str = Field(min_length=2, max_length=200)
    reason: str = Field(min_length=3, max_length=4000)
    content: CurriculumContent


# ---- router factory ----

def build_router(auth_dependency=require_catalog_admin, prefix: str = "/api/v1/curriculum") -> APIRouter:
    deps = [Depends(auth_dependency or require_catalog_admin)]
    router = APIRouter(prefix=prefix, tags=["curriculum"], dependencies=deps)

    @router.post("/frameworks/{framework_id}/approve")
    def approve_framework(framework_id: int, body: FrameworkReview):
        return service.approve_framework(framework_id, body)

    @router.post("/{curriculum_id}/revise", status_code=201)
    def revise(curriculum_id: int, body: RevisionRequest):
        return service.revise_curriculum(curriculum_id, body.content, body.reviewer_name, body.reason)

    # ---- frameworks ----

    @router.get("/frameworks")
    def list_frameworks(
        country: Optional[str] = None,
        industry: Optional[str] = None,
    ):
        return {"items": service.list_frameworks(country=country, industry=industry)}

    @router.get("/frameworks/{framework_id}")
    def get_framework(framework_id: int):
        fw = service.get_framework(framework_id)
        if not fw:
            raise HTTPException(404, "Framework not found")
        return fw

    # ---- research ----

    @router.post("/research")
    def research(body: ResearchRequest):
        return service.research_curriculum_topics(
            body.subject,
            skill_level=body.skill_level,
            industry=body.industry,
            country=body.country,
            course_ids=body.course_ids,
        )

    # ---- curriculum CRUD ----

    @router.post("", status_code=201)
    def create_curriculum(body: CreateCurriculumRequest):
        return service.create_curriculum(
            body.subject,
            skill_level=body.skill_level,
            target_audience=body.target_audience,
            industry=body.industry,
            country=body.country,
            language=body.language,
            duration_hours=body.duration_hours,
            department=body.department,
            additional_requirements=body.additional_requirements,
            accreditation_framework_id=body.accreditation_framework_id,
            course_ids=body.course_ids,
        )

    @router.get("")
    def list_curricula(
        department: Optional[str] = None,
        skill_level: Optional[str] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        items = service.list_curricula(
            department=department,
            skill_level=skill_level,
            industry=industry,
            country=country,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
        )
        return {"count": len(items), "items": items}

    @router.get("/{curriculum_id}")
    def get_curriculum(curriculum_id: int):
        c = service.get_curriculum(curriculum_id)
        if not c:
            raise HTTPException(404, "Curriculum not found")
        return c

    # ---- review workflow ----

    @router.post("/{curriculum_id}/submit")
    def submit_for_review(curriculum_id: int):
        try:
            result = service.submit_for_review(curriculum_id)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if not result:
            raise HTTPException(404, "Curriculum not found")
        return result

    @router.post("/{curriculum_id}/review")
    def review_curriculum(curriculum_id: int, body: ReviewRequest):
        try:
            result = service.review_curriculum(
                curriculum_id,
                action=body.action,
                reviewer_name=body.reviewer_name,
                notes=body.notes,
            )
        except ValueError as e:
            raise HTTPException(422, str(e))
        if not result:
            raise HTTPException(404, "Curriculum not found")
        return result

    # ---- alignment ----

    @router.post("/{curriculum_id}/alignment")
    def run_alignment(curriculum_id: int, body: AlignmentRequest):
        try:
            result = service.run_alignment(curriculum_id, body.framework_id)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if not result:
            raise HTTPException(404, "Curriculum not found")
        return result

    # ---- PDF export ----

    @router.get("/{curriculum_id}/pdf")
    def download_pdf(curriculum_id: int):
        pdf_bytes = service.export_pdf(curriculum_id)
        if not pdf_bytes:
            raise HTTPException(404, "Curriculum not found")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=curriculum_{curriculum_id}.pdf"},
        )

    return router
