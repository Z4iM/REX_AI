
import pytest

from backend.app.assistant.course_matcher import (
    evaluate_course,
    normalize_level,
    match_courses,
)


def make_course(level):
    return {
        "course_id": "TEST-LEVEL",
        "title": "Test Course",
        "level": level,
        "training_format": "Online",
        "price": "3200 EGP",
        "source_file": "test_catalog.md",
    }


def make_profile(level):
    return {
        "skill_level": level,
        "training_format": "Online",
        "budget": "4000 EGP",
    }


@pytest.mark.parametrize(
    "course_level, expected",
    [
        ("Beginner", "eligible"),
        ("Intermediate", "excluded"),
        ("Advanced", "excluded"),
    ],
)
def test_beginner_matching(course_level, expected):
    result = evaluate_course(
        make_course(course_level),
        make_profile("Beginner"),
    )

    assert result["status"] == expected


def test_advanced_learner_can_take_intermediate():
    result = evaluate_course(
        make_course("Intermediate"),
        make_profile("Advanced"),
    )

    assert result["status"] == "eligible"


def test_missing_learner_level():
    result = evaluate_course(
        make_course("Beginner"),
        make_profile(None),
    )

    assert result["status"] == "needs_verification"
    assert "Learner skill level is unknown" in result["unknowns"]


def test_unknown_course_level():
    result = evaluate_course(
        make_course(None),
        make_profile("Beginner"),
    )

    assert result["status"] == "needs_verification"
    assert "Course skill level is unknown" in result["unknowns"]


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Beginner", "beginner"),
        ("INTERMEDIATE", "intermediate"),
        ("advanced", "advanced"),
        ("مبتدئ", "beginner"),
        ("متوسط", "intermediate"),
        ("متقدم", "advanced"),
        ("Unknown", None),
    ],
)
def test_normalize_level(value, expected):
    assert normalize_level(value) == expected


def test_conflict_overrides_unknown():
    course = make_course("Advanced")
    course["price"] = None

    result = evaluate_course(
        course,
        make_profile("Beginner"),
    )

    assert result["status"] == "excluded"
    assert result["conflicts"]
    assert "Course price is unknown" in result["unknowns"]


def test_advanced_catalog_course_excluded(monkeypatch):
    monkeypatch.setattr("backend.app.assistant.course_matcher.load_catalog", lambda: [
        {**make_course("Advanced"), "course_id": "CL-202"}
    ])
    results = match_courses(make_profile("Beginner"))

    cloud = next(
        course
        for course in results
        if course["course_id"] == "CL-202"
    )

    assert cloud["status"] == "excluded"
    assert any(
        "above learner level" in reason
        for reason in cloud["conflicts"]
    )
