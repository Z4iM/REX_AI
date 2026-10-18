
import json

from backend.app.ingestion.markdown_loader import load_markdown


FIELD_ALIASES = {
    "course_id": ["course_id", "program_code"],
    "department": ["department", "category"],
    "level": ["level", "difficulty"],
    "duration": ["duration", "training_hours"],
    "training_format": ["training_format", "delivery_method"],
    "price": ["price"],
    "language": ["language"],
}


def get_field(metadata, aliases):
    for alias in aliases:
        value = metadata.get(alias)

        if value is not None:
            return value

    return None


def normalize_document(document):
    normalized = []

    for section in document["sections"]:
        original = section["metadata"]

        course = {
            "title": section["title"],
            "source_file": document["source_file"],
            "approval_status": "unapproved",
            "dataset_status": document["approval_status"],
            "content": section["content"],
            "metadata": original.copy(),
        }

        for field, aliases in FIELD_ALIASES.items():
            course[field] = get_field(original, aliases)

        normalized.append(course)

    return normalized


if __name__ == "__main__":
    files = [
        "data/samples/course_catalog.md",
        "data/samples/alternative_catalog.md",
    ]

    all_courses = []

    for file in files:
        document = load_markdown(file)
        courses = normalize_document(document)
        all_courses.extend(courses)

    print("Total courses:", len(all_courses))

    for course in all_courses:
        print(json.dumps({
            "title": course["title"],
            "course_id": course["course_id"],
            "department": course["department"],
            "level": course["level"],
            "price": course["price"],
            "approval_status": course["approval_status"],
        }, ensure_ascii=False, indent=2))

    assert len(all_courses) == 5
    assert all(c["approval_status"] == "unapproved"
               for c in all_courses)
    assert all_courses[3]["course_id"] == "AR-101"
    assert all_courses[4]["course_id"] == "CL-202"
    assert all_courses[4]["price"] is None

    print("\nAll normalization checks passed!")
