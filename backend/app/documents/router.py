from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from backend.app.catalog.upload_router import require_catalog_admin
from .models import GenerationRequest, ReviewRequest, Reviewer
from . import service

router = APIRouter(prefix="/api/v1/documents", tags=["document-agent"],
                   dependencies=[Depends(require_catalog_admin)])


@router.get("/templates")
def templates():
    return {"items": service.list_templates()}


@router.post("/templates/{template_id}/approve")
def approve_template(template_id: str, body: Reviewer):
    return service.approve_template(template_id, body.reviewer)


@router.post("", status_code=201)
def generate_document(body: GenerationRequest):
    return service.generate_document(body)


@router.get("")
def documents():
    return {"items": service.list_documents()}


@router.get("/{artifact_id}")
def document(artifact_id: str):
    return service.get_document(artifact_id)


@router.post("/{artifact_id}/review")
def review_document(artifact_id: str, body: ReviewRequest):
    return service.review_document(artifact_id, body)


@router.get("/{artifact_id}/download/{fmt}")
def download_document(artifact_id: str, fmt: str):
    path = service.file_path(artifact_id, fmt)
    media_type = "application/pdf" if fmt == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path, media_type=media_type, filename=f"rex-{artifact_id}.{fmt}")
