# REX AI — Course Document Upload / Review (increment 1)

> Historical upload-package notes. The current checkout also implements approval/rejection, approved-only student integration and Document Generation. Use `docs/SPRINT2_TA_WALKTHROUGH.md` for current setup and `docs/abdulrahman_progress.md` for actual results.

This increment adds staff-controlled **PDF / DOCX / Markdown** uploads, reuses the project's existing document loader and RAG chunker, and stores review packages on disk with checksum-based deduplication.

**It does not yet index unapproved documents or add them to the live catalog.** That is intentional: the next increment adds reviewed course metadata, approval, Gemini embedding, Chroma upsert, live catalog access, and rollback/reprocessing.

## Install into your local `dev/abdulrahman` checkout

Copy the `backend`, `frontend`, and `tests` folders from this ZIP into your repository root, preserving the folder structure. They create new files; they do not replace your existing modules.

1. In `requirements.txt`, ensure `python-multipart>=0.0.9` is present; `fastapi`, `python-docx`, `pymupdf`, `tiktoken` and `python-dotenv` must already be installed. Run `python -m pip install -r requirements.txt`.
2. In `backend/app/main.py`, add `from backend.app.catalog.upload_router import router as catalog_router` with the other imports; add `app.include_router(catalog_router)` immediately after `app = FastAPI(...)`.
3. Set an unshared, strong secret in the local `.env` file: `REX_CATALOG_ADMIN_KEY=<random key>`. Generate the key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Never commit `.env`.
4. Add `data/catalog/` to `.gitignore`. Optionally set `REX_CATALOG_DATA_DIR=./data/catalog` in `.env` (default is the project-root `data/catalog`).
5. Start `python -m uvicorn backend.app.main:app --reload`.
6. Start `python -m streamlit run frontend/app.py`, navigate to **Course Documents**, paste the catalog admin key, and upload a real PDF, DOCX, or Markdown course document.
7. Run `python -m pytest tests/test_course_uploads.py -v` then `python -m pytest tests/ --ignore=tests/test_gemini_connection.py -q`.

Check `http://127.0.0.1:8000/docs` for:
- `POST /api/v1/catalog/uploads`
- `GET /api/v1/catalog/uploads`
- `GET /api/v1/catalog/uploads/{upload_id}`

All endpoints require `X-API-Key`. A second upload of the same bytes should report `already_uploaded: true`. OCR warnings and pages without text are preserved; no document is automatically approved.

**Restrictions:** current upload limit is 10 MiB; one file at a time; local persistent staging. The file content should be reviewed by an authorized staff member before making it available to learners. A shared deployment will also require TLS, proper staff account authentication/roles, server-side audit logs, antivirus/file scanning, rate limits, and durable backups.
