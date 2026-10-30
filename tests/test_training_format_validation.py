
from backend.app.assistant.qualification import (
    QualificationSession,
    process_qualification,
)


def reach_format_question(initial_request="I want to learn AI"):
    session = QualificationSession()

    messages = [
        initial_request,
        "Computer Science graduate",
        "Beginner",
        "Data Scientist",
    ]

    for message in messages:
        process_qualification(session, message)

    assert session.current_step == 3

    return session


def test_invalid_format_does_not_advance():
    session = reach_format_question()

    result = process_qualification(
        session,
        "Anything",
    )

    assert result["status"] == "question"
    assert session.current_step == 3
    assert "training_format" not in session.answers
    assert "Online" in result["reply"]


def test_valid_format_advances():
    session = reach_format_question()

    result = process_qualification(
        session,
        "Hybrid",
    )

    assert result["status"] == "question"
    assert session.current_step == 4
    assert session.answers["training_format"] == "Hybrid"


def test_format_can_be_skipped():
    session = reach_format_question()

    result = process_qualification(
        session,
        "skip",
    )

    assert result["status"] == "question"
    assert session.current_step == 4
    assert session.answers["training_format"] is None


def test_arabic_training_format():
    session = reach_format_question(
        "عايز أتعلم الذكاء الاصطناعي"
    )

    result = process_qualification(
        session,
        "أونلاين",
    )

    assert result["status"] == "question"
    assert session.current_step == 4
    assert session.answers["training_format"] == "أونلاين"
