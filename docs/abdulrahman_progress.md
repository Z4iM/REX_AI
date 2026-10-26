# AbdulRahman development progress

## 2026-10-26 — Document rejection milestone

### Local state inspected

- Actual repository: `D:\REX-AI`, branch `dev/abdulrahman`. The chat's initially supplied directory under `Documents\ChatGPT` was empty; the saved local project identified the existing checkout.
- Read `REX_AI_CODEX_HANDOFF.md` completely, the WBS/team assignments, architecture requirements, integration instructions, dependency manifests, ignore rules, existing local diff, catalog services, ingestion/review code, UI, and relevant tests.
- Upload, SQLite approval, approved Chroma publication, withdrawal, and staff pages were already installed as local untracked additions. Main already registers their routers. Rejection was missing.
- Existing unrelated tracked modifications and local additions were preserved. No checkout, merge, commit, push, PR, credential changes, or real academy data changes were performed.
- The student course matcher still loads sample catalogs, and chat/recommendation still need the approved-only integration milestone. The local `INTEGRATION.md` describes the earlier upload increment, not completed student integration.

### Implemented

- `POST /api/v1/catalog/uploads/{upload_id}/reject`, protected by the existing catalog administrator `X-API-Key` dependency.
- Validated JSON body: `reviewer` (2–120 trimmed characters), `reason` (1–4000 trimmed characters). Missing, blank, wrong-type, overlong and unexpected fields return 422. Missing/incorrect key returns 401; unconfigured administration returns 503.
- Pending and incomplete uploads can be rejected, including incomplete records without usable chunks. Existing source checksum and identity verification still apply.
- The upload's `review.json` atomically records `review_status=approval_status=rejected`, `indexing_allowed=false`, `rejected_by`, UTC `rejected_at`, `rejection_reason`, and an appended `review_history` event containing the previous review status. Source bytes, extracted sections, warnings and previous history remain intact.
- Upload audit events live in the manifest, separate from the existing course-level SQLite `catalog_events`. This keeps the rejection state and its audit event in one atomic replacement, avoiding a split manifest/database rejection write.
- Repeated rejection returns 409 and retains the first decision. Duplicate uploads retain the rejected manifest and return useful guidance to submit a corrected source.
- Approval checks the rejection state inside its SQLite write transaction. Publication checks before embedding/indexing and again at the final SQLite publication gate.
- Upload staging and rejection share SQLite's writer lock with course decisions, preventing concurrent duplicate staging or approval from overwriting a rejection.
- **Safe transition rule:** rejection returns 409 while any linked course is approved, index-failed, or published. Staff must explicitly withdraw every linked course first. Rejection never withdraws courses, edits their course audit history, or deletes vectors. Withdrawn course records remain available for staff audit.
- The Streamlit Approvals page provides a rejection form, required reviewer/reason, explicit confirmation, persistent success feedback after rerun, rejection history, and disabled rejection/approval actions for rejected sources. Backend conflict/error details are shown to staff.

### Files changed for this milestone

- `backend/app/catalog/catalog_service.py`
- `backend/app/catalog/approval_router.py`
- `backend/app/catalog/approved_index.py`
- `backend/app/catalog/upload_router.py`
- `frontend/pages/4_Course_Approvals.py`
- `tests/test_document_rejection.py` (new)
- `docs/abdulrahman_progress.md` (new)

### Verification performed

- Baseline: `python -m pytest tests/test_course_uploads.py tests/test_catalog_approval_publication.py -q` — **15 passed** before implementation, and again after the initial implementation.
- Focused: `python -m pytest tests/test_document_rejection.py tests/test_course_uploads.py tests/test_catalog_approval_publication.py -q --tb=short` — **49 passed**, including 34 new rejection cases.
- Regression: `python -m pytest tests/ --ignore=tests/test_gemini_connection.py -q --tb=short` — **140 passed**, two third-party deprecation warnings from Google GenAI and ChromaDB under Python 3.14.
- New tests cover authenticated API transitions, validation, incomplete sources, persisted audit/evidence, duplicate/repeated rejection, published-course protection, multiple linked courses, approval/publication gates, atomic-write failure and retry, source integrity, concurrent approval/rejection in both orders, and the actual Streamlit form/history using AppTest connected to an isolated TestClient.
- The first new test run exposed an invalid Markdown fixture (the existing loader requires level-two sections). Corrected the fixture; no production ingestion changes were needed.
- All test catalog data uses temporary directories; external Gemini/Chroma services were not called. The legacy `test_gemini_connection.py` was explicitly excluded because it makes a paid external request at import time; live integration was not verified.
- `git diff --check` reports an existing trailing-space line in `backend/app/assistant/course_matcher.py:131`, outside this milestone; preserved the user's local change.

