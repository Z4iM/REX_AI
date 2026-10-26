"""Secure course-document staging; deliberately does not approve or index content.

Source text is never automatically published to RAG or to the course catalog.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import zipfile
from pathlib import Path, PureWindowsPath
from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.app.ingestion.document_review import prepare_document_for_review
from backend.app import runtime

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
MAX_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md"}
UPLOAD_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def data_dir() -> Path:
    return runtime.catalog_dir()


def require_catalog_admin(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = os.environ.get("REX_CATALOG_ADMIN_KEY")
    if not expected:
        raise HTTPException(503, "Course catalog administration is not configured")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid or missing admin API key")


router = APIRouter(prefix="/api/v1/catalog", tags=["catalog-admin"],
                   dependencies=[Depends(require_catalog_admin)])


def _load_manifest(upload_id: str) -> dict:
    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
        raise HTTPException(404, "Upload not found")
    manifest = data_dir() / "uploads" / upload_id / "review.json"
    if not manifest.is_file():
        raise HTTPException(404, "Upload not found")
    return json.loads(manifest.read_text(encoding="utf-8"))


def _summarize(record: dict) -> dict:
    return {key: record[key] for key in (
        "upload_id", "filename", "file_type", "source_sha256", "review_status",
        "approval_status", "chunk_count", "extraction_warnings", "missing_pages",
    )}


def _write_and_prepare(raw: bytes, name: str, suffix: str, enable_ocr: bool) -> tuple[dict, bool]:
    from .catalog_service import catalog_transaction

    # A concurrent duplicate upload must never overwrite a review decision.
    with catalog_transaction():
        return _write_and_prepare_locked(raw, name, suffix, enable_ocr)


def _write_and_prepare_locked(raw: bytes, name: str, suffix: str, enable_ocr: bool) -> tuple[dict, bool]:
    digest = hashlib.sha256(raw).hexdigest()
    directory = data_dir() / "uploads" / digest
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "review.json"
    if manifest_path.is_file():
        return json.loads(manifest_path.read_text(encoding="utf-8")), True

    source_path = directory / ("source" + suffix)
    source_path.write_bytes(raw)
    try:
        package = prepare_document_for_review(source_path, enable_ocr=enable_ocr)
        if not runtime.is_demo() and any("REX_SYNTHETIC_DEMO" in c["text"] for c in package["chunks"]):
            raise HTTPException(409, "This is a demo fixture. Start Demo mode before uploading it.")
        record = {
            "upload_id": digest,
            "filename": name,
            "file_type": suffix.lstrip("."),
            "source_sha256": digest,
            "review_status": package["review_status"],
            "approval_status": "unapproved",
            "data_origin": runtime.origin(),
            "indexing_allowed": False,
            "missing_pages": package["missing_pages"],
            "extraction_warnings": package["extraction_warnings"],
            "extraction_review_required": package["extraction_review_required"],
            "chunk_count": package["chunk_count"],
            "chunks": package["chunks"],
        }
        tmp = directory / "review.json.tmp"
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(manifest_path)
        return record, False
    except Exception:
        # Prevent a failed extraction from being mistaken for an upload.
        if not manifest_path.exists():
            shutil.rmtree(directory, ignore_errors=True)
        raise


@router.post("/uploads", status_code=201)
async def upload_course_document(
    file: Annotated[UploadFile, File(description="One course document: PDF, DOCX or Markdown")],
    enable_ocr: Annotated[bool, Form()] = False,
):
    filename = PureWindowsPath(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Supported file types: PDF, DOCX, MD")

    content = bytearray()
    try:
        while True:
            piece = await file.read(1024 * 1024)
            if not piece:
                break
            if len(content) + len(piece) > MAX_BYTES:
                raise HTTPException(413, "Maximum upload size is 10 MiB")
            content.extend(piece)
    finally:
        await file.close()

    if not content:
        raise HTTPException(422, "Document is empty")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(422, "File is not a PDF")
    if suffix == ".docx" and not zipfile.is_zipfile(__import__("io").BytesIO(content)):
        raise HTTPException(422, "File is not a DOCX document")

    try:
        record, existing = await run_in_threadpool(
            _write_and_prepare, bytes(content), filename, suffix, enable_ocr
        )
    except (ValueError, RuntimeError, OSError) as exc:
        # Invalid/corrupt files, unreadable OCR content, and parser errors.
        raise HTTPException(422, f"Could not extract document: {exc}") from exc

    return {
        **_summarize(record),
        "already_uploaded": existing,
        "message": ("This document was rejected. Upload a corrected source for a new review."
                    if record["review_status"] == "rejected" else
                    "Saved for staff review. Not indexed in RAG or published to the catalog."),
    }


@router.get("/uploads")
def list_course_uploads():
    root = data_dir() / "uploads"
    items = []
    if root.is_dir():
        for manifest in root.glob("*/review.json"):
            try:
                items.append(_summarize(json.loads(manifest.read_text(encoding="utf-8"))))
            except (OSError, ValueError, KeyError):
                continue
    return {"count": len(items), "items": sorted(items, key=lambda x: x["filename"])}


@router.get("/uploads/{upload_id}")
def get_course_upload(upload_id: str):
    record = _load_manifest(upload_id)
    return {
        **_summarize(record),
        "indexing_allowed": False,
        "chunks": record["chunks"],
        "rejected_by": record.get("rejected_by"),
        "rejected_at": record.get("rejected_at"),
        "rejection_reason": record.get("rejection_reason"),
        "review_history": record.get("review_history", []),
        "metadata_suggestions": record.get("metadata_suggestions"),
    }
