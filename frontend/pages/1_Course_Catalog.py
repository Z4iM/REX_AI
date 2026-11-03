"""Student catalog: published staff-verified records only."""
import streamlit as st
from frontend.ui import api, header
from frontend.components import record_picker, next_step
from frontend.course_cards import STYLE, render_course_card
header("Browse courses", "Explore published courses. Open a course for requirements, schedules and learning outcomes.")
result = api("GET", "/api/v1/catalog/courses", staff=False)
if result is None:
    st.stop()
courses = result["items"]
if not courses:
    next_step("No courses are listed yet", "You can still ask REX about learning goals and where to start.", "assistant_page.py", "Ask the Learning Advisor")
    st.stop()
st.html(STYLE)
selected = record_picker(courses, key="learner_course", id_field="course_id", label="courses",
                         statuses=False, render_card=render_course_card)
if selected is None:
    st.stop()
course=next(c for c in courses if c["course_id"]==selected)
st.divider()
st.subheader(course["title"])
st.page_link("assistant_page.py", label="Get help choosing a course", icon=":material/forum:")
with st.container():
    st.write(course["description"])
    price = f"{course['price_egp']:g} EGP" if course.get("price_egp") is not None else "Ask staff about pricing"
    st.write(" · ".join([course.get("level") or "Level unspecified", course.get("training_format") or "Delivery unspecified", price]))
    for label, field in [("Duration in hours", "duration_hours"), ("Instructor", "instructor_name"),
            ("About the instructor", "instructor_bio"), ("Location", "location"), ("Schedule", "schedule"), ("Offers", "offers"),
            ("Who this is for", "target_audience")]:
        if course.get(field) is not None:
            st.write(f"**{label}:** {course[field]}")
    for label, field in [("Prerequisites", "prerequisites"), ("What you will learn", "learning_outcomes"),
                         ("Admission requirements", "admission_requirements"), ("Career directions", "career_opportunities")]:
        if course.get(field):
            st.markdown("**" + label + "**")
            for item in course[field]:
                st.write("• " + item)
    for faq in course.get("faqs", []):
        st.markdown("**" + faq["question"] + "**")
        st.write(faq["answer"])
    st.caption("Details not listed here require confirmation from staff. Course code: " + course["course_id"])
