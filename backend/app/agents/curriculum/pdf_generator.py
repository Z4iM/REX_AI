"""Professional PDF curriculum generator using PyMuPDF (fitz).

Generates a polished, multi-page PDF document with:
- Cover page with metadata
- Table of contents
- Course overview and objectives
- Detailed module breakdowns
- Practical exercises
- Assessment plan
- Capstone project details
- Accreditation alignment report (if available)
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

# ---- Colour palette ----
NAVY = (0.071, 0.137, 0.278)          # #122347
DARK_BLUE = (0.086, 0.192, 0.380)     # #163161
ACCENT_BLUE = (0.180, 0.396, 0.718)   # #2E65B7
LIGHT_BLUE = (0.855, 0.906, 0.969)    # #DAE7F7
WHITE = (1, 1, 1)
BLACK = (0.1, 0.1, 0.1)
GRAY = (0.4, 0.4, 0.4)
LIGHT_GRAY = (0.92, 0.92, 0.92)
GREEN = (0.133, 0.545, 0.133)
ORANGE = (0.878, 0.557, 0.102)
RED = (0.8, 0.2, 0.2)


def _json_or_list(val) -> list:
    if val is None:
        return []
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return [val]
    return val if isinstance(val, list) else [val]


def _json_or_dict(val) -> dict:
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return val if isinstance(val, dict) else {}


class CurriculumPDFGenerator:
    """Builds a professional curriculum PDF document."""

    def __init__(self, curriculum: dict, alignment: dict | None = None):
        self.c = curriculum
        self.alignment = alignment
        self.doc = fitz.open()
        self.page_w = 595.28   # A4
        self.page_h = 841.89
        self.margin = 56
        self.y = self.margin
        self.page_num = 0
        self.current_page: fitz.Page | None = None

    # ---- layout helpers ----

    def _new_page(self) -> fitz.Page:
        page = self.doc.new_page(width=self.page_w, height=self.page_h)
        self.current_page = page
        self.y = self.margin
        self.page_num += 1
        # Footer
        footer_text = f"REX AI – Curriculum Document  |  Page {self.page_num}"
        page.insert_text(
            fitz.Point(self.margin, self.page_h - 24),
            footer_text,
            fontsize=8,
            color=GRAY,
        )
        # Footer line
        page.draw_line(
            fitz.Point(self.margin, self.page_h - 36),
            fitz.Point(self.page_w - self.margin, self.page_h - 36),
            color=LIGHT_GRAY,
            width=0.5,
        )
        return page

    def _ensure_space(self, needed: float = 80):
        if self.y + needed > self.page_h - 60:
            self._new_page()

    def _draw_text(self, text: str, fontsize: float = 10, color=BLACK,
                   bold: bool = False, indent: float = 0, max_width: float | None = None):
        self._ensure_space(fontsize + 6)
        font = "helv" if not bold else "hebo"
        x = self.margin + indent
        w = (max_width or (self.page_w - 2 * self.margin)) - indent
        # Word-wrap
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            tw = fitz.get_text_length(test, fontname=font, fontsize=fontsize)
            if tw > w and current:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        for line in lines:
            self._ensure_space(fontsize + 4)
            self.current_page.insert_text(
                fitz.Point(x, self.y + fontsize),
                line,
                fontname=font,
                fontsize=fontsize,
                color=color,
            )
            self.y += fontsize + 4
        self.y += 2

    def _draw_section_title(self, title: str, fontsize: float = 14):
        self._ensure_space(fontsize + 20)
        # Accent line
        self.current_page.draw_line(
            fitz.Point(self.margin, self.y),
            fitz.Point(self.margin + 4, self.y + fontsize + 4),
            color=ACCENT_BLUE,
            width=4,
        )
        self.current_page.insert_text(
            fitz.Point(self.margin + 12, self.y + fontsize),
            title,
            fontname="hebo",
            fontsize=fontsize,
            color=NAVY,
        )
        self.y += fontsize + 12

    def _draw_bullet(self, text: str, fontsize: float = 10, bullet: str = "•", indent: float = 16):
        self._draw_text(f"{bullet}  {text}", fontsize=fontsize, indent=indent)

    def _draw_divider(self):
        self._ensure_space(12)
        self.current_page.draw_line(
            fitz.Point(self.margin, self.y),
            fitz.Point(self.page_w - self.margin, self.y),
            color=LIGHT_GRAY,
            width=0.5,
        )
        self.y += 12

    def _draw_info_row(self, label: str, value: str):
        self._ensure_space(18)
        self.current_page.insert_text(
            fitz.Point(self.margin + 8, self.y + 10),
            f"{label}:",
            fontname="hebo",
            fontsize=9,
            color=DARK_BLUE,
        )
        self.current_page.insert_text(
            fitz.Point(self.margin + 160, self.y + 10),
            str(value),
            fontname="helv",
            fontsize=9,
            color=BLACK,
        )
        self.y += 16

    # ---- page builders ----

    def _build_cover(self):
        page = self._new_page()

        # Top accent bar
        page.draw_rect(
            fitz.Rect(0, 0, self.page_w, 6),
            color=ACCENT_BLUE,
            fill=ACCENT_BLUE,
        )

        # Header area
        page.draw_rect(
            fitz.Rect(0, 40, self.page_w, 260),
            color=NAVY,
            fill=NAVY,
        )

        # REX AI logo text
        page.insert_text(
            fitz.Point(self.margin, 90),
            "REX AI",
            fontname="hebo",
            fontsize=16,
            color=LIGHT_BLUE,
        )
        page.insert_text(
            fitz.Point(self.margin, 112),
            "Curriculum & Accreditation Agent",
            fontname="helv",
            fontsize=10,
            color=LIGHT_BLUE,
        )

        # Title
        title = self.c.get("title", "Curriculum Document")
        page.insert_text(
            fitz.Point(self.margin, 170),
            title[:80],
            fontname="hebo",
            fontsize=24,
            color=WHITE,
        )
        if len(title) > 80:
            page.insert_text(
                fitz.Point(self.margin, 200),
                title[80:160],
                fontname="hebo",
                fontsize=24,
                color=WHITE,
            )

        # Subtitle
        subtitle = self.c.get("description", "")[:120]
        page.insert_text(
            fitz.Point(self.margin, 238),
            subtitle,
            fontname="helv",
            fontsize=11,
            color=LIGHT_BLUE,
        )

        # Metadata section
        self.y = 300
        self.current_page = page
        meta_fields = [
            ("Department", self.c.get("department", "—")),
            ("Target Audience", self.c.get("target_audience", "—")),
            ("Skill Level", self.c.get("skill_level", "—")),
            ("Industry", self.c.get("industry", "—")),
            ("Country", self.c.get("country", "—")),
            ("Language", self.c.get("language", "English")),
            ("Training Hours", str(self.c.get("training_hours", "—"))),
            ("Accreditation Framework", self.c.get("accreditation_framework", "None selected")),
        ]

        self._draw_section_title("Course Overview", fontsize=13)
        for label, value in meta_fields:
            self._draw_info_row(label, value)

        # Generated date
        self.y += 12
        self._draw_divider()
        self._draw_text(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            fontsize=8,
            color=GRAY,
        )

        # Disclaimer box
        self.y += 8
        box_top = self.y
        disclaimer = (
            "DISCLAIMER: This curriculum document was generated by REX AI for review purposes. "
            "Any accreditation alignment analysis is a proposal only. Official accreditation requires "
            "formal review and approval by the relevant accrediting body."
        )
        page.draw_rect(
            fitz.Rect(self.margin, box_top, self.page_w - self.margin, box_top + 50),
            color=ORANGE,
            fill=(1, 0.96, 0.90),
        )
        page.draw_rect(
            fitz.Rect(self.margin, box_top, self.margin + 4, box_top + 50),
            color=ORANGE,
            fill=ORANGE,
        )
        page.insert_textbox(
            fitz.Rect(self.margin + 12, box_top + 6, self.page_w - self.margin - 8, box_top + 46),
            disclaimer,
            fontname="helv",
            fontsize=7.5,
            color=GRAY,
        )
        self.y = box_top + 60

    def _build_objectives(self):
        self._new_page()
        self._draw_section_title("Course Objectives")
        for obj in _json_or_list(self.c.get("objectives")):
            self._draw_bullet(str(obj))

        self.y += 10
        self._draw_section_title("Prerequisites")
        prereqs = _json_or_list(self.c.get("prerequisites"))
        if prereqs:
            for p in prereqs:
                self._draw_bullet(str(p))
        else:
            self._draw_text("No specific prerequisites required.", fontsize=10, indent=16, color=GRAY)

        self.y += 10
        self._draw_section_title("Learning Outcomes")
        self._draw_text(
            "Upon successful completion, learners will be able to:",
            fontsize=10,
            color=GRAY,
            indent=4,
        )
        self.y += 4
        for i, lo in enumerate(_json_or_list(self.c.get("learning_outcomes")), 1):
            self._draw_bullet(f"LO{i}: {lo}", indent=16)

    def _build_modules(self):
        self._new_page()
        self._draw_section_title("Modules & Topics")
        modules = _json_or_list(self.c.get("modules"))
        for mod in modules:
            if isinstance(mod, dict):
                num = mod.get("module_number", "")
                title = mod.get("title", "Untitled Module")
                desc = mod.get("description", "")
                hours = mod.get("duration_hours", "")
                topics = mod.get("topics", [])
                outcomes = mod.get("learning_outcomes", [])
                activities = mod.get("activities", [])

                self._ensure_space(100)
                # Module header bar
                bar_top = self.y
                self.current_page.draw_rect(
                    fitz.Rect(self.margin, bar_top, self.page_w - self.margin, bar_top + 22),
                    color=DARK_BLUE,
                    fill=DARK_BLUE,
                )
                self.current_page.insert_text(
                    fitz.Point(self.margin + 8, bar_top + 15),
                    f"Module {num}: {title}",
                    fontname="hebo",
                    fontsize=10,
                    color=WHITE,
                )
                if hours:
                    hrs_text = f"{hours}h"
                    self.current_page.insert_text(
                        fitz.Point(self.page_w - self.margin - 40, bar_top + 15),
                        hrs_text,
                        fontname="hebo",
                        fontsize=9,
                        color=LIGHT_BLUE,
                    )
                self.y = bar_top + 28

                if desc:
                    self._draw_text(desc, fontsize=9, color=GRAY, indent=8)

                if topics:
                    self._draw_text("Topics:", fontsize=9, bold=True, indent=8, color=DARK_BLUE)
                    for t in topics:
                        self._draw_bullet(str(t), fontsize=9, indent=24, bullet="▸")

                if outcomes:
                    self._draw_text("Learning Outcomes:", fontsize=9, bold=True, indent=8, color=DARK_BLUE)
                    for o in outcomes:
                        self._draw_bullet(str(o), fontsize=9, indent=24, bullet="✓")

                if activities:
                    self._draw_text("Activities:", fontsize=9, bold=True, indent=8, color=DARK_BLUE)
                    for a in activities:
                        self._draw_bullet(str(a), fontsize=9, indent=24, bullet="◆")

                self.y += 8
            else:
                self._draw_bullet(str(mod))

    def _build_exercises(self):
        self._new_page()
        self._draw_section_title("Practical Exercises")
        exercises = _json_or_list(self.c.get("practical_exercises"))
        for ex in exercises:
            if isinstance(ex, dict):
                self._ensure_space(60)
                title = ex.get("title", "Exercise")
                etype = ex.get("type", "")
                desc = ex.get("description", "")
                module = ex.get("module", "")
                hours = ex.get("duration_hours", "")

                self._draw_text(f"▶  {title}", fontsize=10, bold=True, indent=8, color=DARK_BLUE)
                detail_parts = []
                if etype:
                    detail_parts.append(f"Type: {etype}")
                if module:
                    detail_parts.append(f"Module: {module}")
                if hours:
                    detail_parts.append(f"Duration: {hours}h")
                if detail_parts:
                    self._draw_text("  |  ".join(detail_parts), fontsize=8, indent=24, color=GRAY)
                if desc:
                    self._draw_text(desc, fontsize=9, indent=24)
                self.y += 4
            else:
                self._draw_bullet(str(ex))

    def _build_assessments(self):
        self._draw_section_title("Assessment Plan")
        assessments = _json_or_list(self.c.get("assessments"))

        # Table header
        self._ensure_space(40)
        bar_top = self.y
        self.current_page.draw_rect(
            fitz.Rect(self.margin, bar_top, self.page_w - self.margin, bar_top + 18),
            color=NAVY,
            fill=NAVY,
        )
        cols = [
            (self.margin + 4, "Assessment"),
            (self.margin + 200, "Type"),
            (self.margin + 310, "Weight"),
            (self.margin + 380, "Module"),
        ]
        for x, label in cols:
            self.current_page.insert_text(
                fitz.Point(x, bar_top + 13),
                label,
                fontname="hebo",
                fontsize=8,
                color=WHITE,
            )
        self.y = bar_top + 22

        for i, a in enumerate(assessments):
            if isinstance(a, dict):
                self._ensure_space(20)
                bg = LIGHT_GRAY if i % 2 == 0 else WHITE
                self.current_page.draw_rect(
                    fitz.Rect(self.margin, self.y, self.page_w - self.margin, self.y + 16),
                    color=bg,
                    fill=bg,
                )
                entries = [
                    (self.margin + 4, str(a.get("title", ""))[:35]),
                    (self.margin + 200, str(a.get("type", ""))),
                    (self.margin + 310, f"{a.get('weight_percent', '')}%"),
                    (self.margin + 380, str(a.get("module", ""))[:20]),
                ]
                for x, txt in entries:
                    self.current_page.insert_text(
                        fitz.Point(x, self.y + 12),
                        txt,
                        fontname="helv",
                        fontsize=8,
                        color=BLACK,
                    )
                self.y += 18

    def _build_capstone(self):
        self.y += 10
        self._draw_section_title("Capstone Project")
        capstone = _json_or_dict(self.c.get("capstone_project"))
        if not capstone:
            self._draw_text("No capstone project defined.", fontsize=10, color=GRAY, indent=8)
            return

        self._draw_text(capstone.get("title", "Capstone Project"), fontsize=12, bold=True, indent=8, color=DARK_BLUE)
        if capstone.get("description"):
            self._draw_text(capstone["description"], fontsize=9, indent=8)
        if capstone.get("duration_hours"):
            self._draw_text(f"Duration: {capstone['duration_hours']} hours", fontsize=9, indent=8, color=GRAY)

        if capstone.get("deliverables"):
            self.y += 4
            self._draw_text("Deliverables:", fontsize=9, bold=True, indent=8, color=DARK_BLUE)
            for d in capstone["deliverables"]:
                self._draw_bullet(str(d), fontsize=9, indent=24, bullet="📋")

        if capstone.get("evaluation_criteria"):
            self.y += 4
            self._draw_text("Evaluation Criteria:", fontsize=9, bold=True, indent=8, color=DARK_BLUE)
            for ec in capstone["evaluation_criteria"]:
                self._draw_bullet(str(ec), fontsize=9, indent=24, bullet="✓")

    def _build_alignment_report(self):
        if not self.alignment:
            return
        self._new_page()
        self._draw_section_title("Accreditation Alignment Report")

        # Disclaimer box first
        box_top = self.y
        disclaimer = self.alignment.get(
            "disclaimer",
            "This is an automated alignment analysis. Official accreditation requires formal review by the accrediting body.",
        )
        self.current_page.draw_rect(
            fitz.Rect(self.margin, box_top, self.page_w - self.margin, box_top + 34),
            color=ORANGE,
            fill=(1, 0.96, 0.90),
        )
        self.current_page.draw_rect(
            fitz.Rect(self.margin, box_top, self.margin + 4, box_top + 34),
            color=ORANGE,
            fill=ORANGE,
        )
        self.current_page.insert_textbox(
            fitz.Rect(self.margin + 12, box_top + 6, self.page_w - self.margin - 8, box_top + 30),
            f"⚠ {disclaimer}",
            fontname="helv",
            fontsize=7.5,
            color=GRAY,
        )
        self.y = box_top + 42

        fw_name = self.alignment.get("framework_name", "Unknown")
        score = self.alignment.get("overall_alignment_score", 0)
        level = self.alignment.get("alignment_level", "Unknown")

        self._draw_info_row("Framework", fw_name)
        self._draw_info_row("Alignment Level", level)

        # Score bar
        self._ensure_space(40)
        bar_x = self.margin + 160
        bar_w = 200
        bar_h = 14
        bar_y = self.y

        # Background
        self.current_page.draw_rect(
            fitz.Rect(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
            color=LIGHT_GRAY,
            fill=LIGHT_GRAY,
        )
        # Fill
        fill_color = GREEN if score >= 70 else (ORANGE if score >= 40 else RED)
        fill_w = bar_w * (score / 100)
        self.current_page.draw_rect(
            fitz.Rect(bar_x, bar_y, bar_x + fill_w, bar_y + bar_h),
            color=fill_color,
            fill=fill_color,
        )
        self.current_page.insert_text(
            fitz.Point(bar_x + bar_w + 8, bar_y + 11),
            f"{score}%",
            fontname="hebo",
            fontsize=10,
            color=fill_color,
        )
        self.current_page.insert_text(
            fitz.Point(self.margin + 8, bar_y + 11),
            "Alignment Score:",
            fontname="hebo",
            fontsize=9,
            color=DARK_BLUE,
        )
        self.y = bar_y + 24

        # Summary
        if self.alignment.get("summary"):
            self._draw_text(self.alignment["summary"], fontsize=9, indent=8)

        # Competency details
        competencies = _json_or_list(self.alignment.get("competency_alignment"))
        if competencies:
            self.y += 8
            self._draw_text("Competency-Level Analysis:", fontsize=10, bold=True, color=DARK_BLUE)
            for comp in competencies:
                if isinstance(comp, dict):
                    status = comp.get("status", "unknown")
                    icon = {"fully_aligned": "✅", "partially_aligned": "⚠️", "not_addressed": "❌"}.get(status, "•")
                    color = {"fully_aligned": GREEN, "partially_aligned": ORANGE, "not_addressed": RED}.get(status, BLACK)
                    self._draw_text(
                        f"{icon}  {comp.get('competency', 'Unknown')} — {status.replace('_', ' ').title()}",
                        fontsize=9,
                        bold=True,
                        indent=8,
                        color=color,
                    )
                    if comp.get("curriculum_coverage"):
                        self._draw_text(f"Coverage: {comp['curriculum_coverage']}", fontsize=8, indent=28, color=GRAY)
                    if comp.get("gaps"):
                        self._draw_text(f"Gap: {comp['gaps']}", fontsize=8, indent=28, color=RED)
                    if comp.get("recommendation"):
                        self._draw_text(f"Recommendation: {comp['recommendation']}", fontsize=8, indent=28, color=DARK_BLUE)
                    self.y += 2

        # Missing topics
        missing = _json_or_list(self.alignment.get("missing_topics"))
        if missing:
            self.y += 6
            self._draw_text("Missing Topics:", fontsize=10, bold=True, color=RED)
            for m in missing:
                self._draw_bullet(str(m), fontsize=9, indent=16, bullet="✗")

        # Strengths
        strengths = _json_or_list(self.alignment.get("strengths"))
        if strengths:
            self.y += 6
            self._draw_text("Strengths:", fontsize=10, bold=True, color=GREEN)
            for s in strengths:
                self._draw_bullet(str(s), fontsize=9, indent=16, bullet="★")

        # Recommendations
        recs = _json_or_list(self.alignment.get("recommendations"))
        if recs:
            self.y += 6
            self._draw_text("Recommendations:", fontsize=10, bold=True, color=DARK_BLUE)
            for i, r in enumerate(recs, 1):
                self._draw_bullet(f"{i}. {r}", fontsize=9, indent=16, bullet="→")

    # ---- public API ----

    def generate(self) -> bytes:
        """Build all pages and return the PDF as bytes."""
        self._build_cover()
        self._build_objectives()
        self._build_modules()
        self._build_exercises()
        self._build_assessments()
        self._build_capstone()
        self._build_alignment_report()
        pdf_bytes = self.doc.tobytes()
        self.doc.close()
        return pdf_bytes


def generate_curriculum_pdf(curriculum: dict, alignment: dict | None = None) -> bytes:
    """Convenience wrapper: returns PDF bytes for a curriculum dict."""
    gen = CurriculumPDFGenerator(curriculum, alignment)
    return gen.generate()


def save_curriculum_pdf(curriculum: dict, alignment: dict | None = None,
                        output_dir: str | Path | None = None) -> Path:
    """Generate and save a curriculum PDF to disk. Returns the file path."""
    from .db import DATA_DIR
    dest = Path(output_dir) if output_dir else DATA_DIR / "exports"
    dest.mkdir(parents=True, exist_ok=True)
    title_slug = (curriculum.get("title", "curriculum") or "curriculum")
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in title_slug)[:60].strip()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{ts}.pdf"
    path = dest / filename
    path.write_bytes(generate_curriculum_pdf(curriculum, alignment))
    return path
