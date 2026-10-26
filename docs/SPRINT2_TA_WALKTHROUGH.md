# Sprint 2 TA walkthrough

The easiest path is the isolated fictional demo. Its complete beginner instructions and expected results are in [examples/ta_demo/README.md](../examples/ta_demo/README.md).

## One command for the TA demo

```powershell
cd D:\REX-AI
python -m pip install -r requirements-dev.txt
python scripts/run_demo.py
```

Open http://127.0.0.1:8510. Choose **Demo setup**, sign in once, and follow its numbered steps. Use your existing staff key from `.env`; it is not printed or included in the examples. Ctrl+C stops the two processes started by this launcher. Close an existing demo before starting another on ports 8010/8510.

## What the pages do

| Page | Purpose |
|---|---|
| Home | Choose learner or staff work and find the demo walkthrough. |
| Browse courses | Read published course facts, instructors, schedules, offers, FAQs and requirements. |
| Ask REX | Ask questions with citations or complete a guided course recommendation; optionally request staff follow-up with explicit consent. |
| 1 · Add course documents | Upload PDF, Word or Markdown for review; scanned PDFs have an optional OCR setting. |
| 2 · Review & publish | Extract suggestions, check the original, edit verified fields, approve/publish, reject unsuitable sources, inspect history or explicitly withdraw a course. |
| 3 · Create documents | Approve a template, generate a course description/proposal/participant guide in English or Arabic, review/revise and download Word/PDF. |
| Training opportunities | Faris's RFP engine: import JSON/CSV/XLSX, filter Egypt/Saudi opportunities, identify expired/irrelevant/duplicate records, update workflow statuses and read dashboard alerts. Academy mode also supports configured online sources. |
| Learner follow-up | Staff-only consented contact requests and learning preferences. |
| Demo setup | Load isolated fictional examples and download a ZIP; it never automatically approves or publishes a course. |

## Academy mode

For actual approved academy information, use the standard servers instead:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# A second terminal:
python -m streamlit run frontend/app.py
```

The default mode is `academy`; the demo launcher overrides it for its child processes. `.env.example` documents configuration. Do not publish authored TA fixtures as actual academy offerings. The current tested text model is `gemini-3.5-flash`, with real embeddings configured separately. Health endpoints confirm the app is running; they do not prove provider availability. Failed provider calls show an error rather than returning fabricated text.

Uploads do not grant approval. Saved course approval does not grant publication. Publication becomes visible only after verified indexing. Source rejection preserves evidence and is blocked while linked active courses exist; withdraw them explicitly first. Changed or withdrawn source revisions invalidate their old RAG results and generated-document approval/downloads.

## Tests

```powershell
python -m pytest tests/ backend/app/agents/rfp/tests/ -q
python -m compileall -q backend frontend scripts
# Optional paid provider checks, using temporary isolated storage:
$env:REX_RUN_LIVE_TESTS='1'
python -m pytest tests/test_live_sprint2.py -q
Remove-Item Env:REX_RUN_LIVE_TESTS
```

Offline tests mock the AI boundary but include actual SQLite, real Chroma persistence, source-file parsing, rendered files, Streamlit actions and subprocess startup. Live checks cover real publication/search/answers, recommendations, AI extraction, document generation and Faris's summaries. They do not submit tenders or contact anyone. Current results are in [the progress log](abdulrahman_progress.md).

## Boundaries still pending

AbdulRahman's Assistant/catalog/RAG and three course-based Document Agent types are implemented, and Faris's RFP package is integrated from `origin/dev/faris` at `4331c89`. Faris's Curriculum/Accreditation Agent and Ahmed's AI Marketing Agent are not implemented by the authored reference pack. Their approved interfaces, full team orchestration, individual accounts/RBAC, deployment/TLS and final team review remain later work. Automated citation checks do not replace human semantic review.

Qualification sessions expire after seven days; consented leads expire after thirty days. Session IDs are private bearer tokens; deleting a session also removes its lead. Contact details are not sent to Gemini. Demo data uses separate SQLite, Chroma and file directories under `data/demo/`.

The local MCP server remains available through `python -m backend.app.mcp_server`. It exposes published evidence and limited staff draft/lead tools when the configured staff capability is present. It has no model-controlled approval, publication or outbound-message tools.
