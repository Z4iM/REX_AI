# REX AI TA examples

Everything in this folder is fictional demonstration material, labeled `REX_SYNTHETIC_DEMO`. Names, prices, schedules, offers and organisations are authored examples, not academy commitments. No real personal data, keys, accreditations or live tenders are included.

## Start here

From `D:\REX-AI`, run:

```powershell
python scripts/run_demo.py
```

Open http://127.0.0.1:8510 and choose **Demo setup** in the sidebar. Sign in once with your name and the existing `REX_CATALOG_ADMIN_KEY` from your local `.env`. Keep the key private. Both servers run together; Ctrl+C in that terminal stops them. The demo API is at http://127.0.0.1:8010/docs.

1. Select **Load course examples**. This reads four real Markdown files and prepares local suggestions. Nothing is approved or published automatically.
2. Open **2 · Review & publish**. Select `demo-py-101.md`. Inspect the extracted source and filled fields, confirm your review, then select **Save verified course**.
3. In the publication section below, select **Publish course**. This makes a real Gemini embedding call and saves the index to Chroma. A failed call leaves the course unpublished and can be retried.
4. Open **Browse courses**. Python Foundations Demo should appear at 2400 EGP, online, beginner level, with its fictional instructor, schedule, prerequisites, outcomes and FAQs.
5. Open **Ask REX**. Ask “What does Python Foundations Demo cost and who teaches it?” REX should cite the reviewed information. Ask an unsupported question to see that missing details require confirmation. Guided recommendation example: interest Python, basic computer literacy, beginner, office automation, online, 3000 EGP, 6 hours per week.
6. Open **3 · Create documents**. Choose Course description, inspect and approve its template, select the published course, then generate a draft. Review the text, enter a reason and save an approval. Download PDF and Word. Repeat with a course proposal or participant guide, or choose Arabic.
7. Back in **Demo setup**, select **Load tender examples**. In **Training opportunities**, expect two saved opportunities: Egypt and Saudi Arabia. Germany and expired tenders are rejected; the repeated Egyptian row is deduplicated. Update a workflow status and inspect alerts. Loading again should add zero new opportunities.
8. Upload `negative_cases/reject_missing_information.md` using **1 · Add course documents**. On the review page, reject it with a reason and confirmation. Its history remains visible, approval is disabled, and uploading the identical file preserves rejection.
9. Test Word and PDF ingestion by uploading the matching files under `courses/`. These are alternate source files, so approval with an existing course ID can conflict; use them for extraction/rejection or choose a distinct course ID after reviewing the source. Avoid replacing a published course merely to change format.
10. Try withdrawal only after reviewing its impact. It removes the course from learner access and prevents downloads/approval of documents based on that source revision. Original files and audit history are retained.

## Contents

- `courses/`: four complete course source packs in Markdown, Word and PDF: beginner Python, intermediate data analysis, advanced cloud operations, and an Arabic digital skills course. Each includes authored content/modules and practical exercises.
- `course_content/`: fictional CSV exercise inputs, including malformed values, duplicate rows and expected totals.
- `course_manifest.json`: expected facts to compare with extracted suggestions. These are review references, never an automatic approval input.
- `tenders.json`: positive, unsupported-country, expired and duplicate RFP cases. Demo setup refreshes relative dates when loading; direct file imports use the dates written in this file.
- `learner_profiles.json`: matching and exclusion examples, not stored learners.
- `negative_cases/`: incomplete and multiple-course source files.
- `reference_materials/teaching_reference_pack.*`: ten authored reference examples: participant/facilitator guide, presentation outline, question bank, rubric, capstone, description, curriculum, proposal and outcomes/assessment plan. These examples do not claim that all ten types have working AI generators. Runtime generation currently supports three course-based types; curriculum-dependent generation awaits Faris.

## Storage and trust

Demo catalog, uploads, Chroma, sessions, leads, generated files and RFP database live under ignored `data/demo/`. Academy mode continues using its own catalog/RFP directories. Demo examples are rejected when imported through the academy upload/import endpoints. Both modes still require explicit human course approval and publication. Re-running setup preserves earlier review decisions, including rejection. No external email/webhook is sent by demo setup or the UI search action.

To regenerate the authored examples after intentional content edits, run `scripts/build_demo_examples.py` with Python containing python-docx and PyMuPDF. The builder is separate from startup; ordinary demonstrations do not rebuild or change existing files.
