
import hashlib
import json
from pathlib import Path

from backend.app.rag.chunker import (
    count_tokens,
    split_long_text,
)


def chunk_document(
    document,
    max_tokens=400,
    overlap_tokens=60,
):
    """
    Turn a loaded document into traceable RAG chunks.

    - Preserves source and section information.
    - Preserves PDF page numbers where available.
    - Uses the existing tokenization strategy.
    - Marks every chunk as pending review.

    Does not generate embeddings or insert data into ChromaDB.
    """

    if not 0 <= overlap_tokens < max_tokens:
        raise ValueError("Invalid chunking configuration")

    source_file = document["source_file"]
    file_type = document.get(
        "file_type",
        Path(source_file).suffix.lstrip("."),
    )

    sections = document["sections"]

    # Identify this specific document version.
    document_payload = {
        "source_file": source_file,
        "file_type": file_type,
        "sections": sections,
    }

    document_hash = hashlib.sha256(
        json.dumps(
            document_payload,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    document_id = document_hash[:20]

    chunks = []

    for section_index, section in enumerate(sections):

        title = section["title"]
        content = section["content"].strip()

        if not content:
            continue

        section_metadata = section.get("metadata", {})

        prefix = (
            f"Document: {source_file}\n"
            f"Section: {title}"
        )

        if count_tokens(prefix + "\n" + content) <= max_tokens:
            pieces = [content]
        else:
            pieces = split_long_text(
                content,
                prefix,
                max_tokens,
                overlap_tokens,
            )

        for chunk_index, piece in enumerate(pieces):

            chunk_text = prefix + "\n" + piece

            identity = (
                f"{document_hash}|"
                f"{section_index}|"
                f"{chunk_index}"
            )

            chunk_id = hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:20]

            metadata = {
                "document_id": document_id,
                "source_file": source_file,
                "file_type": file_type,
                "section": title,
                "section_index": section_index,
                "chunk_index": chunk_index,
                "approval_status": "unapproved",
                "ingestion_status": "pending_review",
                "extraction_review_required": document.get(
                    "extraction_review_required",
                    False,
                ),
            }

            # Preserve PDF page citations.
            page_number = section_metadata.get(
                "page_number"
            )

            if isinstance(page_number, int):
                metadata["page_number"] = page_number

            extraction_method = section_metadata.get(
                "extraction_method"
            )

            if extraction_method:
                metadata["extraction_method"] = (
                    extraction_method
                )

            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "token_count": count_tokens(chunk_text),
                "metadata": metadata,
            })

    return chunks
