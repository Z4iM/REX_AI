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
              "Curriculum/RFP/Marketing integration is not provided by this server.")


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
def generate_document_draft(document_type: Literal["course_description", "course_proposal", "participant_guide"],
                            course_ids: list[str], requester: str, language: Literal["en", "ar"] = "en",
                            audience: str = "Prospective learners") -> dict:
    """Staff-only real generation of a persisted draft; this tool cannot approve or publish it."""
    _staff()
    return documents.generate_document(GenerationRequest(document_type=document_type, course_ids=course_ids,
                                        requester=requester, language=language, audience=audience))


if __name__ == "__main__":
    mcp.run(transport="stdio")