### Remaining work / decisions

- This milestone is complete; stop for user review before continuing.
- Next: approved catalog student cutover, with empty catalog/update/withdrawal behavior tests. AI-assisted extraction and Document Generation remain later milestones.
- Ownership clarified by the user on 2026-10-26: AbdulRahman owns Document Generation in addition to the Assistant/catalog/RAG; Faris has completed RFP on his branch and will later own Curriculum; Ahmed owns only AI Marketing. Updated the handoff and WBS. RFP integration into this checkout remains unverified. The old separate accreditation gap-analysis work package has no confirmed owner under the revised assignments.
- Existing shared administrator authentication is reused; individual staff identity verification, broader RBAC/deployment hardening, and live embedding verification remain future work.

## 2026-10-26 — Sprint 2 continuation authorized

The user authorized completing all independent AbdulRahman Sprint 2 milestones without stopping between them. Teammate-dependent work must stop at its actual dependency. No commits or pushes were requested.

### Approved catalog integration and learner persistence

- Switched the student matcher, chat and personalized recommendation paths to published catalog records and approved-only retrieval. Removed production sample-catalog fallback and updated Streamlit copy.
- Closed a multi-course-document exposure path: publishing now indexes only explicitly reviewed catalog fields, under `verified_catalog_v2`; legacy raw upload vectors are excluded. Added a staff refresh-index endpoint/button for existing published courses.
- Publication rechecks the approval timestamp at its final gate. Answers/recommendations recheck source publication after generation so withdrawal or source replacement during an AI call fails closed.
- Qualification sessions now persist in SQLite, expire after seven days and can be deleted by the session-token holder. Updates are serialized to prevent lost conversation steps.
- Isolated all automated test storage; sample-dependent tests explicitly inject their fixtures. Live Gemini test collection is opt-in with `REX_RUN_LIVE_TESTS=1`.
- Verification: `python -m pytest tests/ -q --tb=short` — **148 passed, 1 skipped**, one Google dependency deprecation warning. No live Gemini calls.
- Fetched remote refs without merging or changing local files. `origin/dev/faris` exists at `4331c89`; inspected its protected RFP routes. The Assistant/catalog/course-document generator do not depend on RFP, so no merge/pull is needed for this workstream.

### Metadata extraction

- Added authenticated, persisted deterministic/Gemini extraction suggestions with reviewer audit and source quotes/chunk IDs/page metadata. Values without supported evidence remain unknown; price conversion never silently assumes currency.
- Multiple course candidates are kept separate. Conflicting fields are omitted and flagged. Suggestions prefill the approval form but still require explicit human verification and approval; extraction never indexes or publishes.
- Validation rejects unsupported AI quotes and rejected sources. Gemini input is bounded to avoid unbounded external cost.
- Focused verification: `python -m pytest tests/test_metadata_extraction.py tests/test_document_rejection.py tests/test_student_catalog.py -q --tb=short` — **46 passed**.

### Document Generation Agent

- Implemented three independent course-based types required by the Sprint 2 MVP: course description, course proposal and participant guide. Each supports English/Arabic and both DOCX/PDF.
- Real Gemini JSON generation is grounded in published course snapshots; there is no production fake/fallback output. A versioned template must first be approved by staff. Generated sections must cite valid source IDs, and original verified facts/source hashes are included in each file.
- Persisted immutable artifact versions, source snapshots, checksums, template approvals and reviewer audit in SQLite. Added draft review, approval, rejection, revision requests, revised generation, protected downloads, and the Streamlit Document Generation page.
- Final approval produces separate approved copies with reviewer/time labels while retaining draft evidence. Download/approval fails closed for withdrawn/updated sources or changed files. Approval-revision identifiers also isolate stale RAG vectors from later approvals of the same upload.
- Curriculum-dependent generation explicitly returns 409 pending Faris's approved Curriculum Agent interface; it does not fabricate a curriculum. Course-based generation is independent of RFP.
- Focused verification: `python -m pytest tests/test_document_generation.py -q --tb=short -x` — **21 passed**, generating real files with mocked Gemini only.
- Broader verification after these milestones: `python -m pytest tests/ -q --tb=short` — **173 passed, 1 skipped**, one Google dependency deprecation warning.

### MCP, consent-based leads and operational verification

