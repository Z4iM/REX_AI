
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
