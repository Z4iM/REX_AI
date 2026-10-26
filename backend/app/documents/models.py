from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    document_type: Literal["course_description", "course_proposal", "participant_guide", "curriculum"]
    course_ids: list[str] = Field(min_length=1, max_length=5)
    language: Literal["en", "ar"] = "en"
    audience: str = Field(default="Prospective learners", min_length=2, max_length=240)
    requester: str = Field(min_length=2, max_length=120)
    revision_of: str | None = Field(default=None, max_length=36)
    revision_instructions: str = Field(default="", max_length=2000)

    @field_validator("course_ids")
    @classmethod
    def validate_courses(cls, value):
        from backend.app.catalog.catalog_service import COURSE_RE
        codes = [code.strip().upper() for code in value]
        if len(set(codes)) != len(codes) or any(not COURSE_RE.fullmatch(code) for code in codes):
            raise ValueError("Course IDs must be valid and unique")
        return codes


class Reviewer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    reviewer: str = Field(min_length=2, max_length=120)


class ReviewRequest(Reviewer):
    decision: Literal["approve", "reject", "request_revision"]
    reason: str = Field(min_length=1, max_length=4000)


class Section(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    heading: str = Field(min_length=1, max_length=140)
    text: str = Field(min_length=1, max_length=6000)
    source_ids: list[str] = Field(min_length=1, max_length=5)


class GeneratedContent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=3, max_length=240)
    sections: list[Section] = Field(min_length=3, max_length=12)
