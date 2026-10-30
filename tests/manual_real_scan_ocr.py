
import sys
import tempfile
from pathlib import Path

import pymupdf

from backend.app.ingestion.document_loader import load_document


TEST_PAGES = {
    3: [
        "Software Testing",
        "Playwright",
        "Cypress",
        "GitHub Actions",
    ],
    8: [
        "Data Science",
        "RAG",
        "BentoML",
        "MLflow",
    ],
}


def run_ocr_test(pdf_path):
    pdf_path = Path(pdf_path)

    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    with tempfile.TemporaryDirectory() as temp_dir:

        with pymupdf.open(pdf_path) as original:

            for page_number, keywords in TEST_PAGES.items():

                if page_number > original.page_count:
                    continue

                print("\n" + "=" * 60)
                print(f"TESTING PAGE {page_number}")
                print("=" * 60)

                page = original[page_number - 1]

                original_text = page.get_text(
                    "text",
                    sort=True,
                )

                # Simulate a scan by rendering the page to pixels.
                pixmap = page.get_pixmap(
                    dpi=250,
                    alpha=False,
                )

                image_bytes = pixmap.tobytes("png")

                scanned_path = (
                    Path(temp_dir)
                    / f"scanned_page_{page_number}.pdf"
                )

                # Create an image-only PDF.
                with pymupdf.open() as scanned:

                    new_page = scanned.new_page(
                        width=page.rect.width,
                        height=page.rect.height,
                    )

                    new_page.insert_image(
                        new_page.rect,
                        stream=image_bytes,
                    )

                    scanned.save(scanned_path)

                # Verify that the PDF truly has no text layer.
                with pymupdf.open(scanned_path) as check:
                    assert not check[0].get_text().strip()

                # Run OCR through our unified document loader.
                result = load_document(
                    scanned_path,
                    enable_ocr=True,
                    ocr_language="eng",
                    ocr_dpi=250,
                )

                assert result["ocr_pages"] == [1]
                assert result["pages_without_text"] == []

                ocr_text = result["sections"][0]["content"]

                print("OCR activated:", result["ocr_pages"])
                print("Original characters:", len(original_text))
                print("OCR characters:", len(ocr_text))

                print("\nKEYWORD RECOVERY:")

                for keyword in keywords:
                    found = (
                        keyword.casefold()
                        in ocr_text.casefold()
                    )

                    print(
                        f"{keyword}: "
                        f"{'FOUND' if found else 'MISSING'}"
                    )

                print("\nOCR TEXT PREVIEW:")
                print(ocr_text[:1800])


if __name__ == "__main__":

    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m tests.manual_real_scan_ocr "
            "<pdf_path>"
        )

    run_ocr_test(sys.argv[1])
