
import os
import requests
import streamlit as st


API_URL = os.getenv("REX_API_URL", "http://127.0.0.1:8000").rstrip("/")

from frontend.ui import header
header("Ask REX", "Ask a course question below, or use the guided recommendation further down the page.")

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


# Display previous messages
for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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
    "Ask REX AI about available courses..."
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
                json={"message": prompt},
                timeout=180,
            )

            response.raise_for_status()
            result = response.json()

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
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
