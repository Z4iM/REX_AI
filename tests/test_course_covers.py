"""Course art runs after publication and never bypasses catalog visibility."""
from io import BytesIO

from PIL import Image

from backend.app.catalog import course_covers
from test_catalog_approval_publication import valid_approval


def approve(client, headers, filename="course.md"):
    upload = client.post("/api/v1/catalog/uploads", headers=headers,
                         files={"file": (filename, b"Python practice for new programmers.")})
    assert upload.status_code == 201
    approval = client.post(f'/api/v1/catalog/uploads/{upload.json()["upload_id"]}/approve',
                           headers=headers, json=valid_approval(location="Alexandria", learning_outcomes=["Practice basic Python", "Read code examples"]).model_dump(mode="json"))
    assert approval.status_code == 200, approval.text


def test_publish_generates_one_cover_and_withdraw_hides_it(catalog_client, staff_headers, monkeypatch):
    monkeypatch.setenv("REX_RETRIEVAL_BACKEND", "sqlite")
    monkeypatch.setenv("PUTER_AUTH_TOKEN", "test-token")
    buffer = BytesIO()
    Image.new("RGB", (96, 54), "#93604c").save(buffer, "PNG")
    calls = []

    def generate(course, token):
        assert course["status"] == "published"
        calls.append(course["course_id"])
        return buffer.getvalue()

    monkeypatch.setattr(course_covers, "_generate", generate)
    approve(catalog_client, staff_headers)
    assert not calls
    root = "/api/v1/catalog"
    assert catalog_client.get(root + "/courses/PY-101").status_code == 404
    publish = catalog_client.post(root + "/staff/courses/PY-101/publish", headers=staff_headers)
    assert publish.status_code == 200, publish.text
    cover = catalog_client.get(root + "/courses/PY-101").json()["cover_path"]
    assert catalog_client.get(root + "/courses").json()["items"][0]["cover_path"] == cover
    response = catalog_client.get(cover)
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(response.content)) as rendered:
        assert rendered.size == (960, 540)
    course_covers.generate_cover("PY-101")
    assert calls == ["PY-101"]
    withdrawal = catalog_client.post(root + "/staff/courses/PY-101/withdraw",
                                     headers=staff_headers, json={"reviewer": "Test Reviewer"})
    assert withdrawal.status_code == 200
    assert catalog_client.get(cover).status_code == 404


def test_invalid_provider_image_does_not_undo_publication(catalog_client, staff_headers, monkeypatch):
    monkeypatch.setenv("REX_RETRIEVAL_BACKEND", "sqlite")
    monkeypatch.setenv("PUTER_AUTH_TOKEN", "test-token")
    calls = []
    def invalid_image(*args):
        calls.append(True)
        return b"not an image"
    monkeypatch.setattr(course_covers, "_generate", invalid_image)
    approve(catalog_client, staff_headers)
    response = catalog_client.post("/api/v1/catalog/staff/courses/PY-101/publish", headers=staff_headers)
    assert response.status_code == 200
    course = catalog_client.get("/api/v1/catalog/courses/PY-101").json()
    assert course["status"] == "published" and "cover_path" not in course
    course_covers.generate_cover("PY-101")
    assert calls == [True]


def test_simultaneous_cover_workers_send_one_request(published_course, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    monkeypatch.setenv("PUTER_AUTH_TOKEN", "test-token")
    entered, release = Event(), Event()
    calls = []

    def generate(*args):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        buffer = BytesIO()
        Image.new("RGB", (32, 18)).save(buffer, "PNG")
        return buffer.getvalue()

    monkeypatch.setattr(course_covers, "_generate", generate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(course_covers.generate_cover, "PY-101")
        try:
            assert entered.wait(5)
            pool.submit(course_covers.generate_cover, "PY-101").result(3)
        finally:
            release.set()
        first.result(5)
    assert calls == [True]
    assert course_covers.image_path(published_course[0]).is_file()


def test_course_library_shows_reference_card_with_saved_cover(catalog_client, staff_headers, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    import requests
    from test_simple_workspace import connect_ui

    monkeypatch.setenv("REX_RETRIEVAL_BACKEND", "sqlite")
    monkeypatch.setenv("PUTER_AUTH_TOKEN", "test-token")
    image = BytesIO()
    Image.new("RGB", (96, 54), "#93604c").save(image, "PNG")
    monkeypatch.setattr(course_covers, "_generate", lambda *_: image.getvalue())
    approve(catalog_client, staff_headers)
    assert catalog_client.post("/api/v1/catalog/staff/courses/PY-101/publish", headers=staff_headers).status_code == 200
    connect_ui(monkeypatch, catalog_client)
    # Include response headers for the card's JPEG check.
    def image_get(url, **kwargs):
        raw = catalog_client.get(url)
        response = requests.Response()
        response.status_code = raw.status_code
        response.headers.update(raw.headers)
        response._content = raw.content
        return response
    monkeypatch.setattr(requests, "get", image_get)

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "frontend/app.py"), default_timeout=25).run()
    # AppTest switches scripts without the custom navigation entrypoint.
    import streamlit as st
    monkeypatch.setattr(st, "page_link", lambda *args, **kwargs: None)
    app.switch_page("pages/1_Course_Catalog.py").run()
    assert not app.exception
    card = next(x.proto.body for x in app.get("html") if '<article class="rex-course">' in x.proto.body)
    assert 'data:image/jpeg;base64,' in card
    assert "Alexandria" in card and "Practice basic Python" in card
    assert "rex-course-meta" in card and "rex-course-mode" in card
