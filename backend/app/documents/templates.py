"""Versioned layouts; an authenticated reviewer must approve their current hash."""
import hashlib
import json
from .brand import STYLE_VERSION

TEMPLATES = {
    "course_description": {
        "name": "Course description", "version": 1,
        "sections": ["Course overview", "Learning outcomes", "Entry requirements and practical details"],
        "purpose": "Describe the verified course to prospective learners. State unknown details explicitly.",
    },
    "course_proposal": {
        "name": "Course proposal", "version": 1,
        "sections": ["Proposed training", "Learning outcomes and audience considerations", "Delivery details and open questions"],
        "purpose": "Prepare a training proposal based on verified course facts. Do not invent client needs, dates, discounts, accreditation or commitments.",
    },
    "participant_guide": {
        "name": "Participant guide", "version": 1,
        "sections": ["Course orientation", "What you will learn", "Preparation and information to confirm"],
        "purpose": "Orient participants using the approved description, outcomes and prerequisites. Do not invent lessons, materials, schedules or assessments.",
    },
}


for _id, _name, _sections in [
    ("curriculum", "Curriculum", ["Course purpose and outcomes", "Modules and training hours", "Practice, assessments and capstone"]),
    ("facilitator_guide", "Facilitator guide", ["Instructor preparation", "Module facilitation plan", "Assessment and feedback guidance"]),
    ("presentation_outline", "Presentation outline", ["Opening and learning objectives", "Module presentation outline", "Activities and assessment recap"]),
    ("question_bank", "Question bank", ["Outcome mapping", "Questions and proposed answers", "Review guidance"]),
    ("assessment_rubrics", "Assessment rubrics", ["Assessment objectives", "Criteria and performance levels", "Scoring and feedback"]),
    ("capstone_brief", "Capstone project brief", ["Project objective and context", "Tasks and deliverables", "Evaluation criteria"]),
    ("assessment_plan", "Learning outcomes and assessment plan", ["Learning outcomes", "Assessment mapping and weights", "Implementation and review"]),
]:
    TEMPLATES[_id] = {"name": _name, "version": 1, "sections": _sections,
                      "requires_curriculum": True,
                      "purpose": "Develop this material from the selected approved curriculum and published course facts. Label newly proposed teaching content and require staff review."}


def template_hash(kind):
    return hashlib.sha256(json.dumps({**TEMPLATES[kind], "visual_style": STYLE_VERSION}, sort_keys=True).encode()).hexdigest()
