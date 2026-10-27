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
from pydantic import BaseModel, ConfigDict, Field

from . import service


# ---- request / response models ----

class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=2, max_length=500)
    skill_level: str = "Intermediate"
    industry: str = ""
    country: str = ""


class CreateCurriculumRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=2, max_length=500)
    skill_level: str = "Intermediate"
    target_audience: str = ""
    industry: str = ""
    country: str = ""
    language: str = "English"
    duration_hours: Optional[float] = None
    department: str = ""
    additional_requirements: str = ""
    accreditation_framework_id: Optional[int] = None
    research_context: Optional[dict] = None


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(pattern="^(approve|request_revision)$")
    reviewer_name: str = Field(min_length=2, max_length=200)
    notes: str = ""


class AlignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    framework_id: int


# ---- router factory ----

def build_router(auth_dependency=None, prefix: str = "/api/v1/curriculum") -> APIRouter:
    deps = [Depends(auth_dependency)] if auth_dependency else []
    router = APIRouter(prefix=prefix, tags=["curriculum"], dependencies=deps)

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
            research_context=body.research_context,
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
