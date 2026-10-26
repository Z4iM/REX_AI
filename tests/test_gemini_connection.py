
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# Load environment variables from the project root
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

import pytest
if os.getenv("REX_RUN_LIVE_TESTS") != "1":
    pytest.skip("Set REX_RUN_LIVE_TESTS=1 to spend Gemini quota", allow_module_level=True)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL",
    "gemini-embedding-2"
)
DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from .env")


# Initialize Gemini client
client = genai.Client(api_key=API_KEY)

# Synthetic test text
text = """
Python for Data Analytics is a beginner course
that teaches Python, Pandas, NumPy, and data visualization.
"""

print("Connecting to Gemini...")
print("Embedding model:", MODEL)

# Generate embedding
response = client.models.embed_content(
    model=MODEL,
    contents=text,
    config=types.EmbedContentConfig(
        output_dimensionality=DIMENSIONS
    )
)

embedding = response.embeddings[0].values

print("Embedding dimensions:", len(embedding))
print("First 5 embedding values:", embedding[:5])

assert len(embedding) == DIMENSIONS
assert all(isinstance(x, (int, float)) for x in embedding)

print("\nGemini embedding test PASSED!")
