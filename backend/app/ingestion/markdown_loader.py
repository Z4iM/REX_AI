
from pathlib import Path
import re
import json


def extract_metadata(lines):
    """Extract structured key-value pairs from text."""
    metadata = {}

    for line in lines:
        match = re.match(r"^([\w ]+):\s*(.+)$", line.strip())

        if match:
            key = match.group(1).lower().replace(" ", "_")
            metadata[key] = match.group(2).strip()

    return metadata


def load_markdown(file_path):
    """Load a Markdown document into structured sections."""
    path = Path(file_path)

    if path.suffix.lower() != ".md":
        raise ValueError("Only Markdown files are supported")

    text = path.read_text(encoding="utf-8-sig")

    if not text.strip():
        raise ValueError("Document is empty")

    # Divide by level-two Markdown headings
    parts = re.split(r"(?m)^##\s+", text)

    # Preserve document-level metadata
    header_metadata = extract_metadata(parts[0].splitlines())

    status = header_metadata.get("dataset_status", "unapproved")

    sections = []
    for part in parts[1:]:
        lines = part.splitlines()

        if not lines:
            continue

        title = lines[0].strip()
        content_lines = lines[1:]

        # Extract fields before the first subsection
        top_lines = []

        for line in content_lines:
            if line.startswith("### "):
                break
            top_lines.append(line)

        sections.append({
            "title": title,
            "content": "\n".join(content_lines).strip(),
            "metadata": extract_metadata(top_lines)
        })

    # Introductory content can contain course fields and provenance notices.
    # Dropping it silently loses review evidence (and synthetic-data labels).
    preamble = parts[0].strip()
    if preamble:
        sections.append({"title": "Document", "content": preamble,
                         "metadata": {**header_metadata, "section_kind": "document_preamble"}})


    return {
        "source_file": path.name,
        "approval_status": status,
        "sections": sections
    }


if __name__ == "__main__":
    result = load_markdown("data/samples/course_catalog.md")

    print("Source:", result["source_file"])
    print("Status:", result["approval_status"])
    print("Sections found:", len(result["sections"]))

    for section in result["sections"]:
        print("\nTitle:", section["title"])
        print("Metadata:", json.dumps(
            section["metadata"], indent=2
        ))
