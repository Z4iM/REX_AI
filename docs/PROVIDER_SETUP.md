# AI provider setup

The default setup uses Groq's free text API tier and local SQLite full-text retrieval. No payment details or paid plan are required by the application configuration. Provider availability, free quotas and model access are controlled by the provider, not by REX.

1. Open https://console.groq.com/keys and sign in.
2. Select **Create API Key**, name it for this project and copy it once.
3. Save `GROQ_API_KEY=...` in the existing local `.env`. Do not replace the file or remove the staff key.
4. Use `REX_AI_PROVIDER=groq`, `GROQ_TEXT_MODEL=openai/gpt-oss-20b`, `REX_RETRIEVAL_BACKEND=sqlite` and `REX_ENABLE_AI_WEB_SEARCH=0`.
5. Restart the backend and Streamlit. If using the demo launcher, stop the old launcher before starting it again.

A quota error means the provider rejected the request because an account or model limit was reached. Wait and retry, check the account limits page or deliberately choose another available model. Replacing a key on the same limited account does not create additional quota. The application shows a sanitized error and never substitutes invented generated content.

Groq browser search is an optional separately priced tool. It is disabled unless `REX_ENABLE_AI_WEB_SEARCH=1` is deliberately configured. File imports and configured RSS/HTML sources remain available without it. Login-protected procurement portals require authorized manual exports; REX does not bypass their access controls.

Gemini remains supported by setting `REX_AI_PROVIDER=gemini` and supplying its key and model. Set `REX_RETRIEVAL_BACKEND=gemini` to use the existing Gemini/Chroma vector path. Existing Chroma collections must match their configured embedding model and dimensions. Switching to SQLite retrieval does not delete Chroma, unpublish existing courses or approve new records; published verified fields are indexed locally when searched.

Official references: [Groq quickstart](https://console.groq.com/docs/quickstart), [limits](https://console.groq.com/docs/rate-limits), [structured outputs](https://console.groq.com/docs/structured-outputs), [browser search](https://console.groq.com/docs/tool-use/built-in-tools/browser-search), [OpenCode models and external-client restrictions](https://opencode.ai/v2/docs/console/models/).

## RFP web search with LangSearch

Set `LANGSEARCH_API_KEY` in the backend's ignored local `.env`, then restart the backend. In Academy mode, open **Training opportunities → Add opportunities → Search public tenders**. REX calls LangSearch's hosted MCP `web_search` tool directly from the backend; there is no Codex MCP setup step for the application.

The connector uses twelve English and Arabic searches to find notices on UNGM, Etimad, UNDP Procurement Notices and Egyptian government portals. Only publicly indexed notices with readable fields can be imported; coverage depends on the search index. It uses the country and deadline stated in the notice, not the search index metadata. Existing relevance, expiry and deduplication checks still apply. Discovered opportunities require staff verification. This search does not use Groq or Gemini, access sign-in-only portals, submit bids, or send messages. No results can be a valid outcome; imports remain available separately.

The same search also reads publicly accessible Egypt training listings from GlobalTenders and Saudi Etimad leads from GCC Tender Alerts. These are secondary sources: every result remains marked for review, and access restrictions on original portals are respected. The public directory sources can still run when LangSearch is unavailable.

## Automatic course covers with Puter

New publications can generate an editorial cover in the background. The course goes live first and remains available if image generation fails. Covers are stored under the current catalog data directory, shown in the Course library, and linked only to the published course revision. Existing published courses are not regenerated. REX makes at most one automatic generation attempt per course revision; a timed-out or failed request is not retried automatically. Browsing the catalog only reads stored images.

1. Install Node.js 24 or later and run `npm --prefix scripts/puter ci --ignore-scripts` from the repository root.
2. Create an account token in [Puter's account dashboard](https://puter.com/dashboard#account). Set `PUTER_AUTH_TOKEN` in the ignored backend `.env` and restart FastAPI.
3. Publish a verified course as usual. Reopen or refresh Course library after the background job finishes.

Only the published title and a short part of its description are sent to Puter. The browser version of Puter uses the viewer's Puter account; this server integration uses the configured account and its limits. See [Puter's token instructions](https://developer.puter.com/tutorials/puter-auth-token/).
