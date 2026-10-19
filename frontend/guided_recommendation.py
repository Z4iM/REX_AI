
import requests
import streamlit as st


API_URL = "http://127.0.0.1:8000"


def render_guided_recommendation():

    st.divider()
    st.header("🎯 Guided Course Recommendation")

    st.caption(
        "Answer a few questions and REX AI will help "
        "you find suitable courses."
    )

    st.warning(
        "SYNTHETIC DEMO: All course information is fictional "
        "and used for development and testing."
    )

    # ---------------------------------
    # 1. Initialize Session State
    # ---------------------------------

    if "qualification_id" not in st.session_state:
        st.session_state.qualification_id = None

    if "qualification_messages" not in st.session_state:
        st.session_state.qualification_messages = []

    if "qualification_status" not in st.session_state:
        st.session_state.qualification_status = "new"

    if "qualification_profile" not in st.session_state:
        st.session_state.qualification_profile = {}

    if "qualification_matches" not in st.session_state:
        st.session_state.qualification_matches = None

    if "qualification_recommendation" not in st.session_state:
        st.session_state.qualification_recommendation = None

    # ---------------------------------
    # 2. Reset Qualification
    # ---------------------------------

    if st.button("🔄 Start New Qualification"):

        st.session_state.qualification_id = None
        st.session_state.qualification_messages = []
        st.session_state.qualification_status = "new"
        st.session_state.qualification_profile = {}
        st.session_state.qualification_matches = None
        st.session_state.qualification_recommendation = None

        st.rerun()

    # ---------------------------------
    # 3. Display Conversation History
    # ---------------------------------

    for message in st.session_state.qualification_messages:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    status = st.session_state.qualification_status

    # ---------------------------------
    # 4. Completed Qualification
    # ---------------------------------

    if status == "ready":

        st.success("✅ Your learner profile is ready!")

        st.subheader("📋 Collected Profile")

        st.json(
            st.session_state.qualification_profile
        )

        # Display constraint matching results
        matches = st.session_state.qualification_matches

        if matches is not None:

            st.subheader("📊 Course Constraint Results")

            st.dataframe(
                matches,
                width="stretch",
                hide_index=True,
            )

            st.caption(
                "These results evaluate budget and training "
                "format only. They do not establish overall "
                "course suitability."
            )

        st.divider()

        # ---------------------------------
        # 5. Personalized Recommendation
        # ---------------------------------

        st.subheader("🤖 AI Course Recommendation")

        recommendation = (
            st.session_state.qualification_recommendation
        )

        if recommendation is None:

            if st.button(
                "🎯 Generate My Recommendation",
                type="primary",
                key="generate_recommendation",
            ):

                session_id = (
                    st.session_state.qualification_id
                )

                try:

                    with st.spinner(
                        "REX AI is analyzing your profile..."
                    ):

                        response = requests.post(
                            f"{API_URL}/api/v1/qualification/"
                            f"{session_id}/recommendation",
                            timeout=120,
                        )

                        response.raise_for_status()

                        result = response.json()

                        st.session_state.qualification_recommendation = (
                            result
                        )

                    st.rerun()

                except requests.exceptions.Timeout:

                    st.error(
                        "The recommendation request timed out. "
                        "Please try again."
                    )

                except requests.exceptions.HTTPError as exc:

                    status_code = (
                        exc.response.status_code
                        if exc.response is not None
                        else None
                    )

                    if status_code == 404:

                        st.error(
                            "Your conversation session was not found. "
                            "Please start a new qualification."
                        )

                    elif status_code == 409:

                        st.error(
                            "Please complete the qualification "
                            "before requesting a recommendation."
                        )

                    else:

                        st.error(
                            "The recommendation service returned "
                            "an error. Please try again."
                        )

                except requests.exceptions.RequestException:

                    st.error(
                        "Cannot connect to the REX AI backend. "
                        "Please check that FastAPI is running."
                    )

        # ---------------------------------
        # 6. Display Recommendation
        # ---------------------------------

        recommendation = (
            st.session_state.qualification_recommendation
        )

        if recommendation:

            st.success("Recommendation generated successfully!")

            st.markdown("### REX AI Recommendation")

            st.markdown(
                recommendation.get(
                    "answer",
                    "No recommendation was generated."
                )
            )

            result_status = recommendation.get("status")

            if result_status == "no_confirmed_match":

                st.info(
                    "No course is confirmed to satisfy all "
                    "checked constraints. Review the conflicts "
                    "and missing information."
                )

            elif result_status == "insufficient_evidence":

                st.warning(
                    "Insufficient evidence was retrieved to "
                    "explain a suitable recommendation."
                )

            # Display eligible candidates
            eligible = recommendation.get(
                "eligible_courses", []
            )

            if eligible:

                st.subheader("✅ Eligible by Checked Constraints")

                st.dataframe(
                    eligible,
                    width="stretch",
                    hide_index=True,
                )

            # Display source references
            sources = recommendation.get("sources", [])

            if sources:

                with st.expander(
                    "📚 View Recommendation Sources"
                ):

                    for source in sources:

                        st.markdown(
                            f"**[{source['source_id']}] "
                            f"{source['course']}**"
                        )

                        st.caption(
                            f"Section: {source['section']} | "
                            f"File: {source['file']}"
                        )

            st.caption(
                "SYNTHETIC DEMO — These courses are not "
                "verified Andalusia Academy offerings."
            )

        return

    # ---------------------------------
    # 7. Collect Student Answers
    # ---------------------------------

    with st.form(
        "qualification_form",
        clear_on_submit=True,
    ):

        message = st.text_input(
            "Your message",
            placeholder="I want to learn Data Science...",
        )

        submitted = st.form_submit_button(
            "Send",
            type="primary",
        )

    if submitted:

        message = message.strip()

        if not message:

            st.warning("Please enter a message.")
            return

        if not any(char.isalnum() for char in message):

            st.warning(
                "Please enter meaningful text or numbers."
            )
            return

        # ---------------------------------
        # 8. Send Answer to FastAPI
        # ---------------------------------

        try:

            response = requests.post(
                f"{API_URL}/api/v1/qualification",
                json={
                    "message": message,
                    "session_id": (
                        st.session_state.qualification_id
                    ),
                },
                timeout=30,
            )

            response.raise_for_status()

            result = response.json()

        except requests.exceptions.RequestException:

            st.error(
                "Could not continue qualification. "
                "Check the backend connection. "
                "If the backend restarted, start a "
                "new qualification session."
            )

            return

        # ---------------------------------
        # 9. Update Session State
        # ---------------------------------

        st.session_state.qualification_id = (
            result["session_id"]
        )

        st.session_state.qualification_status = (
            result["status"]
        )

        st.session_state.qualification_profile = (
            result["profile"]
        )

        st.session_state.qualification_matches = (
            result.get("course_matches")
        )

        # Store conversation messages
        st.session_state.qualification_messages.extend([
            {
                "role": "user",
                "content": message,
            },
            {
                "role": "assistant",
                "content": result["reply"],
            },
        ])

        st.rerun()
