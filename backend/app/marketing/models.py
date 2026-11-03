from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

CHANNELS = Literal["social_caption", "facebook_instagram", "linkedin", "email", "whatsapp", "headline", "cta"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class ChannelContent(StrictModel):
    channel: CHANNELS
    variations: list[str] = Field(min_length=2, max_length=5)


class CampaignContent(StrictModel):
    title: str = Field(min_length=3, max_length=240)
    strategy: str = Field(min_length=20, max_length=6000)
    channels: list[ChannelContent] = Field(min_length=1, max_length=7)


class CampaignRequest(StrictModel):
    course_id: str = Field(min_length=2, max_length=40)
    curriculum_id: int = Field(ge=1)
    requester: str = Field(min_length=2, max_length=120)
    audience: str = Field(min_length=3, max_length=400)
    objective: str = Field(min_length=3, max_length=1000)
    language: Literal["en", "ar"] = "en"
    channels: list[CHANNELS] = Field(min_length=1, max_length=7)
    budget_egp: float | None = Field(default=None, ge=0, le=10000000)
    revision_of: str | None = Field(default=None, max_length=36)
    revision_instructions: str = Field(default="", max_length=4000)
    edited_content: CampaignContent | None = None


class CampaignReview(StrictModel):
    reviewer: str = Field(min_length=2, max_length=120)
    decision: Literal["approve", "reject", "request_revision"]
    reason: str = Field(min_length=3, max_length=4000)
