
import pytest

from backend.app.assistant.course_matcher import (
    parse_egp,
    normalize_format,
    evaluate_course,
    match_courses,
)


# ------------------------------------------
# Test Data
# ------------------------------------------

@pytest.fixture
def sample_course():
    return {
        "course_id": "TEST-001",
        "level": "Beginner",
        "title": "Python for Data Analytics",
        "training_format": "Online",
        "price": "3200 EGP",
        "source_file": "test_catalog.md",
    }


@pytest.fixture
def sample_profile():
    return {
        "background": "Computer Science graduate",
        "skill_level": "Beginner",
        "career_goal": "Data Analyst",
        "training_format": "Online",
        "budget": "4000 EGP",
        "availability": "10 hours",
    }


# ------------------------------------------
# Test 1: Valid Course
# ------------------------------------------

def test_eligible_course(sample_course, sample_profile):
    result = evaluate_course(
        sample_course,
        sample_profile,
    )

    assert result["status"] == "eligible"
    assert result["conflicts"] == []
    assert result["unknowns"] == []


# ------------------------------------------
# Test 2: Course Exceeds Budget
# ------------------------------------------

def test_course_exceeds_budget(
    sample_course,
    sample_profile,
):
    sample_profile["budget"] = "2000 EGP"

    result = evaluate_course(
        sample_course,
        sample_profile,
    )

    assert result["status"] == "excluded"

    assert any(
        "1200 EGP" in reason
        for reason in result["conflicts"]
    )


# ------------------------------------------
# Test 3: Training Format Mismatch
# ------------------------------------------

def test_training_format_mismatch(
    sample_course,
    sample_profile,
):
    sample_profile["training_format"] = "Hybrid"

    result = evaluate_course(
        sample_course,
        sample_profile,
    )

    assert result["status"] == "excluded"

    assert any(
        "Training format does not match" in reason
        for reason in result["conflicts"]
    )


# ------------------------------------------
# Test 4: Unknown Price
# ------------------------------------------

def test_unknown_price(
    sample_course,
    sample_profile,
):
    sample_course["price"] = "Not announced"

    result = evaluate_course(
        sample_course,
        sample_profile,
    )

    assert result["status"] == "needs_verification"
    assert "Course price is unknown" in result["unknowns"]


# ------------------------------------------
# Test 5: Unknown Training Format
# ------------------------------------------

def test_unknown_training_format(
    sample_course,
    sample_profile,
):
    sample_course["training_format"] = None

    result = evaluate_course(
        sample_course,
        sample_profile,
    )

    assert result["status"] == "needs_verification"

    assert (
        "Training format is unknown"
        in result["unknowns"]
    )


# ------------------------------------------
# Test 6: Conflict Takes Priority
# ------------------------------------------

def test_conflict_overrides_unknown(
    sample_course,
    sample_profile,
):
    sample_course["price"] = None
    sample_course["training_format"] = "Hybrid"

    result = evaluate_course(
        sample_course,
        sample_profile,
    )

    assert result["status"] == "excluded"
    assert len(result["conflicts"]) == 1
    assert len(result["unknowns"]) == 1


# ------------------------------------------
# Test 7: Exact Budget Boundary
# ------------------------------------------

def test_exact_budget_accepted(
    sample_course,
    sample_profile,
):
    sample_profile["budget"] = "3200 EGP"

    result = evaluate_course(
        sample_course,
        sample_profile,
    )

    assert result["status"] == "eligible"


# ------------------------------------------
# Test 8: Invalid Budget Rejected
# ------------------------------------------

def test_invalid_budget(
    sample_course,
    sample_profile,
):
    sample_profile["budget"] = "4000"

    with pytest.raises(ValueError):
        evaluate_course(
            sample_course,
            sample_profile,
        )


# ------------------------------------------
# Test 9: Price Parsing
# ------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("3200 EGP", 3200.0),
        ("3,200 EGP", 3200.0),
        ("3200 جنيه", 3200.0),
        ("3200 جنيه مصري", 3200.0),
        ("3200.50 EGP", 3200.50),
        ("Not announced", None),
        ("3200 USD", None),
    ],
)
def test_price_parsing(value, expected):
    assert parse_egp(value) == expected


# ------------------------------------------
# Test 10: Training Format Aliases
# ------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("Online", "online"),
        ("أونلاين", "online"),
        ("عن بعد", "online"),
        ("Hybrid", "hybrid"),
        ("هجين", "hybrid"),
        ("On-site", "onsite"),
        ("حضوري", "onsite"),
        ("Unknown format", None),
    ],
)
def test_training_format_aliases(value, expected):
    assert normalize_format(value) == expected


# ------------------------------------------
# Test 11: Deterministic Output
# ------------------------------------------

def test_matching_is_deterministic(
    sample_course,
    sample_profile,
):
    first = evaluate_course(
        sample_course,
        sample_profile,
    )

    second = evaluate_course(
        sample_course,
        sample_profile,
    )

    assert first == second


# ------------------------------------------
# Test 12: Real Synthetic Catalog
# ------------------------------------------

def test_complete_synthetic_catalog(monkeypatch):
    from backend.app.ingestion.markdown_loader import load_markdown
    from backend.app.ingestion.course_normalizer import normalize_document
    fixtures = []
    for path in ("data/samples/course_catalog.md", "data/samples/alternative_catalog.md"):
        fixtures.extend(normalize_document(load_markdown(path)))
    monkeypatch.setattr("backend.app.assistant.course_matcher.load_catalog", lambda: fixtures)
    profile = {
        "background": "Computer Science graduate",
        "skill_level": "Beginner",
        "career_goal": "Data Analyst",
        "training_format": "Online",
        "budget": "4000 EGP",
        "availability": "10 hours",
    }

    results = match_courses(profile)

    assert len(results) == 5

    by_id = {
        course["course_id"]: course
        for course in results
    }

    assert by_id["CRS-001"]["status"] == "eligible"
    assert by_id["CRS-002"]["status"] == "excluded"
    assert by_id["CRS-003"]["status"] == "excluded"
    assert by_id["AR-101"]["status"] == "needs_verification"
    assert by_id["CL-202"]["status"] == "excluded"

    assert sum(
        course["status"] == "eligible"
        for course in results
    ) == 1
