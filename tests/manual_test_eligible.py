
import json

from backend.app.assistant.personalized_recommendation import (
    recommend_courses,
)


profile = {
    "background": "Computer Science graduate with no programming experience",
    "skill_level": "Beginner",
    "career_goal": "Become a Data Analyst",
    "training_format": "Online",
    "budget": "4000 EGP",
    "availability": "10 hours",
}

print("Testing personalized recommendation...\n")

result = recommend_courses(
    profile=profile,
    initial_request="I want to learn data analytics from scratch",
    language="en",
)

print(json.dumps(
    result,
    ensure_ascii=False,
    indent=2
))

# Verify that eligible courses were found.
assert result["status"] == "candidates_found"

# The Python for Data Analytics course should qualify.
eligible_ids = {
    course["course_id"]
    for course in result["eligible_courses"]
}

assert eligible_ids == {"CRS-001"}

# Verify Gemini generated an answer.
assert result["answer"].strip()

# Verify the answer has traceable sources.
assert len(result["sources"]) > 0

# Citations must reference the eligible course.
assert all(
    source["course"] == "Course 1: Python for Data Analytics"
    for source in result["sources"]
)

# Verify synthetic mode.
assert result["mode"] == "SYNTHETIC_DEMO"

print("\nSUCCESSFUL MATCH TEST PASSED!")
