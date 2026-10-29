# Security and deployment scope

REX AI is configured for a controlled local academy workspace. Staff endpoints require a shared administrator key and audit actions using a declared reviewer name. This is not individual account authentication or role-based access control. Public hosting requires HTTPS, individual accounts, authorization roles, rate limits, operational monitoring and a deployment review.

Course sources remain untrusted until human verification and publication. Source withdrawal invalidates downstream access; generated outputs require their own review. The instructor executes only allowlisted internal APIs, confirms every write and cannot send campaigns or RFP notifications. API keys belong in local environment configuration, never prompts or committed files.

Uploads are limited to 10 MiB. Office containers are checked before parsing, with at most 2,000 entries and 50 MiB expanded content. Demo sample files must remain inside their configured pack, exclude symbolic links, and have bounded sizes. Downloads include only recognized sample directories and file types; keep that directory dedicated to fictional sample content. Demo and academy storage roots must not overlap.

## Optional Chroma backend

The default dependency set excludes Chroma and uses SQLite FTS5. The optional `requirements-vector.txt` preserves existing Gemini/Chroma compatibility without changing or deleting stored vectors.

The October 29, 2026 dependency audit identified four distinct published advisories against Chroma 1.5.9; the audit database listed no fixed versions: PYSEC-2026-311, PYSEC-2026-3813, PYSEC-2026-3814 and PYSEC-2026-3815. One advisory appeared twice in the scan output. The findings concern Chroma server code execution or authorization. REX uses an embedded local client and does not mount Chroma's HTTP endpoints, which limits exposure but does not resolve upstream findings.

Do not launch or expose a Chroma HTTP server from this environment. Existing installations may still contain Chroma; moving it out of the default requirements does not uninstall it. Use a fresh virtual environment for the default SQLite installation. Operators retaining vector retrieval must evaluate the upstream findings and recheck for a patched release before deployment. Do not suppress audit findings to claim a clean result.

References: [upstream release/advisory tracking](https://github.com/chroma-core/chroma/issues/7909), [published advisory](https://osv.dev/vulnerability/PYSEC-2026-311).

## Verification

Run `python -m pip check`, `python -m pip_audit --local` and the offline test suite after dependency updates. CI audits the default installation. Optional vector integrations require a separate dependency audit and are not covered by a clean default-installation result. Keep runtime databases, generated files, secrets and SQLite sidecars out of version control, and back up operational storage separately.
