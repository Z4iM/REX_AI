"""Staff-only sample staging. Fixtures never approve or publish themselves."""
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath
import json
import os
import zipfile
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError
from backend.app import runtime
from backend.app.catalog.upload_router import require_catalog_admin, _write_and_prepare, MAX_BYTES, ALLOWED_EXTENSIONS
from backend.app.catalog.metadata_extraction import ExtractionRequest, extract_metadata
from backend.app.documents.models import Reviewer
from backend.app.integrations.rfp import ImportRequest, import_opportunities

MAX_PACK_BYTES = 50 * 1024 * 1024
PACK_DIRECTORIES = {"courses", "course_content", "negative_cases", "reference_materials", "workflow_requests"}
PACK_ROOT_FILES = {"README.md", "course_manifest.json", "learner_profiles.json", "rfp_ta_upload.json", "tenders.json"}
PACK_EXTENSIONS = ALLOWED_EXTENSIONS | {".json", ".csv"}


class SampleCourse(BaseModel):
    file: str = Field(min_length=1, max_length=240)


class SampleManifest(BaseModel):
    courses: list[SampleCourse] = Field(min_length=1, max_length=100)


def sample_file(root, relative):
    """Only bounded, ordinary files physically inside the configured pack."""
    name = PurePosixPath(relative)
    if (name.is_absolute() or PureWindowsPath(relative).drive or "\\" in relative
            or ".." in name.parts or not name.parts):
        raise HTTPException(422, "Sample pack contains an unsafe file path")
    path = root.joinpath(*name.parts)
    if any(root.joinpath(*name.parts[:i]).is_symlink() for i in range(1, len(name.parts) + 1)):
        raise HTTPException(422, "Sample pack must not contain symbolic links")
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise HTTPException(422, "A required sample file is missing or outside the sample pack")
    if resolved.stat().st_size > MAX_BYTES:
        raise HTTPException(413, "Each sample file must be at most 10 MiB")
    return resolved


def sample_json(root, name):
    try:
        return json.loads(sample_file(root, name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(422, "Sample pack contains missing, unreadable or invalid JSON") from None


def examples_dir():
    configured = os.getenv("REX_DEMO_EXAMPLES_DIR", "").strip()
    if not configured:
        raise HTTPException(503, "Configure REX_DEMO_EXAMPLES_DIR with an external sample pack directory and restart the backend")
    path = Path(configured).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise HTTPException(503, "REX_DEMO_EXAMPLES_DIR must be an existing absolute directory")
    return path

def demo_only():
    if not runtime.is_demo():
        raise HTTPException(409, "Start Demo mode to use fictional examples")

router = APIRouter(prefix="/api/v1/demo", tags=["demo"], dependencies=[Depends(require_catalog_admin), Depends(demo_only)])

@router.post("/stage-courses")
def stage_courses(body: Reviewer):
    examples = examples_dir()
    try:
        manifest = SampleManifest.model_validate(sample_json(examples, "course_manifest.json"))
    except ValidationError:
        raise HTTPException(422, "Sample course manifest requires between 1 and 100 course file entries") from None
    # Validate the whole manifest before changing persistent state.
    sources = []
    total = 0
    for example in manifest.courses:
        path = sample_file(examples, example.file)
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(415, "Sample courses must be PDF, DOCX or MD")
        raw = path.read_bytes()
        if (not raw or (path.suffix.lower() == ".pdf" and not raw.startswith(b"%PDF-"))
                or (path.suffix.lower() == ".docx" and not zipfile.is_zipfile(BytesIO(raw)))):
            raise HTTPException(422, "A sample course is empty or has an invalid file format")
        total += len(raw)
        if total > MAX_PACK_BYTES:
            raise HTTPException(413, "Sample courses exceed the 50 MiB pack limit")
        sources.append((path, raw))
    items = []
    for path, raw in sources:
        try:
            record, duplicate = _write_and_prepare(raw, path.name, path.suffix.lower(), False)
        except (ValueError, RuntimeError, OSError):
            raise HTTPException(422, "Could not extract a sample course; check its contents") from None
        # Preserve previous human decisions, including rejections.
        if not duplicate and record["review_status"] == "pending_review":
            extract_metadata(record["upload_id"], ExtractionRequest(reviewer=body.reviewer))
        items.append({"upload_id": record["upload_id"], "filename": path.name,
                      "already_loaded": duplicate, "review_status": record["review_status"]})
    return {"items": items, "notice": "Loaded for human review. No courses were approved or published."}

@router.post("/stage-tenders")
def stage_tenders():
    try:
        data = sample_json(examples_dir(), "tenders.json")
        items = data["items"]
        for item in items:
            item["publication_date"] = str(date.today() - timedelta(days=2))
            item["deadline"] = str(date.today() + timedelta(days=-1 if "Expired" in item["title"] else 60))
        request = ImportRequest(items=items, use_gemini=False)
    except (ValidationError, KeyError, TypeError):
        raise HTTPException(422, "Sample tenders must contain a valid opportunity items list") from None
    return import_opportunities(request)

@router.get("/examples.zip")
def examples_zip():
    examples = examples_dir()
    stream = BytesIO()
    total = 0
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(examples.rglob("*")):
            name = path.relative_to(examples)
            # Never bundle arbitrary operator files, credentials or runtime databases.
            if (path.suffix.lower() not in PACK_EXTENSIONS
                    or any(part.startswith(".") for part in name.parts)
                    or (len(name.parts) == 1 and name.name not in PACK_ROOT_FILES)
                    or (len(name.parts) > 1 and name.parts[0] not in PACK_DIRECTORIES)):
                continue
            checked = sample_file(examples, name.as_posix())
            total += checked.stat().st_size
            if total > MAX_PACK_BYTES:
                raise HTTPException(413, "Sample pack exceeds the 50 MiB download limit")
            archive.write(checked, name.as_posix())
    return Response(stream.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="rex-demo-examples.zip"'})
