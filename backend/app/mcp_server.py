"""Local stdio FastMCP adapter for AbdulRahman's implemented agent services.

No network listener is started. Staff draft tools additionally require the operator
to supply REX_MCP_STAFF_KEY matching the backend catalog administrator key.
Approval, publication and outbound messaging are deliberately absent from tools.
"""
import os
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from typing import Annotated, Literal
from backend.app.catalog import catalog_service as catalog
from backend.app.catalog.approved_index import search_approved_courses
from backend.app.catalog.upload_router import require_catalog_admin
from backend.app.documents import service as documents
from backend.app.documents.models import GenerationRequest
from backend.app.assistant.leads import LeadRequest, save_lead as persist_lead

mcp = FastMCP("REX AI course and document tools", instructions=
              "Use published course data only. Draft documents require independent human approval. "
              "Staff can create curriculum and campaign drafts from approved sources. Human approval remains outside MCP.")


def _staff():
    require_catalog_admin(os.getenv("REX_MCP_STAFF_KEY"))


@mcp.tool()
def search_courses(query: Annotated[str, Field(min_length=1, max_length=1000)]) -> list[dict]:
    """Find published courses by words in their verified title/description/department."""
    words = query.casefold().split()
    return [c for c in catalog.list_courses() if any(word in
            " ".join(str(c.get(k) or "") for k in ("title", "description", "department")).casefold()
            for word in words)][:30]


@mcp.tool()
def get_course_details(course_id: str) -> dict:
    """Read the current published course record; unpublished courses are unavailable."""
    return catalog.get_course(course_id)


@mcp.tool()
def save_lead(session_id: str, name: str, consent: Literal[True], email: str | None = None,
              phone: str | None = None) -> dict:
    """Staff-only storage of a learner's explicitly consented follow-up request. Never infer consent; sends no messages."""
    _staff()
    return persist_lead(session_id, LeadRequest(name=name, email=email, phone=phone, consent=consent))


@mcp.tool()
def retrieve_course_documents(query: Annotated[str, Field(min_length=1, max_length=1000)],
                              limit: Annotated[int, Field(ge=1, le=10)] = 5) -> list[dict]:
    """Retrieve source-cited, current, verified course evidence through approved-only RAG."""
    return search_approved_courses(query, top_k=limit)


@mcp.tool()
def get_document_templates() -> list[dict]:
    """Staff-only versioned document templates and their current review state."""
    _staff()
    return documents.list_templates()


@mcp.tool()
def generate_document_draft(document_type: Literal["course_description", "course_proposal", "participant_guide", "curriculum", "facilitator_guide", "presentation_outline", "question_bank", "assessment_rubrics", "capstone_brief", "assessment_plan"],
                            course_ids: list[str], requester: str, language: Literal["en", "ar"] = "en",
                            audience: str = "Prospective learners", curriculum_id: int | None = None) -> dict:
    """Staff-only real generation of a persisted draft; this tool cannot approve or publish it."""
    _staff()
    return documents.generate_document(GenerationRequest(document_type=document_type, course_ids=course_ids,
                                        requester=requester, language=language, audience=audience, curriculum_id=curriculum_id))


@mcp.tool()
def list_approved_curricula() -> list[dict]:
    """Staff-only approved teaching plans; source revocation is checked."""
    _staff()
    from backend.app.agents.curriculum import service
    result = []
    for c in service.list_curricula(status="approved"):
        service.validate_sources(c["source_records"])
        result.append(c)
    return result


@mcp.tool()
def generate_curriculum_draft(subject: str, course_ids: list[str], duration_hours: float = 20) -> dict:
    """Staff-only proposed curriculum from published sources; cannot approve it."""
    _staff()
    from backend.app.agents.curriculum.router import CreateCurriculumRequest
    from backend.app.agents.curriculum import service
    body = CreateCurriculumRequest(subject=subject, course_ids=course_ids, duration_hours=duration_hours)
    return service.create_curriculum(**body.model_dump())


@mcp.tool()
def generate_marketing_draft(course_id: str, curriculum_id: int, requester: str, audience: str,
                             objective: str, language: Literal["en", "ar"] = "en") -> dict:
    """Staff-only campaign draft from an approved curriculum; does not approve, send or publish."""
    _staff()
    from backend.app.marketing.models import CampaignRequest
    from backend.app.marketing import service
    return service.generate_campaign(CampaignRequest(course_id=course_id, curriculum_id=curriculum_id,
        requester=requester, audience=audience, objective=objective, language=language,
        channels=["social_caption", "facebook_instagram", "linkedin", "email", "whatsapp", "headline", "cta"]))


@mcp.tool()
def list_training_opportunities(country: Literal["EG", "SA"] = "EG") -> list[dict]:
    """Staff-only country-filtered stored RFP opportunities; no external searches or messages."""
    _staff()
    from backend.app.integrations.rfp import session_factory
    from backend.app.agents.rfp import db
    with session_factory() as session:
        return [db.to_dict(o) for o in db.search_opportunities(session, country=country, limit=50)]


if __name__ == "__main__":
    mcp.run(transport="stdio")
