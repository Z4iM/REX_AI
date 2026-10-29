import json
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from backend.app.catalog.upload_router import require_catalog_admin
from . import service
from .models import CampaignRequest, CampaignReview

router = APIRouter(prefix="/api/v1/marketing", tags=["marketing"], dependencies=[Depends(require_catalog_admin)])


@router.get("")
def list_campaigns():
    return {"items": service.list_campaigns()}


@router.post("", status_code=201)
def create_campaign(body: CampaignRequest):
    return service.generate_campaign(body)


@router.get("/{campaign_id}")
def campaign(campaign_id: str):
    return service.get_campaign(campaign_id)


@router.post("/{campaign_id}/review")
def review(campaign_id: str, body: CampaignReview):
    return service.review_campaign(campaign_id, body)


@router.get("/{campaign_id}/export")
def export(campaign_id: str):
    record = service.export_campaign(campaign_id)
    return Response(json.dumps(record, ensure_ascii=False, indent=2).encode(), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="campaign-{campaign_id}.json"'})
