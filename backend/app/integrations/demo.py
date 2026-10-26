"""Staff-only TA setup. Fixtures never approve or publish themselves."""
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import json
import zipfile
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from backend.app import runtime
from backend.app.catalog.upload_router import require_catalog_admin, _write_and_prepare
from backend.app.catalog.metadata_extraction import ExtractionRequest, extract_metadata
from backend.app.documents.models import Reviewer
from backend.app.integrations.rfp import ImportRequest, import_opportunities

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "ta_demo"

def demo_only():
    if not runtime.is_demo():
        raise HTTPException(409, "Start Demo mode to use fictional examples")

router = APIRouter(prefix="/api/v1/demo", tags=["ta-demo"], dependencies=[Depends(require_catalog_admin), Depends(demo_only)])

@router.post("/stage-courses")
def stage_courses(body: Reviewer):
    manifest = json.loads((EXAMPLES / "course_manifest.json").read_text(encoding="utf-8"))
    items = []
    for example in manifest["courses"]:
        path = EXAMPLES / example["file"]
        record, duplicate = _write_and_prepare(path.read_bytes(), path.name, path.suffix, False)
        # Preserve previous human decisions, including rejections.
        if not duplicate and record["review_status"] == "pending_review":
            extract_metadata(record["upload_id"], ExtractionRequest(reviewer=body.reviewer))
        items.append({"upload_id": record["upload_id"], "filename": path.name,
                      "already_loaded": duplicate, "review_status": record["review_status"]})
    return {"items": items, "notice": "Loaded for human review. No courses were approved or published."}

@router.post("/stage-tenders")
def stage_tenders():
    items = json.loads((EXAMPLES / "tenders.json").read_text(encoding="utf-8"))["items"]
    for item in items:
        item["publication_date"] = str(date.today() - timedelta(days=2))
        item["deadline"] = str(date.today() + timedelta(days=-1 if "Expired" in item["title"] else 60))
    return import_opportunities(ImportRequest(items=items, use_gemini=False))

@router.get("/examples.zip")
def examples_zip():
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EXAMPLES.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(EXAMPLES).as_posix())
    return Response(stream.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="rex-ta-demo-examples.zip"'})