- Added a real local stdio FastMCP server with published course search/details, approved evidence retrieval, staff template inspection, document draft generation and consent-based lead capture. Staff capabilities require `REX_MCP_STAFF_KEY` matching the existing admin key. No model tool can approve/publish content or send outbound messages.
- Completed the Assistant's documented consent-based lead output: validated contact details, explicit boolean consent, SQLite persistence/idempotent updates, 30-day expiry, staff-only listing/UI and withdrawal of consent. Contact records are not included in Gemini prompts. Session deletion removes its contact record under one writer lock; concurrent saves recheck session existence.
- Added a public published-course browsing page, configuration example with blank credentials, current OpenAPI export, a TA walkthrough and updated documentation/CI. No real credential values were edited.
- Real isolated Chroma integration passed: `python -m pytest tests/test_chroma_catalog_integration.py -q --tb=short` — **1 passed**, covering actual persistent storage, retrieval and withdrawal with offline embeddings.
- MCP/document UI/student-focused regression: `python -m pytest tests/test_document_generation.py tests/test_mcp_tools.py tests/test_student_catalog.py -q --tb=short` — **36 passed**.
- Full suite before the lead/provider-configuration additions: `python -m pytest tests/ -q --tb=short` — **182 passed, 1 skipped**, two dependency deprecation warnings. This included real subprocess startup of FastAPI/Streamlit and the stdio MCP protocol.
- Lead/MCP/student focused verification: **22 passed**. Provider-configuration/lead/document/student focused verification: **47 passed**. Final results are recorded below after the last complete run.

### Live provider and visual QA results

- Ran the bundled-runtime `tests/manual_document_visual_qa.py` against isolated, explicitly synthetic QA records outside academy storage. Visually inspected all six PDF pages covering three types in English/Arabic: no clipping, overlap or missing Arabic glyphs observed. These QA records are not published academy information.
- Attempted the required DOCX page renderer: `render_docx.py` failed with `FileNotFoundError: LibreOffice soffice.exe was not found on PATH`. DOCX files were created, reopened and structurally verified in tests; **DOCX page layout was not visually verified**. LibreOffice/Word rendering remains an environment validation limit, not a missing application generation endpoint.
- Opt-in live smoke command: `$env:REX_RUN_LIVE_TESTS='1'; python -m pytest tests/test_live_sprint2.py -q --tb=short`. Real Gemini embeddings, persistent Chroma indexing and the `index_refreshed` event succeeded in temporary test storage. Text generation failed before document generation; the first run hit a deadline and a small text-only diagnostic returned HTTP 504 `DEADLINE_EXCEEDED`.
- Checked the current model name without exposing credentials: the local configuration uses `gemini-3.8-flash`. Added documented model-compatible low-latency thinking settings and a bounded configurable text deadline (default 90 seconds). Official reference: https://ai.google.dev/gemini-api/docs/generate-content/thinking . The local model/key configuration was preserved.
- Repeated the live flow once after that concrete latency change: publication again succeeded; text generation returned **HTTP 503 UNAVAILABLE, high model demand**. The live test failed, not skipped/passed. Further paid retries stopped. Live end-to-end chat/recommendation/extraction/document generation is **not verified** while that provider is unavailable; there is no fake fallback.

### Scope completion and external dependencies

