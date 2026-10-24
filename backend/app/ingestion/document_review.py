
import hashlib
from pathlib import Path

from backend.app.ingestion.document_loader import load_document
from backend.app.rag.document_chunker import chunk_document


def calculate_file_hash(file_path):
    """Calculate a SHA-256 hash of the original file."""

    digest = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def prepare_document_for_review(
    file_path,
    pdf_extraction_mode="text",
    *,
    enable_ocr=False,
    ocr_language="eng",
    ocr_dpi=200,
):
    """
    Prepare a document for human review.

    Steps:
    1. Load the document.
    2. Generate RAG chunks.
    3. Calculate the original file checksum.
    4. Collect extraction warnings.
    5. Determine whether extraction is incomplete.
    6. Return an unapproved review package.

    This function does not:
    - Approve documents
    - Call Gemini
    - Generate embeddings
    - Write anything to ChromaDB
    """

    path = Path(file_path)

    # 1. Read the document.
    document = load_document(
        path,
        pdf_extraction_mode=pdf_extraction_mode,
        enable_ocr=enable_ocr,
        ocr_language=ocr_language,
        ocr_dpi=ocr_dpi,
    )

    # 2. Split the document into searchable chunks.
    chunks = chunk_document(document)

    if not chunks:
        raise ValueError(
            "Document produced no usable chunks"
        )

    # 3. Identify the exact original file version.
    source_sha256 = calculate_file_hash(path)

    # 4. Collect extraction information.
    missing_pages = document.get(
        "pages_without_text",
        [],
    )

    extraction_warnings = list(
        document.get("extraction_warnings", [])
    )

    extraction_review_required = bool(
        document.get(
            "extraction_review_required",
            False,
        )
        or extraction_warnings
    )

    # 5. Incomplete extraction needs correction
    # before normal approval can proceed.
    if missing_pages:
        review_status = "blocked_incomplete"
    else:
        review_status = "pending_review"

    # 6. Attach provenance to each chunk.
    for chunk in chunks:
        chunk["metadata"]["source_sha256"] = (
            source_sha256
        )

    # 7. Return a review package.
    return {
        "document_id": chunks[0]["metadata"]["document_id"],
        "source_file": document["source_file"],
        "source_sha256": source_sha256,
        "file_type": document["file_type"],
        "page_count": document.get("page_count"),
        "chunk_count": len(chunks),
        "missing_pages": missing_pages,
        "extraction_review_required": (
            extraction_review_required
        ),
        "extraction_warnings": extraction_warnings,
        "review_status": review_status,
        "approval_status": "unapproved",
        "indexing_allowed": False,
        "chunks": chunks,
    }
