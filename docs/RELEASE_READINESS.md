# Release readiness — October 29, 2026

The current working tree is ready for review and a feature-branch commit for controlled local academy use. This is not a public-production security certification or final academy acceptance. No commit, push, merge or branch switch was performed during the audit.

## Corrections

- Confined sample-pack paths to the configured directory; rejected traversal and symbolic links; validated manifests, file formats and size limits before staging. Sample downloads exclude unrelated root files, hidden files and runtime formats. Malformed packs return useful validation errors.
- Prevented demo storage from overlapping any configured academy storage directory, including an academy SQLite RFP database inside the demo tree.
- Added expanded-content and entry limits for Office files. Invalid DOCX/XLSX packages return validation feedback; Excel imports have bounded rows/columns and close workbooks.
- Required alignment results to cover every staff-verified framework criterion exactly once, rejecting missing, duplicate or invented criteria.
- Preserved instructor execution conflicts without rewriting a persisted action as a failed planning transaction. Health metadata now uses the application's actual version.
- Isolated test credentials, removed Gemini calls during test collection, and kept live-provider checks explicitly opt-in.
- Pinned direct dependencies to the versions tested in an isolated Python 3.14 installation. Moved Chroma to optional requirements because its upstream advisories remain unresolved; preserved the existing integration and stored data.
- Enabled CI for `dev/**` pushes, added default dependency auditing, expanded SQLite sidecar exclusions, clarified historical architecture documents and exported the current OpenAPI schema.

## Verification

Final default-installation checks:

- `python -B -m pytest tests/ backend/app/agents/rfp/tests/ -q --disable-warnings --maxfail=1`: **498 passed, 7 skipped**, 86.89 seconds. Skips cover six opt-in live-provider checks and the optional Chroma integration.
- Focused release, instructor and RFP checks before the final run: **195 passed, 1 skipped**.
- Earlier isolated installation with Chroma: **497 passed, 6 skipped**, including actual embedded Chroma persistence, retrieval and revocation. Subsequent Excel checks are covered by the final default run.
- `python -m pip check`: no broken requirements.
- `python -m pip_audit --local`: no known vulnerabilities in the audited default environment. This does not apply to existing environments retaining Chroma; see [security findings](SECURITY.md).
- Compilation and `git diff --check` passed. Git emitted line-ending notices only.
- The current OpenAPI snapshot matched the running application schema. Authentication checks exercised all **56 staff operations** without a key and received HTTP 401. Automated UI checks cover navigation, source review, document versions, curriculum, campaigns and instructor actions. Process-start tests run actual localhost API and Streamlit services.
- Publishable files and 216 historical branch file blobs were scanned for configured secret values and common credential patterns: no matches. This is a scoped scan, not proof that every possible secret format is detectable.
- No publishable runtime database, personal preparation material or hardcoded operator filesystem path was found. Existing personal-material deletions remain pending in the working tree.

## Remaining limits

Individual staff accounts/RBAC, public-hosting controls, managed deployment and real academy acceptance remain outstanding. Staff must verify real course sources, frameworks and generated output. Live provider availability and portal access were not re-tested during this offline audit. Online discovery remains optional and disabled by default; opportunity imports work independently. Campaign distribution is manual. The instructor uses allowlisted internal API tools; LangGraph and an instructor MCP client are historical design targets, not implemented features.

The original brief also requires authentic team contributions and final presentation/review. Passing automated tests does not complete those requirements. The employee guide was left untouched.
