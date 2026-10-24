
from copy import deepcopy

import pytest

from backend.app.rag.document_chunker import chunk_document


def sample_document():
    return {
        "source_file": "training_portfolio.pdf",
        "file_type": "pdf",
        "approval_status": "unapproved",
        "extraction_review_required": True,
        "sections": [
            {
                "title": "Page 1",
                "content": (
                    "Python for Data Analytics. "
                    "Duration: 100 hours."
                ),
                "metadata": {
                    "page_number": 1,
                    "extraction_method": "ocr",
                },
            }
        ],
    }


def test_preserves_document_metadata():
    chunks = chunk_document(sample_document())

    assert len(chunks) == 1

    metadata = chunks[0]["metadata"]

    assert metadata["source_file"] == (
        "training_portfolio.pdf"
    )
    assert metadata["page_number"] == 1
    assert metadata["extraction_method"] == "ocr"
    assert metadata["approval_status"] == "unapproved"
    assert metadata["ingestion_status"] == "pending_review"
    assert metadata["extraction_review_required"] is True


def test_large_document_is_split():
    document = sample_document()

    document["sections"][0]["content"] = (
        "Python data engineering and machine learning. " * 300
    )

    chunks = chunk_document(
        document,
        max_tokens=120,
        overlap_tokens=20,
    )

    assert len(chunks) > 1
    assert all(
        chunk["token_count"] <= 120
        for chunk in chunks
    )


def test_chunk_ids_are_deterministic():
    document = sample_document()

    first = chunk_document(document)
    second = chunk_document(document)

    assert [c["chunk_id"] for c in first] == [
        c["chunk_id"] for c in second
    ]


def test_document_changes_produce_new_ids():
    original = sample_document()
    modified = deepcopy(original)

    modified["sections"][0]["content"] = (
        "Updated training curriculum."
    )

    first = chunk_document(original)
    second = chunk_document(modified)

    assert first[0]["chunk_id"] != second[0]["chunk_id"]


def test_unapproved_documents_remain_unapproved():
    document = sample_document()

    # A value in the incoming document must not
    # automatically grant indexing permission.
    document["approval_status"] = "approved"

    chunks = chunk_document(document)

    assert all(
        c["metadata"]["approval_status"] == "unapproved"
        for c in chunks
    )


def test_invalid_chunk_settings():
    with pytest.raises(ValueError):
        chunk_document(
            sample_document(),
            max_tokens=100,
            overlap_tokens=100,
        )
