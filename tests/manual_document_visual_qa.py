"""Render isolated synthetic QA fixtures, never insert them into academy storage.

Run with the bundled Python runtime. Prints the temporary output directory.
"""
import json
from pathlib import Path
import tempfile
from backend.app.documents.rendering import render_document


def main():
    root = Path(tempfile.mkdtemp(prefix="rex-sprint2-document-qa-"))
    for language in ("en", "ar"):
        for kind in ("course_description", "course_proposal", "participant_guide"):
            ar = language == "ar"
            record = {
                "artifact_id": "00000000-0000-4000-8000-000000000001", "version": 1, "status": "approved",
                "approved_by": "QA Reviewer", "approved_at": "2026-10-26T12:00:00+00:00",
                "document_type": kind, "language": language, "audience": "متعلمين جدد" if ar else "Prospective learners",
                "content": {"title": ("عينة اختبار فقط لدورة بايثون" if ar else "Synthetic QA fixture Python course") + " " + kind,
                    "sections": [{"heading": heading, "text": text, "source_ids": ["S1"]} for heading, text in (
                        [("نظرة عامة", "هذه عينة اختبار اصطناعية فقط للتحقق من سلامة تنسيق النص العربي ولا تمثل دورة حقيقية بالأكاديمية."),
                         ("مخرجات التعلم", "توضح العينة طريقة عرض بيانات الدورة المعتمدة والمراجع. يجب مراجعة المعلومات قبل استخدامها."),
                         ("متطلبات المشاركة", "لم تحدد البيانات موعد الدراسة أو تفاصيل الشهادة. يجب الرجوع إلى موظفي الأكاديمية للتأكد.")]
                        if ar else [("Course overview", "This is an isolated synthetic QA fixture for checking document layout. It is not an academy offering."),
                                    ("Learning outcomes", "The fixture demonstrates source-cited learning outcomes using the verified course snapshot."),
                                    ("Entry requirements", "Schedules and certification were not specified. Confirm missing details with academy staff.")])]},
                "sources": [{"source_id": "S1", "source_file": "synthetic_qa_only.md", "course": {
                    "course_id": "QA-101", "title": "بايثون عينة اختبار" if ar else "Python QA fixture",
                    "description": "هذه بيانات اختبار اصطناعية فقط." if ar else "Synthetic test-only description.",
                    "level": "Beginner", "training_format": "Online", "price_egp": 2500, "duration_hours": 20,
                    "department": None, "prerequisites": ["مهارات الحاسوب الأساسية" if ar else "Basic computer skills"],
                    "learning_outcomes": ["استخدام بايثون" if ar else "Use Python"], "source_sha256": "a" * 64}}],
            }
            directory = root / (kind + "_" + language)
            render_document(record, directory)
            (directory / "fixture.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    import pymupdf
    for pdf_path in root.glob("*/document.pdf"):
        with pymupdf.open(pdf_path) as pdf:
            for index, page in enumerate(pdf, 1):
                page.get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25)).save(pdf_path.parent / f"page-{index}.png")
    print(root)


if __name__ == "__main__":
    main()
