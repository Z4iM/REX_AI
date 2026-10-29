
import os
import requests
import streamlit as st


API_URL = os.getenv("REX_API_URL", "http://127.0.0.1:8000").rstrip("/")

from frontend.ui import header
header("Ask REX", "Talk about your learning goals, explore a learning path, or ask about approved courses. Guided course recommendations are available below.")

# ---------------------------------
# Check FastAPI connection
# ---------------------------------
try:
    health = requests.get(
        f"{API_URL}/health",
        timeout=5
    )

    health.raise_for_status()

    pass

except requests.exceptions.RequestException:
    st.error(
        "Cannot connect to FastAPI. "
        "Make sure the backend is running."
    )
    st.stop()


# ---------------------------------
# Chat history
# ---------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    st.info("Start with a greeting or tell REX what you want to learn. Course details come from published, approved academy information.")


# Display previous messages
for message in st.session_state.messages:

    with st.chat_message(message["role"], avatar=":material/person:" if message["role"] == "user" else ":material/assistant:"):
        st.markdown(message["content"])
        if message.get("mode") == "LEARNER_GUIDANCE":
            st.caption("General learning guidance · Course facts require approved sources.")

        if message.get("sources"):
            with st.expander("View Sources"):

                for source in message["sources"]:
                    st.write(
                        f"[{source['source_id']}] "
                        f"{source['course']}"
                    )

                    st.caption(
                        f"Section: {source['section']} | "
                        f"File: {source['file']}"
                    )


# ---------------------------------
# User input
# ---------------------------------
prompt = st.chat_input(
    "Say hello, describe your goals, or ask about a course...",
    max_chars=1000,
)

if prompt:

    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
    })

    try:
        with st.spinner("REX AI is thinking..."):

            response = requests.post(
                f"{API_URL}/api/v1/chat",
                json={"message": prompt, "history": [
                    {"role": m["role"], "content": m["content"][:4000]}
                    for m in st.session_state.messages[:-1][-12:]
                ]},
                timeout=180,
            )

            response.raise_for_status()
            result = response.json()

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
            "mode": result.get("mode", "APPROVED_CATALOG"),
        })

    except requests.exceptions.RequestException:
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                "Sorry, I couldn't process your request. "
                "Please try again."
            ),
        })

    st.rerun()
from frontend.guided_recommendation import render_guided_recommendation

render_guided_recommendation()
