
from pathlib import Path
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError
from backend.app.ingestion.archive_safety import validate_office_archive


def load_docx(file_path):
    """
    Extract paragraphs, headings, and tables from a DOCX file.

    Preserves document order and marks the content
    as unapproved until reviewed.
    """

    path = Path(file_path)

    if path.suffix.lower() != ".docx":
        raise ValueError("Only DOCX files are supported")

    if not path.is_file():
        raise FileNotFoundError(
            f"DOCX file not found: {path}"
        )

    validate_office_archive(path)
    try:
        document = Document(path)
    except (KeyError, zipfile.BadZipFile, XMLSyntaxError) as exc:
        raise ValueError("DOCX package is incomplete or corrupt") from exc

    sections = []
    current_title = "Document Content"
    content_lines = []

    def save_section():
        """Save the current section if it contains text."""

        if not any(line.strip() for line in content_lines):
            return

        sections.append({
            "title": current_title,
            "content": "\n".join(content_lines).strip(),
            "metadata": {
                "section_index": len(sections) + 1,
                "source_type": "docx",
            },
        })

    # Iterate through paragraphs and tables in order.
    for block in document.iter_inner_content():

        if isinstance(block, Paragraph):

            text = block.text.strip()

            if not text:
                continue

            style_name = (
                block.style.name.lower()
                if block.style is not None
                else ""
            )

            # Start a new section when a heading appears.
            if (
                style_name.startswith("heading")
                or style_name == "title"
            ):
                save_section()

                current_title = text
                content_lines = []

            else:
                content_lines.append(text)

        elif isinstance(block, Table):

            table_rows = []

            for row in block.rows:

                values = [
                    " ".join(cell.text.split())
                    for cell in row.cells
                ]

                table_rows.append(" | ".join(values))

            if table_rows:
                content_lines.append(
                    "\n".join(table_rows)
                )

    # Save the final section.
    save_section()

    if not sections:
        raise ValueError(
            "No extractable text found in DOCX document"
        )

    return {
        "source_file": path.name,
        "approval_status": "unapproved",
        "sections": sections,
    }
