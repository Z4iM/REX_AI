
import hashlib
import re

import tiktoken


ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    return len(ENCODER.encode(text))


def split_sections(content):
    """Preserve Markdown subsection boundaries."""
    parts = re.split(r"(?m)^###\s+(.+?)\s*$", content)

    sections = []

    if parts[0].strip():
        sections.append(("Course Information", parts[0].strip()))

    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1].strip()

        if body:
            sections.append((title, body))

    return sections


def split_long_text(text, prefix, max_tokens, overlap_tokens):
    """Split oversized sections while preserving Unicode text."""
    words = text.split()
    result = []
    start = 0

    while start < len(words):
        # Find the largest word span fitting our token budget.
        low = start + 1
        high = len(words)
        best = start

        while low <= high:
            mid = (low + high) // 2
            candidate = prefix + "\n" + " ".join(words[start:mid])

            if count_tokens(candidate) <= max_tokens:
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        if best == start:
            raise ValueError(
                "A word exceeds the chunk token budget."
            )

        result.append(" ".join(words[start:best]))

        if best == len(words):
            break

        # Find up to overlap_tokens from the end.
        next_start = best

        for pos in range(best - 1, start, -1):
            overlap = " ".join(words[pos:best])

            if count_tokens(overlap) > overlap_tokens:
                break

            next_start = pos

        # Guarantee forward progress.
        start = next_start if next_start > start else best

    return result


def chunk_courses(courses, max_tokens=400, overlap_tokens=60):
    """Convert normalized courses into traceable RAG chunks."""
    if not 0 <= overlap_tokens < max_tokens:
        raise ValueError("Invalid chunking configuration")

    chunks = []

    for course in courses:
        sections = split_sections(course["content"])

        for section_name, body in sections:
            course_id = course.get("course_id") or "unknown"

            prefix = (
                f"Course: {course['title']}\n"
                f"Course ID: {course_id}\n"
                f"Section: {section_name}"
            )

            if count_tokens(prefix + "\n" + body) <= max_tokens:
                pieces = [body]
            else:
                pieces = split_long_text(
                    body, prefix, max_tokens, overlap_tokens
                )

            for index, piece in enumerate(pieces):
                text = prefix + "\n" + piece

                identity = (
                    f"{course['source_file']}|"
                    f"{course_id}|{course['title']}|"
                    f"{section_name}|{index}"
                )

                chunk_id = hashlib.sha256(
                    identity.encode("utf-8")
                ).hexdigest()[:20]

                chunks.append({
                    "chunk_id": chunk_id,
                    "text": text,
                    "token_count": count_tokens(text),
                    "metadata": {
                        "course_id": str(course_id),
                        "course_title": course["title"],
                        "section": section_name,
                        "source_file": course["source_file"],
                        "dataset_status": course["dataset_status"],
                        "approval_status": course["approval_status"],
                        "chunk_index": index,
                    }
                })

    return chunks


if __name__ == "__main__":
    from backend.app.ingestion.markdown_loader import load_markdown
    from backend.app.ingestion.course_normalizer import normalize_document

    paths = [
        "data/samples/course_catalog.md",
        "data/samples/alternative_catalog.md"
    ]

    courses = []

    for path in paths:
        document = load_markdown(path)
        courses.extend(normalize_document(document))

    chunks = chunk_courses(courses)

    print("Courses loaded:", len(courses))
    print("Chunks generated:", len(chunks))

    for chunk in chunks:
        meta = chunk["metadata"]

        print(
            f"{meta['course_title']} | "
            f"{meta['section']} | "
            f"{chunk['token_count']} tokens"
        )

    assert len(courses) == 5
    assert len(chunks) >= 5
    assert all(c["token_count"] <= 400 for c in chunks)
    assert all(
        c["metadata"]["approval_status"] == "unapproved"
        for c in chunks
    )
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)

    print("\nAll chunking checks passed!")
