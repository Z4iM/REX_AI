
from backend.app.assistant.qualification import (
    QualificationSession,
    process_qualification,
)


def reach_budget_question(initial_request):
    session = QualificationSession()

    messages = [
        initial_request,
        "Computer Science",
        "Beginner",
        "Data Analyst",
        "Online",
    ]

    for message in messages:
        process_qualification(session, message)

    assert session.current_step == 4

    return session


def test_invalid_budget_does_not_advance():
    session = reach_budget_question(
        "I want to learn Data Science"
    )

    result = process_qualification(session, "4000")

    assert result["status"] == "question"
    assert session.current_step == 4
    assert session.completed is False
    assert "EGP" in result["reply"]
    assert "budget" not in session.answers


def test_valid_budget_advances():
    session = reach_budget_question(
        "I want to learn Data Science"
    )

    result = process_qualification(
        session,
        "4000 EGP",
    )

    assert result["status"] == "question"
    assert session.current_step == 5
    assert session.answers["budget"] == "4000 EGP"

    final = process_qualification(session, "10 hours")

    assert final["status"] == "ready"
    assert session.completed is True


def test_budget_can_be_skipped():
    session = reach_budget_question(
        "I want to learn Data Science"
    )

    result = process_qualification(session, "skip")

    assert result["status"] == "question"
    assert session.current_step == 5
    assert session.answers["budget"] is None


def test_arabic_budget_validation():
    session = reach_budget_question(
        "عايز أتعلم تحليل البيانات"
    )

    invalid = process_qualification(
        session,
        "5000",
    )

    assert invalid["status"] == "question"
    assert session.current_step == 4
    assert "الجنيه" in invalid["reply"]

    valid = process_qualification(
        session,
        "5000 جنيه",
    )

    assert valid["status"] == "question"
    assert session.current_step == 5
    assert session.answers["budget"] == "5000 جنيه"
