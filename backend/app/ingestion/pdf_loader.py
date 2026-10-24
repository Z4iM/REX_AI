
from pathlib import Path

import pymupdf


def load_pdf(
    file_path,
    extraction_mode="text",
    enable_ocr=False,
    ocr_language="eng",
    ocr_dpi=200,
):
    """
    Load a PDF into structured page-level sections.

    Features:
    - Standard PDF text extraction
    - Layout-aware Markdown extraction
    - Optional OCR for scanned pages
    - Page number preservation
    - Extraction method tracking
    - OCR quality warnings
    - Human review indicators

    Documents are always unapproved by default.
    """

    # --------------------------------------------------
    # 1. VALIDATE INPUT
    # --------------------------------------------------

    path = Path(file_path)

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

    if not isinstance(ocr_dpi, int) or not 72 <= ocr_dpi <= 600:
        raise ValueError(
            "ocr_dpi must be between 72 and 600"
        )

    if enable_ocr:
        if not isinstance(ocr_language, str) or not ocr_language.strip():
            raise ValueError(
                "ocr_language cannot be empty"
            )

    # --------------------------------------------------
    # 2. INITIALIZE TRACKING
    # --------------------------------------------------

    sections = []
    pages_without_text = []
    fallback_pages = []
    ocr_pages = []

    tessdata = None

    if enable_ocr:
        tessdata = Path(pymupdf.get_tessdata())

    # --------------------------------------------------
    # 3. OPEN AND PROCESS PDF
    # --------------------------------------------------

    with pymupdf.open(path) as pdf:

        if pdf.needs_pass:
            raise ValueError(
                "Password-protected PDF is not supported"
            )

        page_count = pdf.page_count

        markdown_pages = None

        # Prepare layout-aware extraction when requested.
        if extraction_mode == "markdown":

            markdown_pages = pdf.to_markdown(
                page_chunks=True,
                use_ocr=False,
                write_images=False,
            )

        # Process each page individually.
        for page_index, page in enumerate(pdf):

            page_number = page_index + 1

            # First attempt normal text extraction.
            raw_text = page.get_text(
                "text",
                sort=True,
            ).strip()

            used_method = extraction_mode

            # ------------------------------------------
            # CASE A: PAGE CONTAINS SELECTABLE TEXT
            # ------------------------------------------

            if raw_text:

                if extraction_mode == "markdown":

                    text = markdown_pages[page_index][
                        "text"
                    ].strip()

                    # Fall back to standard text if needed.
                    if not text:

                        text = raw_text
                        used_method = "text_fallback"

                        fallback_pages.append(page_number)

                else:

                    text = raw_text

            # ------------------------------------------
            # CASE B: SCANNED PAGE REQUIRES OCR
            # ------------------------------------------

            elif enable_ocr:

                # Validate available OCR languages.
                languages = ocr_language.split("+")

                missing_languages = [
                    language
                    for language in languages
                    if not language.strip()
                    or not (
                        tessdata / f"{language}.traineddata"
                    ).is_file()
                ]

                if missing_languages:

                    raise ValueError(
                        "Missing OCR language data: "
                        + ", ".join(missing_languages)
                        + f". Install it in {tessdata}"
                    )

                # Perform full-page OCR.
                text_page = page.get_textpage_ocr(
                    language=ocr_language,
                    dpi=ocr_dpi,
                    full=True,
                    tessdata=str(tessdata),
                )

                # Extract recognized text.
                text = page.get_text(
                    "text",
                    textpage=text_page,
                    sort=True,
                ).strip()

                if text:

                    used_method = "ocr"

                    ocr_pages.append(page_number)

            # ------------------------------------------
            # CASE C: NO TEXT AND OCR DISABLED
            # ------------------------------------------

            else:

                text = ""

            # ------------------------------------------
            # HANDLE UNREADABLE PAGES
            # ------------------------------------------

            if not text:

                pages_without_text.append(page_number)

                continue

            # ------------------------------------------
            # SAVE EXTRACTED PAGE
            # ------------------------------------------

            sections.append({
                "title": f"Page {page_number}",
                "content": text,
                "metadata": {
                    "page_number": page_number,
                    "source_type": "pdf",
                    "extraction_method": used_method,
                },
            })

    # --------------------------------------------------
    # 4. VALIDATE EXTRACTION RESULT
    # --------------------------------------------------

    if not sections:

        raise ValueError(
            "No extractable text found. "
            "The PDF may require OCR or manual review."
        )

    # --------------------------------------------------
    # 5. IDENTIFY EXTRACTION QUALITY WARNINGS
    # --------------------------------------------------

    extraction_warnings = []

    # OCR text may contain recognition mistakes.
    if ocr_pages:

        extraction_warnings.append(
            f"OCR was used on pages {ocr_pages}. "
            "Verify recognition accuracy and reading order."
        )

    # Some pages could not be read.
    if pages_without_text:

        extraction_warnings.append(
            f"No readable text was extracted from pages "
            f"{pages_without_text}."
        )

    # Markdown extraction required fallback.
    if fallback_pages:

        extraction_warnings.append(
            f"Markdown extraction fell back to plain text "
            f"on pages {fallback_pages}."
        )

    # True when any extraction warning exists.
    extraction_review_required = bool(
        extraction_warnings
    )

    # --------------------------------------------------
    # 6. RETURN STRUCTURED DOCUMENT
    # --------------------------------------------------

    return {
        "source_file": path.name,
        "approval_status": "unapproved",
        "sections": sections,
        "page_count": page_count,
        "pages_without_text": pages_without_text,
        "fallback_pages": fallback_pages,
        "ocr_pages": ocr_pages,
        "extraction_mode": extraction_mode,
        "extraction_review_required": extraction_review_required,
        "extraction_warnings": extraction_warnings,
    }
