import streamlit as st
from frontend.ui import api, header
from frontend.components import task_view
from frontend.guided_recommendation import render_guided_recommendation

header("Learning advisor", "Ask a quick question or get help choosing a course.")
mode = task_view("learner_view", ["Ask REX", "Help me choose a course"])
if mode == "Help me choose a course":
    render_guided_recommendation()
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    st.write("Try: **What should I learn to start working with data?**")
    st.caption("For a specific academy course, include its name in your question.")


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

    with st.spinner("Preparing your answer…"):
        result = api("POST", "/api/v1/chat", staff=False, request_timeout=180,
                     json={"message": prompt, "history": [
                         {"role": m["role"], "content": m["content"][:4000]}
                         for m in st.session_state.messages[:-1][-12:]
                     ]})
    if result is None:
        st.session_state.messages.pop()
        st.stop()

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "sources": result["sources"],
        "mode": result.get("mode", "APPROVED_CATALOG"),
    })
    st.rerun()
