"""Versioned layouts; an authenticated reviewer must approve their current hash."""
import hashlib
import json

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


def template_hash(kind):
    return hashlib.sha256(json.dumps(TEMPLATES[kind], sort_keys=True).encode()).hexdigest()
