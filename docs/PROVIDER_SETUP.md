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
