from backend.app.agents.rfp.router import build_router
from uuid import uuid4
from backend.app.assistant.qualification import (
    QualificationSession,
    process_qualification,
)
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from backend.app.assistant.grounded_answer import answer_question
from backend.app.assistant.course_matcher import match_courses
from backend.app.assistant.personalized_recommendation import (
    recommend_courses,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="REX AI",
    description="Smart Academy Multi-Agent System - Sprint 1",
    version="0.1.0"
)

app.include_router(build_router())
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
# Sprint 1: In-memory conversation storage
sessions: dict[str, QualificationSession] = {}


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
        "version": "0.1.0"
    }



@app.post(
    "/api/v1/qualification",
    response_model=QualificationResponse
)
def qualification_chat(request: QualificationRequest):

    # 1. Create or retrieve the conversation session.
    if request.session_id is None:
        session_id = str(uuid4())
        session = QualificationSession()
        sessions[session_id] = session

    else:
        session_id = request.session_id
        session = sessions.get(session_id)

        if session is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation session not found"
            )

    # 2. Prevent processing a completed conversation.
    if session.completed:
        raise HTTPException(
            status_code=409,
            detail="Qualification already completed"
        )

    # 3. Process the student's message.
    result = process_qualification(
        session,
        request.message
    )

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

def qualification_chat(request: QualificationRequest):

    # First message: create a new conversation.
    if request.session_id is None:
        session_id = str(uuid4())
        session = QualificationSession()

        sessions[session_id] = session

    else:
        # Existing conversation: retrieve its state.
        session_id = request.session_id

        session = sessions.get(session_id)

        if session is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation session not found"
            )

    if session.completed:
        raise HTTPException(
            status_code=409,
            detail="Qualification already completed"
        )

    # Process the message and update the session.
    result = process_qualification(
        session,
        request.message
    )

    return QualificationResponse(
        session_id=session_id,
        status=result["status"],
        reply=result["reply"],
        profile=result["profile"],
        query=result["query"],
        course_matches=matches,
        matching_error=matching_error,
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

@app.post(
    "/api/v1/qualification/{session_id}/recommendation",
    response_model=PersonalizedRecommendationResponse
)
async def generate_personalized_recommendation(
    session_id: str
):
    # 1. Find the conversation.
    session = sessions.get(session_id)

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
