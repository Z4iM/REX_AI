import streamlit as st
from frontend.ui import api, header, require_staff

header("Learner follow-up", "People who asked the academy to contact them. No messages are sent automatically.")
require_staff()
result = api("GET", "/api/v1/catalog/staff/leads")
items = (result or {}).get("items", [])
if not items:
    st.info("No follow-up requests yet. Learners can leave their details after completing the guided recommendation.")
for item in items:
    with st.expander(item["name"]):
        st.write("Email:", item.get("email") or "Not provided")
        st.write("Phone:", item.get("phone") or "Not provided")
        st.write("Interested in:", item["interest"])
        st.write(item["profile"])
        st.caption("Consent received: " + item["consented_at"])
