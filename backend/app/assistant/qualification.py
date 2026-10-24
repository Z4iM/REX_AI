from backend.app.assistant.course_matcher import (
    parse_egp,
    normalize_format,
)
from dataclasses import dataclass, field
import re


QUESTIONS = [
    {
        "field": "background",
        "en": "What is your educational background and previous experience?",
        "ar": "إيه خلفيتك الدراسية وخبرتك السابقة؟",
    },
    {
        "field": "skill_level",
        "en": "What is your current skill level: beginner, intermediate, or advanced?",
        "ar": "مستواك الحالي إيه: مبتدئ، متوسط، ولا متقدم؟",
    },
    {
        "field": "career_goal",
        "en": "What career goal are you working toward?",
        "ar": "إيه هدفك المهني اللي عايز توصله؟",
    },
    {
        "field": "training_format",
        "en": "Do you prefer online, on-site, or hybrid training?",
        "ar": "بتفضل التدريب أونلاين، حضوري، ولا هجين؟",
    },
    {
        "field": "budget",
        "en": "What is your approximate training budget?",
        "ar": "ميزانيتك التقريبية للتدريب كام؟",
    },
    {
        "field": "availability",
        "en": "How many hours per week can you dedicate to learning?",
        "ar": "تقدر تخصص كام ساعة أسبوعياً للتعلم؟",
    },
]


def detect_language(text):
    """Detect Arabic script in the initial request."""
    return "ar" if re.search(r"[\u0600-\u06FF]", text) else "en"


@dataclass
class QualificationSession:
    initial_request: str | None = None
    language: str = "en"
    answers: dict = field(default_factory=dict)
    current_step: int = 0
    completed: bool = False


def build_profile_query(session):
    """Combine the learner's supplied information for RAG."""

    lines = [
        f"Original learning interest: {session.initial_request}"
    ]

    for question in QUESTIONS:
        field_name = question["field"]
        value = session.answers.get(field_name)

        if value:
            lines.append(f"{field_name}: {value}")

    lines.append(
        "Recommend suitable courses based only on the "
        "available course catalog. Check prerequisites, "
        "skill level, and learner preferences. "
        "Do not invent course details."
    )

    return "\n".join(lines)


def process_qualification(session, message):
    """Process one student message and advance the conversation."""

    message = message.strip()

    if not message:
        raise ValueError("Message cannot be empty")

    if session.completed:
        raise ValueError("Qualification already completed")

    # First student message establishes the learning interest.
    if session.initial_request is None:
        session.initial_request = message
        session.language = detect_language(message)

        question = QUESTIONS[0]

        return {
            "status": "question",
            "reply": question[session.language],
            "profile": session.answers.copy(),
            "query": None,
        }

    # Save the answer to the current question.
    question = QUESTIONS[session.current_step]
    field_name = question["field"]

    skip_requested = message.casefold() in {
        "skip",
        "تخطي",
        "تخطى",
    }
    # Validate the requested training format.
    if (
        field_name == "training_format"
        and not skip_requested
        and normalize_format(message) is None
    ):
        reply = (
            "Please choose Online, On-site, or Hybrid. "
            "You can also type 'skip'."
            if session.language == "en"
            else
            "من فضلك اختار أونلاين، حضوري، أو هجين. "
            "وممكن تكتب تخطي."
        )

        return {
            "status": "question",
            "reply": reply,
            "profile": session.answers.copy(),
            "query": None,
        }


    # Validate the student's budget before advancing.
    if (
        field_name == "budget"
        and not skip_requested
        and parse_egp(message) is None
    ):
        reply = (
            "Please enter your budget in EGP, "
            "for example: 4000 EGP. "
            "Or type 'skip' if you prefer not to answer."
            if session.language == "en"
            else
            "من فضلك اكتب الميزانية بالجنيه المصري، "
            "مثلاً: 4000 جنيه. "
            "أو اكتب تخطي لو مش عايز تجاوب."
        )

        return {
            "status": "question",
            "reply": reply,
            "profile": session.answers.copy(),
            "query": None,
        }

    if skip_requested:
        session.answers[field_name] = None
    else:
        session.answers[field_name] = message

    session.current_step += 1


    # Ask the next question.
    if session.current_step < len(QUESTIONS):
        next_question = QUESTIONS[session.current_step]

        return {
            "status": "question",
            "reply": next_question[session.language],
            "profile": session.answers.copy(),
            "query": None,
        }

    # All follow-up questions processed.
    session.completed = True

    return {
        "status": "ready",
        "reply": (
            "Thanks! Your learner profile is ready."
            if session.language == "en"
            else "شكراً! ملفك التعليمي جاهز."
        ),
        "profile": session.answers.copy(),
        "query": build_profile_query(session),
    }


if __name__ == "__main__":
    session = QualificationSession()

    test_messages = [
        "I want to learn AI",
        "Computer Science graduate, basic Python experience",
        "Beginner",
        "I want to become a Data Scientist",
        "Online",
        "4000 EGP",
        "10 hours",
    ]

    for message in test_messages:
        print("\nSTUDENT:", message)

        result = process_qualification(session, message)

        print("REX:", result["reply"])
        print("STATUS:", result["status"])

    print("\nFINAL PROFILE:")
    print(session.answers)

    print("\nRAG QUERY:")
    print(result["query"])

    assert session.completed
    assert session.answers["skill_level"] == "Beginner"
    assert session.answers["training_format"] == "Online"
    assert result["status"] == "ready"

    print("\nQualification test PASSED!")
