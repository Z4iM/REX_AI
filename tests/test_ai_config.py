import pytest
from fastapi import HTTPException
from backend.app.ai import text_config, text_http_options, generate_json


@pytest.mark.parametrize("model,level,budget", [
    ("gemini-3.8-flash", "LOW", None), ("gemini-4-argon", "LOW", None),
    ("gemini-2.5-flash", None, 0),
])
def test_documented_thinking_configuration(monkeypatch, model, level, budget):
    monkeypatch.setenv("GEMINI_TEXT_MODEL", model)
    config = text_config("System instructions")
    assert config.thinking_config.thinking_level == level
    assert config.thinking_config.thinking_budget == budget
    assert config.response_mime_type == "application/json"


def test_bounded_timeout_configuration(monkeypatch):
    monkeypatch.setenv("REX_AI_TIMEOUT_SECONDS", "90")
    assert text_http_options().timeout == 90000
    monkeypatch.setenv("REX_AI_TIMEOUT_SECONDS", "9999")
    with pytest.raises(HTTPException) as exc:
        text_http_options()
    assert exc.value.status_code == 503


def test_missing_key_has_no_fake_generation(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        generate_json("Test", {})
    assert exc.value.status_code == 503
