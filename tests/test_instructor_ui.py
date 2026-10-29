from pathlib import Path
import requests
from streamlit.testing.v1 import AppTest
from backend.app.instructor import service


def test_instructor_login_conversation_confirmation_and_cancel(catalog_client, staff_headers, monkeypatch):
    def request(method, url, headers, timeout, **kwargs):
        r = catalog_client.request(method, url, headers=headers, **kwargs)
        response = requests.Response()
        response.status_code, response._content, response.url = r.status_code, r.content, url
        return response
    monkeypatch.setattr(requests, 'request', request)
    monkeypatch.setattr(service, 'generate_json', lambda *args: {'reply':'Submit the saved teaching plan for review.',
        'calls':[{'tool':'submit_curriculum','path':{'curriculum_id':999}}]})
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'frontend/app.py'), default_timeout=30).run()
    app.switch_page('pages/10_Instructor.py').run()
    assert not app.exception
    assert any(x.value == 'Staff sign-in' for x in app.subheader)
    assert not app.chat_input
    app.session_state['staff_key'] = staff_headers['X-API-Key']
    app.session_state['staff_name'] = 'UI Instructor'
    app.run()
    next(b for b in app.button if b.label == 'New conversation').click().run()
    assert app.chat_input
    app.chat_input[0].set_value('Submit curriculum 999 for review').run()
    assert not app.exception
    assert any(b.label == 'Run proposed actions' for b in app.button)
    assert app.chat_input[0].disabled
    next(b for b in app.button if b.label == 'Cancel proposed actions').click().run()
    assert not app.exception
    assert not app.chat_input[0].disabled


def test_instructor_chat_executes_and_renders_results(catalog_client, staff_headers, monkeypatch, published_course):
    def request(method, url, headers, timeout, **kwargs):
        r = catalog_client.request(method, url, headers=headers, **kwargs)
        response = requests.Response()
        response.status_code, response._content, response.url = r.status_code, r.content, url
        return response
    monkeypatch.setattr(requests, 'request', request)
    monkeypatch.setattr(service, 'generate_json', lambda *args: {'reply':'Here are the published courses.', 'calls':[{'tool':'courses'}]})
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'frontend/app.py'), default_timeout=30).run()
    app.session_state['staff_key'] = staff_headers['X-API-Key']
    app.session_state['staff_name'] = 'UI Instructor'
    app.switch_page('pages/10_Instructor.py').run()
    next(b for b in app.button if b.label == 'New conversation').click().run()
    app.chat_input[0].set_value('List the published courses').run()
    assert not app.exception
    assert any('PY-101' in element.value for element in app.markdown)
