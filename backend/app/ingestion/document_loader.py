
from pathlib import Path

from backend.app.ingestion.markdown_loader import load_markdown
from backend.app.ingestion.pdf_loader import load_pdf
from backend.app.ingestion.docx_loader import load_docx


SUPPORTED_EXTENSIONS = {".md", ".pdf", ".docx"}


def load_document(file_path, pdf_extraction_mode="text"):
    """
    Load a supported document through the appropriate reader.

    Supported:
        .md   - Markdown
        .pdf  - PDF
        .docx - Microsoft Word

    The original loader output is preserved.
    No approval, embedding, or database indexing happens here.
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
        )

    elif extension == ".docx":
        document = load_docx(path)

    else:
        document = load_markdown(path)

    # Record which reader handled the document.
    # Preserve each reader's existing output.
    document["file_type"] = extension.lstrip(".")

    return document
