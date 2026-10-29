import json
import pytest
from fastapi import HTTPException
from backend.app import ai


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_provider_errors_are_sanitized(monkeypatch, status):
    import requests
    monkeypatch.setenv("REX_AI_PROVIDER", "groq"); monkeypatch.setenv("GROQ_API_KEY", "private-test-key")
    def request(*a, **kw):
        response = requests.Response(); response.status_code = status; response._content = b'{"error":"private-test-key"}'
        return response
    monkeypatch.setattr(requests, "post", request)
    with pytest.raises(HTTPException) as exc:
        ai.generate_json("Return JSON", {})
    assert exc.value.status_code == 503 and "private-test-key" not in exc.value.detail


def test_groq_structured_generation(monkeypatch):
    import requests
    monkeypatch.setenv("REX_AI_PROVIDER", "groq"); monkeypatch.setenv("GROQ_API_KEY", "private-test-key")
    def request(*a, **kw):
        assert kw["json"]["response_format"] == {"type": "json_object"}
        assert "tools" not in kw["json"]
        response = requests.Response(); response.status_code = 200
        response._content = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": '{"answer":"Grounded answer"}'}}]}).encode()
        return response
    monkeypatch.setattr(requests, "post", request)
    assert ai.generate_json("Return JSON", {}) == {"answer": "Grounded answer"}


def test_web_search_never_implicitly_enabled(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "private-test-key"); monkeypatch.setenv("REX_ENABLE_AI_WEB_SEARCH", "0")
    with pytest.raises(HTTPException) as exc:
        ai.groq_completion("Search", {}, search=True)
    assert "disabled" in exc.value.detail
