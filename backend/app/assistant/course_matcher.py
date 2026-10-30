
import re

from backend.app.catalog.catalog_service import list_matching_courses


def load_catalog():
    """The public matcher has no fallback to sample or unapproved data."""
    return list_matching_courses()


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

LEVEL_RANK = {
    "beginner": 1,
    "intermediate": 2,
    "advanced": 3,
}


def normalize_level(value):
    """Normalize English and Arabic skill levels."""
    if not value:
        return None

    aliases = {
        "beginner": "beginner",
        "مبتدئ": "beginner",
        "مبتدئة": "beginner",

        "intermediate": "intermediate",
        "متوسط": "intermediate",
        "متوسطة": "intermediate",

        "advanced": "advanced",
        "متقدم": "advanced",
        "متقدمة": "advanced",
    }

    return aliases.get(str(value).strip().casefold())


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

    # Check learner level against course difficulty.
    learner_level = normalize_level(
        profile.get("skill_level")
    )

    course_level = normalize_level(
        course.get("level")
    )

    if learner_level is None:
        unknowns.append(
            "Learner skill level is unknown"
        )

    elif course_level is None:
        unknowns.append(
            "Course skill level is unknown"
        )

    elif LEVEL_RANK[course_level] > LEVEL_RANK[learner_level]:
        conflicts.append(
            f"Course level ({course_level}) is above "
            f"learner level ({learner_level})"
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
        "level": course.get("level"),
        "source_sha256": course.get("source_sha256"),
        "approval_revision": course.get("approval_revision"),
    }


def match_courses(profile):
    """Evaluate every catalog course against learner constraints."""

    courses = load_catalog()

    return [
        evaluate_course(course, profile)
        for course in courses
    ]
