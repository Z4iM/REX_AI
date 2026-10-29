"""Bounded provider adapters; no fabricated fallback or remote error leakage."""
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
    if provider() == "groq":
        return groq_json(system, payload)
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


def provider():
    value = os.getenv("REX_AI_PROVIDER", "gemini").strip().lower()
    if value not in {"gemini", "groq"}:
        raise HTTPException(503, "REX_AI_PROVIDER must be groq or gemini")
    return value


def groq_completion(system, payload, *, search=False):
    import requests
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "GROQ_API_KEY is not configured; save it locally and restart the backend")
    try:
        timeout = int(os.getenv("REX_AI_TIMEOUT_SECONDS", "90"))
        if not 10 <= timeout <= 150:
            raise ValueError()
    except ValueError:
        raise HTTPException(503, "REX_AI_TIMEOUT_SECONDS must be between 10 and 150") from None
    body = {"model": os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-20b"),
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            "temperature": 0.1, "max_completion_tokens": 8192, "reasoning_effort": "low"}
    if search:
        if os.getenv("REX_ENABLE_AI_WEB_SEARCH", "0") != "1":
            raise HTTPException(503, "AI web search is disabled. Import official portal exports, or explicitly enable provider search after checking account pricing.")
        body["tools"] = [{"type": "browser_search"}]
        body["tool_choice"] = "required"
    else:
        body["response_format"] = {"type": "json_object"}
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions",
                                 headers={"Authorization": "Bearer " + key}, json=body, timeout=(10, timeout))
        if response.status_code == 429:
            raise HTTPException(503, "Groq free-tier rate limit reached. Wait and retry, or check account limits; changing keys does not remove account quotas.")
        if response.status_code in (401, 403):
            raise HTTPException(503, "Groq rejected the API key or model access. Check the key and model permissions locally.")
        if response.status_code == 413:
            raise HTTPException(503, "The provider request exceeds the account's request size limit. Reduce the requested context or use a model with a larger allowance.")
        response.raise_for_status()
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Truncated AI response")
        return choice["message"]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"AI generation unavailable ({type(exc).__name__}); please retry") from None


def groq_json(system, payload):
    message = groq_completion(system, payload)
    try:
        value = json.loads(message["content"])
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "AI returned invalid structured content; please retry") from None
