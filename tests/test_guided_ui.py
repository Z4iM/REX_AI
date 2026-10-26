from pathlib import Path
import requests
from streamlit.testing.v1 import AppTest


def element(elements,label): return next(e for e in elements if e.label==label)


def test_demo_ui_single_sign_in_navigation_and_workflow(catalog_client,staff_headers,monkeypatch,tmp_path):
    monkeypatch.setenv('REX_APP_MODE','demo')
    monkeypatch.setenv('REX_DEMO_DATA_DIR',str(tmp_path/'demo'))
    def request(method,url,headers,timeout,**kwargs):
        result=catalog_client.request(method,url,headers=headers,**kwargs)
        response=requests.Response()
        response.status_code,response._content,response.url=result.status_code,result.content,url
        return response
    monkeypatch.setattr(requests,'request',request)
    ui=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'frontend/app.py'),default_timeout=20).run()
    assert not ui.exception
    ui.switch_page('pages/7_Demo_Setup.py').run()
    element(ui.text_input,'Your name').set_value('TA Reviewer')
    element(ui.text_input,'Staff access key').set_value('wrong')
    element(ui.button,'Sign in').click().run()
    assert ui.error and 'staff_key' not in ui.session_state
    element(ui.text_input,'Staff access key').set_value(staff_headers['X-API-Key'])
    element(ui.button,'Sign in').click().run()
    assert not ui.exception
    element(ui.button,'Load course examples').click().run()
    assert not ui.exception
    assert any('No courses were approved' in e.value for e in ui.success)
    element(ui.button,'Load tender examples').click().run()
    assert not ui.exception
    ui.switch_page('pages/4_Course_Approvals.py').run()
    assert not ui.exception
    assert not any(e.label=='Staff access key' for e in ui.text_input)
    uploads=catalog_client.get('/api/v1/catalog/uploads',headers=staff_headers).json()['items']
    primary=next(item['upload_id'] for item in uploads if item['filename']=='demo-py-101.md')
    element(ui.selectbox,'Uploaded document').set_value(primary).run()
    assert element(ui.text_input,'Course ID (unique)').value=='DEMO-PY-101'
    element(ui.checkbox,'I verified these course details against the source document').check()
    element(ui.checkbox,'I checked every extraction warning against the original document').check()
    element(ui.button,'Save verified course').click().run()
    assert not ui.exception
    # Publication remains a separate human action with a live embedding call.
    assert any(e.label=='Publish course' for e in ui.button)
    ui.switch_page('pages/2_RFP_Research.py').run()
    assert not ui.exception
    assert len(ui.selectbox)>1
    element(ui.button,'Save opportunity review').click().run()
    assert not ui.exception
    assert any('Opportunity review saved' in e.value for e in ui.success)
    ui.switch_page('pages/5_Document_Generation.py').run()
    assert not ui.exception
    assert element(ui.button,'Generate document draft').disabled
    element(ui.button,'Sign out').click().run()
    assert 'staff_key' not in ui.session_state
