
import unittest

from backend.app.rag.chunker import (
    split_long_text,
    count_tokens,
)


class TestChunker(unittest.TestCase):

    def test_long_document(self):
        # Simulate a long unfamiliar document.
        words = [f"topic{i:04d}" for i in range(800)]
        text = " ".join(words)

        prefix = "Course: Stress Test\nSection: Content"

        chunks = split_long_text(
            text,
            prefix,
            max_tokens=400,
            overlap_tokens=60,
        )

        # Long content must produce multiple chunks.
        self.assertGreater(len(chunks), 1)

        # Every chunk must respect the token limit.
        for chunk in chunks:
            self.assertLessEqual(
                count_tokens(prefix + "\n" + chunk),
                400,
            )

        # No information should be lost.
        recovered = {
            word
            for chunk in chunks
            for word in chunk.split()
        }
        self.assertEqual(recovered, set(words))

        # Adjacent chunks should overlap.
        for first, second in zip(chunks, chunks[1:]):
            left = first.split()
            right = second.split()

            overlap_found = any(
                left[-n:] == right[:n]
                for n in range(
                    1, min(len(left), len(right)) + 1
                )
            )

            self.assertTrue(overlap_found)

        print(
            f"\nLong document split into {len(chunks)} chunks"
        )


if __name__ == "__main__":
    unittest.main()
