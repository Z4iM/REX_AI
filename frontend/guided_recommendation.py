
import os
import requests
import streamlit as st


API_URL = os.getenv("REX_API_URL", "http://127.0.0.1:8000").rstrip("/")


def render_guided_recommendation():

    st.divider()
    st.header("Help me choose a course")

    st.caption(
        "Answer a few questions and REX AI will help "
        "you find suitable courses."
    )
    st.caption("Learning answers are stored for up to seven days and used with the configured Gemini provider for recommendations. "
               "Keep sensitive personal information out of learning answers. Contact details are optional and stay in the staff system.")


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

    if st.button("Start again"):

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

        st.success("Your learner profile is ready!")

        with st.expander("Optional academy follow-up"):
            with st.form("learner_follow_up"):
                lead_name = st.text_input("Your name", max_chars=120)
                lead_email = st.text_input("Email address (or provide a phone number)", max_chars=254)
                lead_phone = st.text_input("Phone number (optional)", max_chars=40)
                consent = st.checkbox("I agree that academy staff may use my contact details and learner profile for training follow-up, for up to 30 days.")
                save_contact = st.form_submit_button("Save follow-up request")
            if save_contact:
                if not consent or len(lead_name.strip()) < 2 or not (lead_email.strip() or lead_phone.strip()):
                    st.error("Enter your name, a contact method, and explicit consent.")
                else:
                    try:
                        saved = requests.post(f"{API_URL}/api/v1/qualification/{st.session_state.qualification_id}/lead",
                            json={"name": lead_name, "email": lead_email.strip() or None,
                                  "phone": lead_phone.strip() or None, "consent": consent}, timeout=20)
                        saved.raise_for_status()
                        st.success("Follow-up request saved for academy staff.")
                    except requests.exceptions.RequestException:
                        st.error("Could not save your request. Check your contact details or try again.")
            if st.button("Withdraw follow-up consent"):
                try:
                    response = requests.delete(f"{API_URL}/api/v1/qualification/{st.session_state.qualification_id}/lead", timeout=20)
                    response.raise_for_status()
                    st.success("Your follow-up contact record was removed.")
                except requests.exceptions.RequestException:
                    st.error("Could not remove the follow-up request. Please retry.")

        with st.expander("Your learning preferences"):
            for label, value in st.session_state.qualification_profile.items():
                st.write(label.replace("_", " ").title() + ": " + str(value or "Not specified"))

        # Display constraint matching results
        matches = st.session_state.qualification_matches

        if matches is not None:

            with st.expander("How courses compare with your preferences"):
                for match in matches:
                    st.write(match.get("title") or match.get("course_id") or "Course")
                    st.write(match.get("match_reason") or match.get("reason") or match)
            st.caption("Matching preferences does not confirm prerequisites or overall suitability. Review the course requirements.")

        # ---------------------------------
        # 5. Personalized Recommendation
        # ---------------------------------

        st.subheader("AI Course Recommendation")

        recommendation = (
            st.session_state.qualification_recommendation
        )

        if recommendation is None:

            if st.button(
                "Generate My Recommendation",
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
                            timeout=180,
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
                    "View Recommendation Sources"
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
                "Only published, staff-reviewed courses are considered. "
                "Prerequisites and overall suitability require staff confirmation."
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
                        "If your session expired or was deleted, start a "
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
