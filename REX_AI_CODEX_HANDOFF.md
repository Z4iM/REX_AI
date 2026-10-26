# REX AI — Codex Development Handoff

**Date:** 2026-10-26
**Repository:** https://github.com/Z4iM/REX_AI
**Development branch:** `dev/abdulrahman`
**Workspace:** The currently open VS Code folder IS the REX_AI repository root. Work in that folder, not in a new clone/copy.
**Team assignments (user clarification, 2026-10-26):** AbdulRahman Adham owns the REX Assistant, approved catalog/RAG, and Document Generation Agent. Faris Ahmed has completed the RFP Agent on his branch (user-reported) and will later implement the Curriculum Agent. Ahmed ElAbiad owns only the AI Marketing Agent. Branch completion does not establish integration into this checkout. These assignments supersede earlier task-division entries.

## Current continuation status — supersedes historical next-task notes below

The user subsequently authorized completing all independent AbdulRahman Sprint 2 milestones without stopping between them. Work is in the existing `D:\REX-AI` checkout on `dev/abdulrahman`; do not use the empty initial chat directory under Documents. No commit/push/merge is required by this authorization.

Document rejection, approved catalog student integration, metadata suggestions, persistent learner sessions, three English/Arabic DOCX/PDF document types with staff review/revisions/downloads, and local stdio MCP tools have been implemented. Read `docs/abdulrahman_progress.md` for actual test results and remaining validation limits, and `docs/SPRINT2_TA_WALKTHROUGH.md` for operation. The earlier implementation-history/roadmap sections below describe the starting state, not the current backlog.

The user later explicitly authorized Faris RFP integration, fictional TA examples, UI simplification and paid API testing. Faris's RFP package is now imported from `origin/dev/faris` at `4331c89` and registered with existing host staff auth; no whole-branch merge was performed. Guided navigation and one staff sign-in replace repeated technical setup. `python scripts/run_demo.py` starts isolated demo servers on 8010/8510; `examples/ta_demo/README.md` explains the course/tender/document examples. The tested text model is now `gemini-3.5-flash`; only the local model setting changed, not key values. Live provider workflows passed; see progress log for exact results and prior transient failures. Curriculum-dependent generation awaits Faris's approved Curriculum Agent interface. Ahmed's Marketing Agent and full team orchestration remain later work.

## Source-of-truth priority

1. **Actual local workspace files and uncommitted changes** (may be newer than GitHub).
2. Existing project brief, architecture, task division, and test files.
3. This handoff as intent/history. If it disagrees with the code, inspect and report the discrepancy instead of overwriting working code.
4. GitHub `main` and teammate branches are reference sources. The user reports Faris's RFP Agent complete on his branch; verify integration separately rather than assuming it is present locally. Do not merge branches or alter Faris's files without explicit user approval.

Before coding, inspect `git status`, current branch, local diff, dependency manifests, `.gitignore`, relevant modules and tests. Don't print `.env` secrets, commit secrets, or overwrite files. **Do not commit, push, merge, create a PR, or change branches without being asked.**

## Product goal

REX AI is a functional, professional academy multi-agent application, NOT a static prototype. Build true end-to-end features: persistent data, APIs, Streamlit UI, real embeddings/retrieval, validation, auditability, error handling, access controls, repeatable tests, and user-visible outcomes. Keep synthetic fixtures ONLY in tests and isolated synthetic collections; never present them as real academy courses. Only verified staff-approved records may reach student-facing RAG, course matching, recommendations or generated documents.

## Current AbdulRahman workstream — verify locally before assuming present

Existing REX modules include:
- `backend/app/ingestion/document_loader.py`, `pdf_loader.py`, `docx_loader.py`, `document_review.py`, `course_normalizer.py`, `markdown_loader.py`: PDF/DOCX/Markdown parsing, OCR, integrity hashes, extraction warnings, review package.
- `backend/app/rag/document_chunker.py`, `chunker.py`, `build_knowledge_base.py`, `retriever.py`: chunking and earlier synthetic RAG path.
- `backend/app/assistant/course_matcher.py`, `qualification.py`, `personalized_recommendation.py`, `grounded_answer.py`: qualification, deterministic budget/delivery format/skill-level checks, recommendation/chat.
- `backend/app/main.py` and `frontend/app.py`, `frontend/guided_recommendation.py`.

Previously supplied/installed **Course Document Upload** increment:
- `backend/app/catalog/upload_router.py`
- `frontend/pages/3_Course_Documents.py`
- `tests/test_course_uploads.py`
- Staff key `REX_CATALOG_ADMIN_KEY` from local `.env`. Uploads accept PDF/DOCX/MD, persist originals and review manifests under `data/catalog/uploads/<sha256>/`, prepare chunks; do NOT auto-index or approve. The user reported upload works.

