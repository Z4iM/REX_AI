
import sys
from pathlib import Path

import pymupdf


def compare_layout(file_path):
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(path)

    with pymupdf.open(path) as pdf:

        for page_number in [3, 8]:
            if page_number > pdf.page_count:
                continue

            print("\n" + "=" * 65)
            print(
                f"PAGE {page_number} — "
                "LAYOUT-AWARE EXTRACTION"
            )
            print("=" * 65)

            markdown = pdf.to_markdown(
                pages=[page_number - 1],
                use_ocr=False,
            )

            print(markdown[:3000])

            print(
                "\nExtracted characters:",
                len(markdown)
            )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python tests/manual_layout_comparison.py "
            "<pdf_path>"
        )

    compare_layout(sys.argv[1])
