
from pathlib import Path

from backend.app.ingestion.markdown_loader import load_markdown
from backend.app.ingestion.pdf_loader import load_pdf
from backend.app.ingestion.docx_loader import load_docx


SUPPORTED_EXTENSIONS = {".md", ".pdf", ".docx"}


def load_document(
    file_path,
    pdf_extraction_mode="text",
    *,
    enable_ocr=False,
    ocr_language="eng",
    ocr_dpi=200,
):
    """
    Unified document loader for REX AI.

    Supported formats:
        PDF  - Normal text, Markdown, optional OCR
        DOCX - Paragraphs, headings, tables
        MD   - Structured Markdown

    OCR options apply to PDF files only.

    This function does not approve or index documents.
    """

    path = Path(file_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format: {extension or 'none'}. "
            f"Supported formats: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    if not path.is_file():
        raise FileNotFoundError(
            f"Document not found: {path}"
        )

    if extension == ".pdf":

        document = load_pdf(
            path,
            extraction_mode=pdf_extraction_mode,
            enable_ocr=enable_ocr,
            ocr_language=ocr_language,
            ocr_dpi=ocr_dpi,
        )

    elif extension == ".docx":

        document = load_docx(path)

    else:

        document = load_markdown(path)

    document["file_type"] = extension.lstrip(".")

    return document