Previously supplied **Approval + RAG** increment (installation/configuration should be verified):
- `backend/app/catalog/catalog_service.py`
- `backend/app/catalog/approval_router.py`
- `backend/app/catalog/approved_index.py`
- `backend/app/catalog/approved_answer.py`
- `frontend/pages/4_Course_Approvals.py`
- `tests/test_catalog_approval_publication.py`
- Staff approval saves validated metadata to SQLite `data/catalog/catalog.db`; publish uses Gemini embeddings + approved-only Chroma collection and publishes only after indexing succeeds. Published course list and retrieval are independently gated by SQLite publication state and exact source hash. Withdrawal revokes visibility.
- Existing approval flow contains **Approve, Publish, Withdraw**, but **NO Reject uploaded document** action. This is the NEXT task.
- The `INTEGRATION.md` in the supplied approval package described a manual cutover from synthetic RAG to approved catalog. Determine whether these changes were applied locally. Do not assume so.

History of tests: user previously reported 91 and 40 passing tests for the Course Assistant work. Approval package had 10 offline safety tests, using fakes (not proof of live Gemini indexing). Re-run tests in current local environment; report actual results. An old `tests/test_gemini_connection.py` makes an external API request at import time / requires a credential. Keep live/online integration tests explicitly opt-in, and do not suppress unrelated failures.

## Historical first milestone — Document rejection (now implemented)

Provide a real ability for authorized staff to reject an uploaded course document from the **Course Catalog Approvals** UI, with an API endpoint, persistent state, audit history, and meaningful tests.

Expected behavior:
1. Add a staff-only endpoint such as `POST /api/v1/catalog/uploads/{upload_id}/reject` protected with existing admin auth; require validated reviewer ID and nonempty rejection reason.
2. Persist rejected state in the original upload's manifest **atomically**; record timestamp/reviewer/reason/audit event; preserve uploaded evidence for audit, never expose secrets.
3. Rejection of a `pending_review` or `blocked_incomplete` upload is permitted. Rejected uploads must not be approvable or publishable. Enforce these restrictions in server-side logic, not UI alone. Duplicate upload of the same file must not silently reset rejected status.
4. Do not allow rejection to silently unpublish or corrupt a course already approved/published from that upload. Define safe conflict behavior (typically require the separate course withdrawal flow first), test it, and explain the rule.
5. Add Reject button/form and a required reason + reviewer to `frontend/pages/4_Course_Approvals.py`; show rejected status and audit detail; prevent accidental approvals; provide appropriate errors/confirmations.
6. Preserve existing Approve / Publish / Withdraw functionality and existing source hash integrity safeguards. No deletion of approved RAG data without explicit withdrawal. Consider existing `catalog_events` schema and whether upload-level events should be separate.
7. Add focused offline unit/API tests: allowed transition, missing/invalid reason, missing/wrong admin key, repeated rejection, rejected cannot approve, rejected cannot publish, duplicate upload behavior, published-course protection, audit persistence, UI behavior where practical.
8. Verify affected tests; run the broader offline test suite. Do not claim tests passed unless actually executed.
9. Give short summary: edited files, behavior, tests, known limits; STOP and ask the user to continue for next stage.

## Original later roadmap (implementation status is recorded above and in progress log)

1. **Approved-catalog student cutover:** finish `backend/app/assistant/course_matcher.py` source switch to published SQLite catalog, `backend/app/main.py` chat answer switch, `backend/app/assistant/personalized_recommendation.py` retrieval switch, and Streamlit copy; keep synthetic test fixtures isolated. Validate end-to-end behavior with zero published courses, approved courses, updates, and withdrawal.
2. **AI-assisted extraction:** extract structured course metadata from uploaded documents using deterministic parsing and, where appropriate, an LLM grounded by source/page evidence; staff reviews/edits before approval. Never invent missing fields, prices, prerequisites or certification. Decide/handle multi-course source documents thoughtfully.
3. **Document Generation Agent:** from published/approved course data, generate professional DOCX/PDF outputs (course description, proposal, curriculum as supported), source traceability, staff review/approval, secure download endpoints and Streamlit UI, Arabic/English Unicode support, actual content instead of prewritten templates masquerading as generated output.
4. **Hardening/integration:** authentication and RBAC beyond shared dev key, validation, upload-security controls, retries, logs, multi-worker concurrency, tests, deployment/docs; coordinate shared interfaces with Faris and Ahmed without taking their assigned feature work.

## Execution agreement with user

- Work ONLY on `dev/abdulrahman` and on this user's assigned modules. Shared interfaces may be adjusted carefully; avoid edits to Faris's RFP Agent or Ahmed's assigned work unless explicitly authorized.
- Inspect before editing and make minimal, localized changes to the existing architecture; no unnecessary rewrites, packages, or speculative improvements.
- One deliverable/milestone at a time: inspect -> short plan -> implement -> focused tests -> relevant regression tests -> concise explanation -> STOP. User can ask questions and explicitly say `continue` to proceed.
- Prioritize tested code over verbose prose. Be concise and economical with tokens; do not repeatedly dump entire files or repository listings.
- Maintain `docs/abdulrahman_progress.md` (create if absent): completed work, relevant interfaces, exact verification commands/results, pending task, and blockers. Keep documentation professional and truthful.
- If changes depend on teammates' incomplete modules, build/verify with well-defined interfaces/fakes and explicitly wait for their actual integration. Do not fabricate success or stub production functionality.
- Do not make unauthorized external API calls or spend Gemini quotas unnecessarily. Use mocked/fake services for unit tests and explicit opt-in for real external calls.
- Store credentials only in `.env`/appropriate secrets configuration, never in Git or test output.
