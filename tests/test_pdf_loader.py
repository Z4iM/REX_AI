
import pytest
import pymupdf

from backend.app.ingestion.pdf_loader import load_pdf


def test_pdf_text_extraction(tmp_path):
    """Check that PDF text and page numbers are preserved."""

    pdf_path = tmp_path / "sample_course.pdf"

    # Create a sample PDF.
    with pymupdf.open() as pdf:

        page1 = pdf.new_page()
        page1.insert_text(
            (72, 72),
            "Python for Data Analytics"
        )
        page1.insert_text(
            (72, 100),
            "Price: 3200 EGP"
        )

        page2 = pdf.new_page()
        page2.insert_text(
            (72, 72),
            "Prerequisites: No programming experience"
        )

        pdf.save(pdf_path)

    # Read it with our loader.
    result = load_pdf(pdf_path)

    assert result["source_file"] == "sample_course.pdf"
    assert result["approval_status"] == "unapproved"
    assert result["page_count"] == 2
    assert len(result["sections"]) == 2

    assert "Python for Data Analytics" in (
        result["sections"][0]["content"]
    )

    assert "3200 EGP" in (
        result["sections"][0]["content"]
    )

    assert "No programming experience" in (
        result["sections"][1]["content"]
    )

    assert result["sections"][0]["metadata"]["page_number"] == 1
    assert result["sections"][1]["metadata"]["page_number"] == 2


def test_empty_pdf_requires_ocr_or_review(tmp_path):
    """A PDF with no extractable text must not be indexed."""

    pdf_path = tmp_path / "empty.pdf"

    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.save(pdf_path)

    with pytest.raises(
        ValueError,
        match="No extractable text"
    ):
        load_pdf(pdf_path)


def test_invalid_file_type(tmp_path):
    """Only PDF inputs should be accepted."""

    file_path = tmp_path / "sample.txt"
    file_path.write_text("Not a PDF")

    with pytest.raises(
        ValueError,
        match="Only PDF"
    ):
        load_pdf(file_path)


def test_missing_pdf(tmp_path):
    """Missing files must produce a clear error."""

    with pytest.raises(FileNotFoundError):
        load_pdf(tmp_path / "missing.pdf")

def test_markdown_extraction_mode(tmp_path):
    """Markdown mode preserves content and page metadata."""

    pdf_path = tmp_path / "layout_test.pdf"

    with pymupdf.open() as pdf:
        page = pdf.new_page()

        page.insert_text(
            (72, 72),
            "Python for Data Analytics"
        )

        page.insert_text(
            (72, 110),
            "Prerequisites: Basic Python"
        )

        pdf.save(pdf_path)

    result = load_pdf(
        pdf_path,
        extraction_mode="markdown",
    )

    assert result["page_count"] == 1
    assert len(result["sections"]) == 1

    content = result["sections"][0]["content"]

    assert "Python for Data Analytics" in content
    assert "Basic Python" in content

    assert (
        result["sections"][0]["metadata"]["page_number"]
        == 1
    )

    assert result["extraction_mode"] == "markdown"


def test_invalid_extraction_mode(tmp_path):
    """Unknown extraction modes must be rejected."""

    pdf_path = tmp_path / "test.pdf"

    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.save(pdf_path)

    with pytest.raises(
        ValueError,
        match="extraction_mode",
    ):
        load_pdf(
            pdf_path,
            extraction_mode="unsupported",
        )

def make_scanned_pdf(tmp_path):
    """Create an image-only PDF for realistic OCR testing."""

    pdf_path = tmp_path / "scanned_course.pdf"

    # Create a normal document first.
    with pymupdf.open() as source:
        page = source.new_page()

        page.insert_text(
            (72, 100),
            "Python Training Program",
            fontsize=24,
        )

        page.insert_text(
            (72, 150),
            "Duration 100 Hours",
            fontsize=20,
        )

        # Convert the page into an image.
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(2, 2),
            alpha=False,
        )

        image_bytes = pixmap.tobytes("png")

    # Build a new PDF containing only the image.
    with pymupdf.open() as scanned:
        page = scanned.new_page()

        page.insert_image(
            page.rect,
            stream=image_bytes,
        )

        scanned.save(pdf_path)

    return pdf_path


def test_scanned_pdf_with_ocr(tmp_path):
    """OCR must recognize text inside an image-only PDF."""

    pdf_path = make_scanned_pdf(tmp_path)

    result = load_pdf(
        pdf_path,
        enable_ocr=True,
        ocr_language="eng",
    )

    assert result["page_count"] == 1
    assert result["ocr_pages"] == [1]
    assert result["pages_without_text"] == []

    section = result["sections"][0]

    assert section["metadata"]["extraction_method"] == "ocr"

    text = section["content"]

    assert "Python Training Program" in text
    assert "100 Hours" in text


def test_scanned_pdf_without_ocr(tmp_path):
    """Existing default behavior must stay unchanged."""

    pdf_path = make_scanned_pdf(tmp_path)

    with pytest.raises(
        ValueError,
        match="No extractable text",
    ):
        load_pdf(
            pdf_path,
            enable_ocr=False,
        )


def test_missing_ocr_language(tmp_path):
    """Report missing language files clearly."""

    pdf_path = make_scanned_pdf(tmp_path)

    with pytest.raises(
        ValueError,
        match="Missing OCR language data",
    ):
        load_pdf(
            pdf_path,
            enable_ocr=True,
            ocr_language="xyz_not_installed",
        )

def test_ocr_requires_extraction_review(tmp_path):
    """OCR results should carry a review warning."""

    pdf_path = make_scanned_pdf(tmp_path)

    result = load_pdf(
        pdf_path,
        enable_ocr=True,
        ocr_language="eng",
    )

    assert result["extraction_review_required"] is True
    assert len(result["extraction_warnings"]) >= 1
    assert "OCR" in result["extraction_warnings"][0]

    # OCR never grants document approval.
    assert result["approval_status"] == "unapproved"


def test_normal_pdf_without_quality_warnings(tmp_path):
    """Normal text extraction should not raise OCR warnings."""

    pdf_path = tmp_path / "normal.pdf"

    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            "Python Programming Course",
        )
        pdf.save(pdf_path)

    result = load_pdf(pdf_path)

    assert result["extraction_review_required"] is False
    assert result["extraction_warnings"] == []

    # No quality warning does not mean the source is approved.
    assert result["approval_status"] == "unapproved"
