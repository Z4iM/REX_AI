
import hashlib
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

from backend.app.ingestion.markdown_loader import load_markdown
from backend.app.ingestion.course_normalizer import normalize_document
from backend.app.rag.chunker import chunk_courses


ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
API_KEY = os.getenv("GEMINI_API_KEY")

COLLECTION_NAME = "rex_courses_synthetic_gemini2_768"
BATCH_SIZE = 8


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_courses():
    files = [
        ROOT / "data/samples/course_catalog.md",
        ROOT / "data/samples/alternative_catalog.md",
    ]

    courses = []

    for file in files:
        document = load_markdown(file)
        courses.extend(normalize_document(document))

    return courses


def build_knowledge_base():
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY is missing")

    if MODEL != "gemini-embedding-2" or DIMENSIONS != 768:
        raise ValueError("This test collection requires Gemini 2 / 768")

    # 1. Load and chunk documents
    courses = load_courses()
    chunks = chunk_courses(courses)

    print(f"Courses loaded: {len(courses)}")
    print(f"Chunks prepared: {len(chunks)}")

    # Keep this collection exclusively for synthetic tests.
    for chunk in chunks:
        metadata = chunk["metadata"]
        if metadata["dataset_status"].upper() != "SYNTHETIC":
            raise ValueError("Only synthetic test data is allowed")

    # 2. Initialize persistent ChromaDB
    db_path = ROOT / "data/chroma"
    db_path.mkdir(parents=True, exist_ok=True)

    chroma_client = chromadb.PersistentClient(
        path=str(db_path)
    )

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
        metadata={
            "model": MODEL,
            "dimensions": DIMENSIONS,
            "dataset_status": "SYNTHETIC",
        }
    )

    if (
        collection.metadata.get("model") != MODEL
        or collection.metadata.get("dimensions") != DIMENSIONS
    ):
        raise ValueError("Existing collection configuration mismatch")

    # 3. Avoid re-embedding unchanged chunks
    existing = collection.get(
        ids=[chunk["chunk_id"] for chunk in chunks],
        include=["metadatas"]
    )

    saved_hashes = {
        chunk_id: metadata.get("text_sha256")
        for chunk_id, metadata in zip(
            existing["ids"],
            existing["metadatas"] or []
        )
    }

    pending = [
        chunk for chunk in chunks
        if saved_hashes.get(chunk["chunk_id"])
        != content_hash(chunk["text"])
    ]

    print(f"Chunks requiring embeddings: {len(pending)}")

    # 4. Generate embeddings in small batches
    if pending:
        gemini = genai.Client(api_key=API_KEY)

        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]

            # Each Content must produce its own embedding.
            contents = [
                types.Content(parts=[
                    types.Part.from_text(
                        text="task: retrieval | document: "
                        + chunk["text"]
                    )
                ])
                for chunk in batch
            ]

            response = gemini.models.embed_content(
                model=MODEL,
                contents=contents,
                config=types.EmbedContentConfig(
                    output_dimensionality=DIMENSIONS
                )
            )

            embeddings = [
                item.values for item in response.embeddings
            ]

            if len(embeddings) != len(batch):
                raise RuntimeError("Embedding count mismatch")

            if any(len(e) != DIMENSIONS for e in embeddings):
                raise RuntimeError("Embedding dimension mismatch")

            # 5. Save embeddings, text, and metadata
            collection.upsert(
                ids=[c["chunk_id"] for c in batch],
                documents=[c["text"] for c in batch],
                embeddings=embeddings,
                metadatas=[
                    {
                        **c["metadata"],
                        "text_sha256": content_hash(c["text"])
                    }
                    for c in batch
                ]
            )

            print(f"Stored batch: {len(batch)} chunks")

    # 6. Verify persistence
    print("\nKnowledge base ready!")
    print("Collection:", collection.name)
    print("Total stored chunks:", collection.count())
    print("Database location:", db_path)

    assert collection.count() >= len(chunks)


if __name__ == "__main__":
    build_knowledge_base()
