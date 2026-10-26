
import sys
from pathlib import Path

import pymupdf


def inspect_pdf(file_path):
    path = Path(file_path)

    with pymupdf.open(path) as pdf:
        print(f"Document: {path.name}")
        print(f"Total pages: {pdf.page_count}")

        # Pages we want to inspect:
        # Page 3: Two-column course information
        # Page 8: Complex curriculum layout
        for page_number in [3, 8]:

            if page_number > pdf.page_count:
                continue

            page = pdf[page_number - 1]

            print("\n" + "=" * 60)
            print(f"PAGE {page_number}")
            print("=" * 60)

            # Method 1: Our existing extraction
            text = page.get_text(
                "text",
                sort=True,
            )

            print("\nCURRENT EXTRACTION:")
            print(text[:800])

            # Method 2: Position-aware text blocks
            blocks = page.get_text(
                "blocks",
                sort=True,
            )

            text_blocks = [
                block for block in blocks
                if len(block) >= 7 and block[6] == 0
            ]

            print("\nTEXT BLOCKS:")
            print("Number of blocks:", len(text_blocks))

            for block in text_blocks[:12]:
                x0, y0, x1, y1 = block[:4]
                content = " ".join(block[4].split())

                print(
                    f"Position ({x0:.0f}, {y0:.0f}) "
                    f"to ({x1:.0f}, {y1:.0f}): "
                    f"{content[:100]}"
                )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python tests/manual_pdf_layout_audit.py "
            "<pdf_path>"
        )

    inspect_pdf(sys.argv[1])
