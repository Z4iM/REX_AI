
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL",
    "gemini-embedding-2"
)

DIMENSIONS = int(
    os.getenv("EMBEDDING_DIMENSIONS", "768")
)

COLLECTION_NAME = "rex_courses_synthetic_gemini2_768"


def search_knowledge_base(query, top_k=5):
    """Retrieve relevant chunks from the synthetic knowledge base."""

    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    if top_k < 1:
        raise ValueError("top_k must be positive")

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing")

    # 1. Connect to the existing vector database
    chroma = chromadb.PersistentClient(
        path=str(ROOT / "data/chroma")
    )

    collection = chroma.get_collection(
        name=COLLECTION_NAME,
        embedding_function=None
    )

    # 2. Validate the collection configuration
    metadata = collection.metadata or {}

    if (
        metadata.get("model") != MODEL
        or metadata.get("dimensions") != DIMENSIONS
    ):
        raise ValueError("Embedding configuration mismatch")

    if collection.count() == 0:
        return []

    # 3. Generate the query embedding
    gemini = genai.Client(api_key=api_key)

    # Match the custom retrieval prefix used by our
    # Sprint 1 knowledge-base builder.
    prepared_query = (
        f"task: retrieval | query: {query.strip()}"
    )

    response = gemini.models.embed_content(
        model=MODEL,
        contents=prepared_query,
        config=types.EmbedContentConfig(
            output_dimensionality=DIMENSIONS
        )
    )

    embedding = response.embeddings[0].values

    if len(embedding) != DIMENSIONS:
        raise RuntimeError("Unexpected embedding dimensions")

    # 4. Search only our synthetic test collection
    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(top_k, collection.count()),
        where={"dataset_status": "SYNTHETIC"},
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    # 5. Convert ChromaDB output into easy-to-use records
    matches = []

    for chunk_id, document, meta, distance in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        if meta.get("approval_status") != "unapproved":
            continue

        matches.append({
            "chunk_id": chunk_id,
            "course_title": meta["course_title"],
            "course_id": meta["course_id"],
            "section": meta["section"],
            "source_file": meta["source_file"],
            "distance": float(distance),
            "content": document
        })

    return matches


if __name__ == "__main__":
    questions = [
        "I am a beginner and want to learn data analysis",
        "Which course requires Python knowledge?",
        "عايز أتعلم تحليل البيانات من الصفر"
    ]

    for question in questions:
        print("\n" + "=" * 65)
        print("QUESTION:", question)
        print("=" * 65)

        matches = search_knowledge_base(
            question,
            top_k=3
        )

        for index, match in enumerate(matches, 1):
            print(f"\nRESULT {index}")
            print("Course:", match["course_title"])
            print("Section:", match["section"])
            print("Source:", match["source_file"])
            print("Distance:", round(match["distance"], 4))
            print("Content:", match["content"][:250])
