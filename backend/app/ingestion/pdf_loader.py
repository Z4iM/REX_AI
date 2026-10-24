
from pathlib import Path

import pymupdf


def load_pdf(file_path, extraction_mode="text"):
    """
    Load a PDF into structured page-level sections.

    Supported extraction modes:
        text     - Standard PyMuPDF text extraction.
        markdown - Layout-aware Markdown extraction.

    Documents remain unapproved by default.
    OCR is not performed.
    """

    path = Path(file_path)

    # Validate file type.
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported")

    if not path.is_file():
        raise FileNotFoundError(
            f"PDF file not found: {path}"
        )

    if extraction_mode not in {"text", "markdown"}:
        raise ValueError(
            "extraction_mode must be 'text' or 'markdown'"
        )

    sections = []
    pages_without_text = []
    fallback_pages = []

    with pymupdf.open(path) as pdf:

        if pdf.needs_pass:
            raise ValueError(
                "Password-protected PDF is not supported"
            )

        page_count = pdf.page_count

        # Perform layout-aware extraction only when requested.
        markdown_pages = None

        if extraction_mode == "markdown":
            markdown_pages = pdf.to_markdown(
                page_chunks=True,
                use_ocr=False,
                write_images=False,
            )

        for page_index, page in enumerate(pdf):

            page_number = page_index + 1

            # Plain text is also used to detect unreadable pages.
            raw_text = page.get_text(
                "text",
                sort=True,
            ).strip()

            if not raw_text:
                pages_without_text.append(page_number)
                continue

            used_method = extraction_mode

            if extraction_mode == "markdown":

                text = markdown_pages[page_index][
                    "text"
                ].strip()

                # Avoid silently losing extractable text.
                if not text:
                    text = raw_text
                    used_method = "text_fallback"
                    fallback_pages.append(page_number)

            else:
                text = raw_text

            sections.append({
                "title": f"Page {page_number}",
                "content": text,
                "metadata": {
                    "page_number": page_number,
                    "source_type": "pdf",
                    "extraction_method": used_method,
                },
            })

    if not sections:
        raise ValueError(
            "No extractable text found. "
            "The PDF may require OCR."
        )

    return {
        "source_file": path.name,
        "approval_status": "unapproved",
        "sections": sections,
        "page_count": page_count,
        "pages_without_text": pages_without_text,
        "fallback_pages": fallback_pages,
        "extraction_mode": extraction_mode,
    }
