import streamlit as st
from frontend.ui import api, header, require_staff
from frontend.components import record_picker, date_label
header("Learner follow-up", "People who asked the academy to contact them. No messages are sent automatically.")
require_staff()
result=api("GET","/api/v1/catalog/staff/leads")
items=(result or {}).get("items",[])
if not items:
    st.info("No follow-up requests yet. Learners can leave their details after completing the guided recommendation.")
else:
    selected=record_picker(items,key="lead-selected",id_field="lead_id",title_field="name",label="follow-up requests",statuses=False,
        details=lambda r:"Interested in: "+str(r.get("interest") or "Training"))
    if selected:
        item=next(r for r in items if r["lead_id"]==selected)
        with st.container(border=True):
            st.subheader(item["name"])
            st.write("Email: "+(item.get("email") or "Not provided"))
            st.write("Phone: "+(item.get("phone") or "Not provided"))
            st.write("Interested in: "+str(item["interest"]))
            for label,value in item["profile"].items():
                st.write(label.replace("_"," ").title()+": "+str(value or "Not specified"))
            st.caption("Consent received: "+date_label(item["consented_at"]))
        st.info("Use the academy’s approved contact process. This page does not send a message.")
