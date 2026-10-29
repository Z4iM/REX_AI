"""Source-cited document composition using the shared Andalusia Academy theme."""
import re
from pathlib import Path
from .brand import render_pdf, render_word
from .templates import TEMPLATES

AR_NAMES = {
    "course_description": "وصف الدورة", "course_proposal": "المقترح التدريبي", "participant_guide": "دليل المشارك",
    "curriculum": "المنهج التدريبي", "facilitator_guide": "دليل المدرب", "presentation_outline": "مخطط العرض التدريبي",
    "question_bank": "بنك الأسئلة", "assessment_rubrics": "معايير تقييم الأداء", "capstone_brief": "موجز المشروع التطبيقي",
    "assessment_plan": "خطة مخرجات التعلم والتقييم",
}


def _paragraphs(text):
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        lines = paragraph.splitlines()
        if lines and all(re.match(r"^\s*[-*•]\s+", line) for line in lines):
            yield {"kind": "bullets", "items": [re.sub(r"^\s*[-*•]\s+", "", line) for line in lines]}
        else:
            yield {"kind": "paragraph", "text": paragraph}


def document_blocks(record):
    ar = record["language"] == "ar"
    blocks = [{"kind": "callout", "text": ("الجمهور المستهدف: " if ar else "Prepared for: ") + record["audience"]}]
    if record.get("approved_by"):
        blocks.append({"kind": "reference", "text": f'{record["approved_by"]} | {record["approved_at"]}'})
    sources = record["sources"]
    labels = {"level": ("Level", "المستوى"), "training_format": ("Delivery", "نظام التدريب"),
              "price_egp": ("Fee (EGP)", "الرسوم بالجنيه المصري"), "duration_hours": ("Training hours", "ساعات التدريب")}
    if len(sources) == 1:
        course = sources[0]["course"]
        rows = [(pair[1 if ar else 0], str(course[key])) for key, pair in labels.items() if course.get(key) is not None]
        if rows:
            blocks.append({"kind": "facts", "rows": rows})
    for i, section in enumerate(record["content"]["sections"], 1):
        blocks.append({"kind": "section", "text": f'{i:02d}  {section["heading"]}'})
        blocks.extend(_paragraphs(section["text"]))
        blocks.append({"kind": "reference", "text": ("المراجع: " if ar else "Sources: ") + "  ".join(f"[{sid}]" for sid in section["source_ids"])})
    blocks.append({"kind": "appendix", "text": "المراجع وبيانات الدورات المعتمدة" if ar else "Source references and verified course details"})
    blocks.append({"kind": "paragraph", "text": "تتيح البيانات التالية مراجعة محتوى المستند مقابل المصادر التي اعتمدها موظفو الأكاديمية." if ar else
                   "The following records connect this document to the course information verified by academy staff."})
    full_labels = {"description": ("Description", "الوصف"), "department": ("Department", "القسم"),
                   "prerequisites": ("Prerequisites", "المتطلبات السابقة"), "learning_outcomes": ("Learning outcomes", "مخرجات التعلم")}
    for source in sources:
        c = source["course"]
        blocks.append({"kind": "subheading", "text": f'[{source["source_id"]}] {c["title"]}'})
        blocks.append({"kind": "reference", "text": f'{source["source_id"]} | {c["course_id"]} | {source["source_file"]}'})
        rows = [(pair[1 if ar else 0], str(c[key])) for key, pair in labels.items() if c.get(key) is not None]
        if len(sources) > 1 and rows:
            blocks.append({"kind": "facts", "rows": rows})
        for field, pair in full_labels.items():
            value = c.get(field)
            if not value:
                value = "غير محدد في البيانات المعتمدة" if ar else "Not specified in approved data"
            blocks.append({"kind": "reference", "text": pair[1 if ar else 0]})
            blocks.append({"kind": "bullets", "items": value} if isinstance(value, list) else {"kind": "paragraph", "text": str(value)})
        blocks.append({"kind": "reference", "text": "SHA256 " + c["source_sha256"]})
        if c.get("reviewed_at"):
            blocks.append({"kind": "reference", "text": ("تاريخ التحقق: " if ar else "Source reviewed: ") + c["reviewed_at"]})
    if record.get("curriculum"):
        c = record["curriculum"]
        blocks.append({"kind": "subheading", "text": "مرجع المنهج المعتمد" if ar else "Approved curriculum reference"})
        blocks.append({"kind": "reference", "text": f"Curriculum #{c['id']} | {c['title']} | {c['reviewer_name']}"})
    blocks.append({"kind": "reference", "text": "Artifact " + record["artifact_id"]})
    return blocks


def render_document(record, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    ar = record["language"] == "ar"
    document_type = record["document_type"]
    options = {"title": record["content"]["title"], "kind": AR_NAMES.get(document_type, document_type) if ar else TEMPLATES[document_type]["name"],
               "status": record["status"], "version": record["version"],
               "demo": record.get("data_origin") == "synthetic_demo", "ar": ar}
    options["cover_overview"] = record["content"]["sections"][0]["text"].split("\n\n")[0]
    sources = record["sources"]
    summary = [("الدورات" if ar else "COURSES", str(len(sources)))]
    if all(s["course"].get("duration_hours") is not None for s in sources):
        hours = sum(s["course"]["duration_hours"] for s in sources)
        summary.append(("ساعة تدريبية" if ar else "TRAINING HOURS", f"{hours:g}"))
    summary.append(("اللغة" if ar else "LANGUAGE", "العربية" if ar else "English"))
    options["summary"] = summary
    blocks = document_blocks(record)
    render_word(blocks, **options).save(directory / "document.docx")
    (directory / "document.pdf").write_bytes(render_pdf(blocks, **options))
