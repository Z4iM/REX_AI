
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from backend.app.assistant.grounded_answer import answer_question


logger = logging.getLogger(__name__)

app = FastAPI(
    title="REX AI",
    description="Smart Academy Multi-Agent System - Sprint 1",
    version="0.1.0"
)


# Request model
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Message cannot be empty")

        # Reject messages containing only punctuation or symbols.
        # isalnum() supports Arabic, English, and numbers.
        if not any(char.isalnum() for char in value):
            raise ValueError(
                "Message must contain meaningful text or numbers"
            )

        return value


# Response models
class SourceReference(BaseModel):
    source_id: str
    course: str
    section: str
    file: str
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    mode: str
    disclaimer: str


# Health check
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "REX AI Backend",
        "version": "0.1.0"
    }


# REX Assistant endpoint
@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Gemini is synchronous, so run it in a
        # worker thread to avoid blocking the API.
        result = await run_in_threadpool(
            answer_question,
            request.message
        )

        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            mode="SYNTHETIC_DEMO",
            disclaimer=(
                "Synthetic demonstration data only. "
                "Courses are not verified academy offerings."
            )
        )

    except Exception:
        logger.exception("REX Assistant request failed")

        raise HTTPException(
            status_code=503,
            detail="REX Assistant is temporarily unavailable."
        )
