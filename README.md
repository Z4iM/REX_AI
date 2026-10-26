
# REX AI – Smart Academy Multi-Agent System

## Project Overview
REX AI is a multi-agent AI system developed for Andalusia Academy to automate educational and administrative workflows.

## Team Members
- Faris Ahmed
- AbdulRahman Adham
- Ahmed AlAbiad

## AI Agents
1. REX Assistant – Course Recommendation
2. RFP & Tender Research Agent
3. Curriculum & Accreditation Agent
4. Educational Document Generation Agent
5. AI Marketing Agent

## Project Timeline
- Sprint 1: October 10–18, 2026
- Sprint 2: October 19–27, 2026
- Sprint 3: October 28–November 5, 2026

## Technology Stack
FastAPI, Streamlit, SQLite, Gemini, ChromaDB, PyMuPDF, python-docx and a local stdio FastMCP adapter.

## Local Sprint 2 workstream
AbdulRahman's `dev/abdulrahman` checkout implements staff course upload/review/rejection, approved-only publication and student catalog/RAG, persistent learner qualification, and the Educational Document Generation Agent. Generated documents require staff review and support English/Arabic DOCX and PDF.

Current responsibilities: AbdulRahman owns the Assistant/catalog/RAG and Document Generation; Faris owns RFP and later Curriculum; Ahmed owns AI Marketing. Teammates' branch status is separate from what is integrated into this checkout.

Start from the existing repository root:

```powershell
python -m pip install -r requirements-dev.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# In another terminal:
python -m streamlit run frontend/app.py
```

Use `.env.example` for configuration names; keep real credentials in the local ignored `.env`. Course publication, grounded answers and AI document generation require a working Gemini configuration. Never publish synthetic test fixtures as real academy information.

Run `python -m pytest tests/ -q` for offline tests. The paid Gemini smoke test is opt-in. See [the TA walkthrough](docs/SPRINT2_TA_WALKTHROUGH.md) for the full flow and known integration limits, and [the progress log](docs/abdulrahman_progress.md) for actual verification results.

## Guided TA demonstration and Faris RFP integration

Run `python scripts/run_demo.py` and open http://127.0.0.1:8510. Select **Demo setup** and follow the guided workflow. The [example pack](examples/ta_demo/README.md) contains fictional course documents in PDF/Word/Markdown, tender cases, learner profiles, rejection cases and teaching reference materials. Demo storage is separate from academy storage; examples still require human review and publication.

Faris's RFP engine from `origin/dev/faris` (`4331c89`) is integrated into the host FastAPI and Streamlit application with the existing staff key, persistent opportunity/history/alert storage, file imports and configured source discovery. No whole-branch merge was performed. Run `python -m pytest tests/ backend/app/agents/rfp/tests/ -q` to include both workstreams. See the current [TA walkthrough](docs/SPRINT2_TA_WALKTHROUGH.md) and [progress log](docs/abdulrahman_progress.md).
