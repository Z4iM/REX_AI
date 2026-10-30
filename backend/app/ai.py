"""Bounded Gemini JSON calls with no synthetic fallback or remote error leakage."""
import json
import os
from fastapi import HTTPException


def text_http_options():
    from google.genai import types
    try:
        timeout = int(os.getenv("REX_AI_TIMEOUT_SECONDS", "90"))
        if not 10 <= timeout <= 150:
            raise ValueError()
    except ValueError:
        raise HTTPException(503, "REX_AI_TIMEOUT_SECONDS must be between 10 and 150") from None
    return types.HttpOptions(timeout=timeout * 1000)


def text_config(system=None):
    """Use documented low-latency thinking settings without changing model identity."""
    from google.genai import types
    model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash")
    thinking = None
    if model.startswith(("gemini-3.", "gemini-3-", "gemini-4")):
        thinking = types.ThinkingConfig(thinking_level="low")
    elif model.startswith("gemini-2.5-flash"):
        thinking = types.ThinkingConfig(thinking_budget=0)
    return types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                        temperature=0.1, thinking_config=thinking, max_output_tokens=8192)


def generate_json(system: str, payload: dict) -> dict:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(503, "GEMINI_API_KEY is not configured")
    from google import genai
    from google.genai import types
    try:
        client = genai.Client(api_key=key, http_options=text_http_options())
        response = client.models.generate_content(
            model=os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash"),
            contents=json.dumps(payload, ensure_ascii=False),
            config=text_config(system))
        obj = json.loads(response.text or "")
        if not isinstance(obj, dict):
            raise ValueError("JSON object required")
        return obj
    except Exception as exc:
        raise HTTPException(503, f"AI generation unavailable ({type(exc).__name__}); please retry") from None