- Independent AbdulRahman Sprint 2 features are implemented locally. Curriculum-based documents stop at the missing approved Curriculum Agent interface from Faris. RFP does not block course-based documents, and no RFP merge was needed/performed. Remote `main` is confirmed at `4617bb5` (Faris PR #3 merge); `dev/faris` is `4331c89`.
- Do not describe the complete team project or live provider workflow as finished: Ahmed's Marketing and Faris's later Curriculum/full team integration are outside this checkout's delivered scope. Full LangGraph orchestration remains Sprint 3.
- Formal Git/team review remains pending: no commit, push, branch change or PR was made. The user's existing local work remains in the checkout.

### Final verification for this continuation

- `python -m pytest tests/ -q --tb=short` — **199 passed, 2 skipped, 2 warnings in 50.07 seconds**. The skipped checks are the explicitly opt-in Gemini connectivity and live workflow tests. Warnings are third-party deprecations, not suppressed failures.
- `python -m compileall -q backend frontend` — passed.
- `git diff --check` — passed. A separate trailing-whitespace scan of new backend/UI modules was clean.
- Exported `docs/openapi.sprint2.json` from the actual running application model: **25 API paths**.
- Preserved branch `dev/abdulrahman`, all unrelated local work and actual academy files. No commits, pushes, merges or PRs. No real credential values changed.
- Main implementation areas: `backend/app/catalog/`, `backend/app/documents/`, `backend/app/ai.py`, `backend/app/mcp_server.py`, Assistant catalog/recommendation/session/lead services, `backend/app/main.py`, student/staff Streamlit pages and guided flow, offline/live opt-in tests, CI, setup/example configuration and current documentation.
- Remaining acceptance limits: the configured live text model returned 503 high demand (prior timeout 504), so a successful full live generation run still needs provider availability; DOCX page-level visual QA needs a document renderer; Curriculum-based output awaits Faris's approved interface. All other independent features listed above are implemented and covered by the recorded checks.


## 2026-10-26 — Faris RFP integration, guided UI and isolated TA examples

### Authorization and preservation

- User explicitly authorized integrating Faris's RFP, generating fictional demonstration material, simplifying the UI and using configured paid APIs for tests. This supersedes the earlier no-RFP-needed decision, not the prohibition on commits/pushes.
- Verified `D:\REX-AI` and `dev/abdulrahman`, read the full handoff and inspected local changes before editing. Initial chat directory under Documents was empty. Fetched remote refs; integrated only the new RFP package from `origin/dev/faris` at `4331c89` (also present on remote main `4617bb5`). A whole-branch merge would remove newer local ingestion work, so shared files were integrated manually.
- Saved a source/diff recovery snapshot outside the repository at `C:\Users\littl\AppData\Local\Temp\rex-before-rfp-integration-_aco8_ue\local-work.zip`, excluding credentials and application data. No branch checkout, Git merge, commit, push or PR was performed. Existing academy uploads/review decisions were retained.

### Implementation

- Imported Faris's RFP source adapters, deterministic country/relevance/deadline/deduplication engine, Gemini summaries, SQLite opportunities/history/rejections/alerts, configuration/resources and original tests under `backend/app/agents/rfp/`. Added the host adapter in `backend/app/integrations/rfp.py`; all host RFP routes use the existing catalog staff key. Imported data cannot choose trusted provenance. Dashboard alerts are created even when outbound notification delivery is disabled; UI searches/imports do not send email or webhooks. RFP summary model selection now follows the shared configuration unless explicitly overridden.
- Added `backend/app/runtime.py` and the protected `backend/app/integrations/demo.py`. Demo mode uses separate catalog/Chroma/uploads/documents/sessions/leads and RFP storage under `data/demo/`. It rejects a configuration that resolves demo and academy catalogs to the same directory. Record origin is server-derived and independently checked for public listing, detail and RAG publication checks. Known demo markers are rejected in academy uploads/imports. Demo setup stages sources/suggestions, never grants automatic approval/publication, and preserves rejection on repeated loading. Online RFP search is disabled in demo mode; its fictional examples use local dashboard alerts only.
- Extended reviewed catalog fields with instructors/background, schedule, offers, target audience, career directions, admissions and validated FAQs. Added deterministic/AI extraction support and inclusion in approved-only search. Fixed Markdown ingestion dropping preamble text, including course fields and synthetic notices; retained existing section ordering and legacy normalizer behavior. Suggestions prefer complete course candidates and do not treat empty content headings as standalone courses.
- Reworked `frontend/app.py` into Home, learner pages and three numbered course-workflow steps, plus opportunity management, follow-up and demo setup. Added `frontend/ui.py` for one staff sign-in, shared errors and mode banners. Reused the Assistant in `frontend/assistant_page.py`; moved technical profile results out of the main learner flow. Reworked upload, catalog, approvals, documents, RFP and leads screens with simpler copy. RFP retains JSON/CSV/XLSX import through Faris's existing parser and makes clear that workflow status changes do not submit applications.
- Added `scripts/run_demo.py` to start isolated backend/UI on 8010/8510 together, with local startup checks/logs and child-process cleanup. Added `scripts/build_demo_examples.py` and `examples/ta_demo/`: four fictional complete course packs (English/Arabic, each MD/DOCX/PDF), matching references, fictional learner profiles, valid/expired/unsupported/duplicate tenders, incomplete/multiple-course sources, CSV exercise data and a ten-type authored teaching reference pack. All Office/PDF fixtures are explicitly labeled fictional and have two pages. The reference pack is authored example material; it does not implement future Curriculum/Marketing agents.
- Added runtime isolation, host RFP integration and full guided navigation/sign-in tests; adapted existing review/document UI tests. Added native RFP tests to CI, integrated dependencies and regenerated OpenAPI from the real application: **38 paths**. Updated README, handoff, `.env.example`, TA walkthrough and the example pack instructions.

### Verification

- Initial combined regression: 360 passed, 2 skipped, 1 failure. It exposed the coupling between dashboard alerts and outbound delivery; this was fixed and native RFP tests pass.
- Focused document/rejection/native-RFP API regression: **83 passed**.
- Demo/upload/extraction regression after the Markdown fix: **19 passed**.
- Final full offline command: `python -m pytest backend/app/agents/rfp/tests tests/ -q --tb=short` — **374 passed, 3 skipped, 2 third-party deprecation warnings in 56.48 seconds**. Skips are the opt-in embedding connectivity module and two live workflow tests. Real isolated Chroma, SQLite, source ingestion, document files, Streamlit actions, subprocess startup and MCP protocol are included.
- Latest focused checks after final UI copy/login recovery and example exercise additions: `python -m pytest tests/test_guided_ui.py tests/test_demo_rfp_integration.py -q --tb=short` — **13 passed**. Covers invalid/valid shared sign-in, navigation, staged suggestions, manual approval, RFP review, sign-out, origin/isolation, real PDF/Word/MD inputs, duplicate setup and rejection preservation.
- Actual configured `gemini-3.8-flash` again timed out during live grounded answering (HTTP 504). Provider model discovery confirmed available models. `gemini-3.5-flash` passed the live publication/answer/document workflow, so only the local text-model setting and code/example defaults were changed to 3.5. Credential values were not changed or printed. One intermediate live run failed during document generation; the final repeated run below passed. Provider output remains validated, with no fabricated fallback.
- Final paid command: `$env:REX_RUN_LIVE_TESTS='1'; python -m pytest tests/test_live_sprint2.py tests/test_document_generation.py -q --tb=short` — **25 passed, 2 warnings in 74.57 seconds**. This includes **both live workflows**: actual Gemini embeddings/persistent Chroma/retrieval/cited answer/AI document files, and actual recommendations/evidence-checked AI metadata extraction/Faris's RFP summary. All test storage was temporary. Website scraping/search, email/webhook delivery and tender submission were not exercised; no external messages were sent.
- Bundled DOCX renderer still reports missing `soffice.exe`. Resolved this QA limitation using installed Microsoft Word in hidden read-only mode to export all five DOCX examples to temporary QA PDFs. Rendered and visually inspected all **20 pages** across five PDF fixtures and five Word-rendered files, including Arabic; corrected title-border residue and awkward paragraph/page splits. These exports/PNGs remain temporary QA files, not project deliverables.
- `python -m compileall -q backend frontend scripts` — passed. `git diff --check` — passed (Git reports an informational LF/CRLF conversion warning for frontend/app.py). Backend `/health`, demo `/api/v1/system` and Streamlit health returned 200. Verified the actual home page visually in the browser. Demo servers are left running for the user on 8010/8510.

### Current limits and next team work

- Runtime AI document generation remains three course-based types, with staff-reviewed templates, immutable revisions and protected Word/PDF downloads. The ten-type example pack does not imply ten implemented generators. Curriculum-dependent generation awaits Faris's approved Curriculum/Accreditation interface. Ahmed's AI Marketing Agent, complete team orchestration, deployed individual accounts/RBAC/TLS and final team review remain pending.
- The shared staff key is development authentication, not individual staff-account identity. Review accuracy still requires a human; valid citations alone do not prove every generated sentence. Live provider availability can vary, and failed calls retain safe unpublished/draft state.
- Start future TA runs with `python scripts/run_demo.py`; follow `examples/ta_demo/README.md`. Use academy mode only for authorized real course sources. No actual academy information was invented or replaced by the demo package.


## 2026-10-26 — Sprint 2 release preparation

- Publishing request explicitly authorizes committing, pushing `dev/abdulrahman` and merging into `main`. Commit metadata uses the configured AbdulRahman Adham Git identity.
- Refreshed remote references and reconciled `origin/main` (`4617bb5`) with the completed local work. Preserved the integrated RFP engine, host authentication, isolated TA storage and guided frontend when resolving overlapping files. Faris's existing commits remain in the branch history.
- Scanned all 151 publishable files against configured credential values and common credential patterns: no matches. `.env`, local databases, uploads, generated runtime data and logs are excluded. Added binary attributes for PDF/DOCX examples and verified committed binary contents match their original files.
- Final integration validation: `python -m pytest tests/ backend/app/agents/rfp/tests/ -q --tb=short` — **374 passed, 3 opt-in checks skipped, 2 dependency deprecation warnings in 74.17 seconds**. Syntax compilation and staged whitespace checks passed. Paid workflows were already verified separately as recorded above and were not repeated for publishing.
- GitHub pull request and CI history record the subsequent branch push and main merge outcome.
