"""Presentation for the learner catalog, using reviewed data only."""
from base64 import b64encode
from html import escape
import re

import requests
import streamlit as st

from frontend.ui import API

STYLE = """
<style>
.rex-course {background:#fff;color:#263238;border:1px solid #eee9e6;border-radius:17px;
  overflow:hidden;box-shadow:0 2px 7px #46342a18;}
.rex-course-cover {aspect-ratio:16/9;width:100%;display:block;object-fit:cover;
  background:linear-gradient(125deg,#f3ded6,#f6f0eb 56%,#bc8d80);}
.rex-course-cover-placeholder {display:grid;place-items:center;color:#855846;}
.rex-course-cover-placeholder .rex-course-icon {width:2.75rem;height:2.75rem;}
.rex-course-body {padding:1rem 1.05rem 1.05rem;}
.rex-course-mode {display:inline-block;border-radius:8px;background:#dfe4e5;color:#395860;
  padding:.42rem .9rem;font-weight:650;font-size:.87rem;margin-bottom:.55rem;}
.rex-course-title {font-size:1.16rem;line-height:1.35;font-weight:700;margin:0 0 .55rem;overflow-wrap:anywhere;}
.rex-course-location,.rex-course-meta {display:flex;align-items:center;gap:.45rem;border-radius:8px;
  margin:.45rem 0;padding:.45rem .6rem;font-size:.91rem;font-weight:650;}
.rex-course-location {background:#f5f0ed;}
.rex-course-meta {background:#f5f5f5;gap:1.1rem;flex-wrap:wrap;}
.rex-course-meta span {display:inline-flex;align-items:center;gap:.4rem;}
.rex-course-icon {width:1.15rem;height:1.15rem;flex:none;color:#99634f;}
.rex-course-outcomes {padding-inline-start:1.1rem;margin:.9rem 0 0;font-size:.91rem;}
.rex-course-outcomes li {padding:.12rem 0;overflow-wrap:anywhere;}
.rex-course-outcomes li::marker {color:#99634f;}
</style>
"""

ICONS = {
    "book": '<path d="M3 4h6a4 4 0 0 1 3 1.35A4 4 0 0 1 15 4h6v15h-6a3 3 0 0 0-3 1.5A3 3 0 0 0 9 19H3Zm2 2v11h4a5 5 0 0 1 2 .42V7.5A2 2 0 0 0 9 6Zm14 0h-4a2 2 0 0 0-2 1.5v9.92A5 5 0 0 1 15 17h4Z"/>',
    "pin": '<path d="M12 22s7-7.1 7-12a7 7 0 1 0-14 0c0 4.9 7 12 7 12Zm0-9a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z"/>',
    "level": '<rect x="3" y="12" width="4" height="9" rx="2"/><rect x="10" y="7" width="4" height="14" rx="2"/><rect x="17" y="3" width="4" height="18" rx="2"/>',
    "time": '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 2a8 8 0 1 1 0 16 8 8 0 0 1 0-16Zm-1 2v7l5 3 1-1.7-4-2.3V6Z"/>',
}


def icon(name):
    return '<svg class="rex-course-icon" aria-hidden="true" viewBox="0 0 24 24" fill="currentColor">' + ICONS[name] + '</svg>'


def cover_data(course):
    path = course.get("cover_path", "")
    if not re.fullmatch(r"/api/v1/catalog/courses/[A-Z0-9_.-]+/cover/[0-9a-f]{64}", path):
        return None
    try:
        response = requests.get(API + path, timeout=3, allow_redirects=False)
        if (response.status_code == 200 and response.headers.get("content-type", "").startswith("image/jpeg")
                and response.content.startswith(b"\xff\xd8") and len(response.content) <= 2 * 1024 * 1024):
            return b64encode(response.content).decode("ascii")
    except requests.RequestException:
        pass
    return None


def render_course_card(course):
    title = escape(course["title"])
    image = cover_data(course)
    hero = (f'<img class="rex-course-cover" src="data:image/jpeg;base64,{image}" alt="">'
            if image else f'<div class="rex-course-cover rex-course-cover-placeholder" aria-hidden="true">{icon("book")}</div>')
    mode = course.get("training_format")
    mode_html = f'<span class="rex-course-mode">{escape(mode)}</span>' if mode else ""
    location = course.get("location")
    location_html = f'<div class="rex-course-location">{icon("pin")}{escape(location)}</div>' if location else ""
    level, hours = course.get("level"), course.get("duration_hours")
    meta = []
    if level:
        meta.append(f'<span>{icon("level")}{escape(level)}</span>')
    if hours is not None:
        meta.append(f'<span>{icon("time")}{hours:g} {"hour" if hours == 1 else "hours"}</span>')
    meta_html = '<div class="rex-course-meta">' + "".join(meta) + '</div>' if meta else ""
    outcomes = course.get("learning_outcomes") or []
    preview = "".join(f'<li>{escape(text[:140])}{"…" if len(text) > 140 else ""}</li>' for text in outcomes[:2])
    preview_html = f'<ul class="rex-course-outcomes">{preview}</ul>' if preview else ""
    st.html(f'<article class="rex-course">{hero}<div class="rex-course-body">{mode_html}'
            f'<h3 class="rex-course-title">{title}</h3>{location_html}{meta_html}{preview_html}</div></article>')
