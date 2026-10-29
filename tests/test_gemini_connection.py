"""Explicit opt-in Gemini embedding smoke test; no calls during collection."""
import os
import pytest

pytestmark = pytest.mark.skipif(os.getenv("REX_RUN_LIVE_TESTS") != "1", reason="Live Gemini quota usage is explicitly opt-in")


def test_live_gemini_embedding_dimensions():
    from google import genai
    from google.genai import types
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        pytest.skip("Configure GEMINI_API_KEY locally for the optional Gemini check")
    dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=45000)) as client:
        response = client.models.embed_content(
            model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2"),
            contents="Synthetic embedding connectivity check: Python learning objectives.",
            config=types.EmbedContentConfig(output_dimensionality=dimensions))
    assert response.embeddings and len(response.embeddings[0].values) == dimensions
    assert all(isinstance(value, (int, float)) for value in response.embeddings[0].values)
