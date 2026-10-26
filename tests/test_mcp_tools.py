"""Real MCP registration, authorization and stdio protocol smoke test."""
import asyncio
import os
import sys
import pytest
from fastapi import HTTPException
from backend.app import mcp_server as server


def test_public_tools_only_return_published_courses(published_course):
    assert server.search_courses("Python")[0]["course_id"] == "PY-101"
    assert server.get_course_details("PY-101")["status"] == "published"
    from backend.app.catalog.catalog_service import withdraw_course
    withdraw_course("PY-101", "Reviewer")
    assert server.search_courses("Python") == []
    with pytest.raises(HTTPException) as exc:
        server.get_course_details("PY-101")
    assert exc.value.status_code == 404


def test_staff_tools_fail_closed(staff_headers, monkeypatch):
    monkeypatch.delenv("REX_MCP_STAFF_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        server.get_document_templates()
    assert exc.value.status_code == 401
    monkeypatch.setenv("REX_MCP_STAFF_KEY", staff_headers["X-API-Key"])
    assert len(server.get_document_templates()) == 3


def test_mcp_stdio_protocol_and_tool_schemas():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "backend.app.mcp_server"], env=dict(os.environ))
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                result = await session.list_tools()
                names = {tool.name for tool in result.tools}
                assert names == {"search_courses", "get_course_details", "retrieve_course_documents",
                                 "get_document_templates", "generate_document_draft", "save_lead"}
                assert not (await session.call_tool("search_courses", {"query": "Python"})).isError
                assert (await session.call_tool("retrieve_course_documents", {"query": "Python", "limit": 999})).isError
    asyncio.run(run())
