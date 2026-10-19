
import re

from backend.app.ingestion.markdown_loader import load_markdown
from backend.app.ingestion.course_normalizer import normalize_document


CATALOG_FILES = [
    "data/samples/course_catalog.md",
    "data/samples/alternative_catalog.md",
]


def load_catalog():
    courses = []

    for file_path in CATALOG_FILES:
        document = load_markdown(file_path)
        courses.extend(normalize_document(document))

    return courses


def parse_egp(value):
    """Parse explicit EGP prices or budgets."""
    if not value:
        return None

    text = str(value).strip().replace(",", "")

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(?:EGP|جنيه|جنيه مصري)",
        text,
        flags=re.IGNORECASE,
    )

    return float(match.group(1)) if match else None


def normalize_format(value):
    """Normalize common training format names."""
    if not value:
        return None

    text = str(value).lower().strip()

    aliases = {
        "online": "online",
        "أونلاين": "online",
        "عن بعد": "online",
        "hybrid": "hybrid",
        "هجين": "hybrid",
        "on-site": "onsite",
        "onsite": "onsite",
        "in-person": "onsite",
        "حضوري": "onsite",
    }

    return aliases.get(text)


def evaluate_course(course, profile):
    """Check explicit course constraints without an LLM."""

    conflicts = []
    unknowns = []

    requested_format = normalize_format(
        profile.get("training_format")
    )

    available_format = normalize_format(
        course.get("training_format")
    )

    if requested_format:
        if available_format is None:
            unknowns.append("Training format is unknown")
        elif requested_format != available_format:
            conflicts.append(
                "Training format does not match preference"
            )

    budget_text = profile.get("budget")
    budget = parse_egp(budget_text)

    if budget_text and budget is None:
        raise ValueError(
            "Budget must specify an EGP amount, "
            "for example: 4000 EGP"
        )

    if budget is not None:
        price = parse_egp(course.get("price"))

        if price is None:
            unknowns.append("Course price is unknown")
        elif price > budget:
            conflicts.append(
                f"Course price exceeds budget by "
                f"{price - budget:.0f} EGP"
            )

    if conflicts:
        status = "excluded"
    elif unknowns:
        status = "needs_verification"
    else:
        status = "eligible"

    return {
        "course_id": course.get("course_id"),
        "title": course["title"],
        "training_format": course.get("training_format"),
        "price": course.get("price"),
        "status": status,
        "conflicts": conflicts,
        "unknowns": unknowns,
        "source_file": course["source_file"],
    }


def match_courses(profile):
    """Evaluate every catalog course against learner constraints."""

    courses = load_catalog()

    return [
        evaluate_course(course, profile)
        for course in courses
    ]


if __name__ == "__main__":
    profile = {
        "background": (
            "Computer Science graduate with basic Python"
        ),
        "skill_level": "Beginner",
        "career_goal": "Becoming a Data Scientist",
        "training_format": "Hybrid",
        "budget": "4000 EGP",
        "availability": "10 hours",
    }

    results = match_courses(profile)

    for course in results:
        print("\nCourse:", course["title"])
        print("Status:", course["status"])
        print("Conflicts:", course["conflicts"])
        print("Unknowns:", course["unknowns"])

    eligible = [
        course for course in results
        if course["status"] == "eligible"
    ]

    assert len(results) == 5
    assert len(eligible) == 0

    ml_course = next(
        course for course in results
        if course["course_id"] == "CRS-002"
    )

    assert ml_course["status"] == "excluded"
    assert any(
        "1500 EGP" in reason
        for reason in ml_course["conflicts"]
    )

    print("\nCourse matching test PASSED!")
    print("Confirmed eligible courses:", len(eligible))
