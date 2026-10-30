from backend.app.assistant.session_store import advance_session, get_session, delete_session
from backend.app.assistant.leads import LeadRequest, save_lead, delete_lead
import logging
import sqlite3
from sqlalchemy.exc import SQLAlchemyError
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from backend.app.catalog.approved_answer import answer_approved_question as answer_question
from backend.app.assistant.course_matcher import match_courses
from backend.app.catalog.upload_router import router as catalog_router
from backend.app.assistant.personalized_recommendation import (
    recommend_courses,
)
from backend.app.catalog.approval_router import (
    staff_router,
    public_router,
)
from backend.app.documents.router import router as documents_router
from backend.app.integrations.rfp import router as rfp_router, extra_router as rfp_extra_router
from backend.app import runtime
from backend.app.integrations.demo import router as demo_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="REX AI",
    description="Sprint 2 — approved course assistant and staff document generation",
    version="0.2.0"
)
app.include_router(catalog_router)
app.include_router(staff_router)
app.include_router(public_router)
app.include_router(documents_router)
app.include_router(rfp_router)
app.include_router(rfp_extra_router)
app.include_router(demo_router)


@app.get("/api/v1/system")
def system_status():
    return {"mode": "demo" if runtime.is_demo() else "academy", "data_origin": runtime.origin(),
            "notice": "TA DEMO: all course and tender examples are fictional." if runtime.is_demo()
            else "Academy mode: only reviewed, published course information is shown."}


@app.exception_handler(SQLAlchemyError)
@app.exception_handler(sqlite3.OperationalError)
async def database_unavailable(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Application storage is temporarily unavailable; please retry"})


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


class QualificationRequest(ChatRequest):
    session_id: str | None = None



class QualificationResponse(BaseModel):
    session_id: str
    status: str
    reply: str
    profile: dict[str, str | None]
    query: str | None = None

    # New: course matching results
    course_matches: list[dict] | None = None
    matching_error: str | None = None


# Response models
class SourceReference(BaseModel):
    source_id: str
    course: str
    section: str
    file: str
    excerpt: str
    course_id: str | None = None
    source_sha256: str | None = None
    approval_revision: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    mode: str
    disclaimer: str

class PersonalizedRecommendationResponse(BaseModel):
    session_id: str
    status: str
    answer: str
    eligible_courses: list[dict]
    needs_verification: list[dict]
    excluded_courses: list[dict]
    sources: list[dict]
    mode: str



# Health check
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "REX AI Backend",
        "version": "0.2.0"
    }



@app.post(
    "/api/v1/qualification",
    response_model=QualificationResponse
)
def qualification_chat(request: QualificationRequest):

    session_id, result = advance_session(request.session_id, request.message)

    # 4. Initialize variables for EVERY request.
    matches = None
    matching_error = None

    # 5. Match courses only when qualification finishes.
    if result["status"] == "ready":
        try:
            matches = match_courses(result["profile"])

        except ValueError as exc:
            matching_error = str(exc)

    # 6. Return the response.
    return QualificationResponse(
        session_id=session_id,
        status=result["status"],
        reply=result["reply"],
        profile=result["profile"],
        query=result["query"],
        course_matches=matches,
        matching_error=matching_error
    )


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
            mode="APPROVED_CATALOG",
            disclaimer=(
                "Answers use published, staff-reviewed course information. "
                "Missing information requires confirmation from academy staff."
            )
        )

    except Exception:
        logger.exception("REX Assistant request failed")

        raise HTTPException(
            status_code=503,
            detail="REX Assistant is temporarily unavailable."
        )

@app.post(
    "/api/v1/qualification/{session_id}/recommendation",
    response_model=PersonalizedRecommendationResponse
)
async def generate_personalized_recommendation(
    session_id: str
):
    # 1. Find the conversation.
    session = get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation session not found"
        )

    # 2. Require a completed learner profile.
    if not session.completed:
        raise HTTPException(
            status_code=409,
            detail="Complete learner qualification first"
        )

    # 3. Generate the personalized recommendation.
    try:
        result = await run_in_threadpool(
            recommend_courses,
            session.answers.copy(),
            session.initial_request or "",
            session.language,
        )

    except Exception:
        logger.exception(
            "Personalized recommendation generation failed"
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Recommendation service is temporarily unavailable. "
                "Please try again later."
            )
        )

    # 4. Return the validated recommendation.
    return PersonalizedRecommendationResponse(
        session_id=session_id,
        **result
    )


@app.delete("/api/v1/qualification/{session_id}", status_code=204)
def forget_qualification(session_id: str):
    """The holder of a session token can delete their stored learner profile."""
    delete_session(session_id)


@app.post("/api/v1/qualification/{session_id}/lead", status_code=201)
def capture_learner_lead(session_id: str, body: LeadRequest):
    return save_lead(session_id, body)


@app.delete("/api/v1/qualification/{session_id}/lead", status_code=204)
def remove_learner_lead(session_id: str):
    """The original private session token can revoke follow-up consent even after session expiry."""
    delete_lead(session_id)
