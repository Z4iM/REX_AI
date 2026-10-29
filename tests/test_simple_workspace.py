"""Original-file integrity and actual multi-record UI interactions."""
from io import BytesIO
from pathlib import Path
import requests
import pymupdf
from docx import Document
import pytest
from streamlit.testing.v1 import AppTest
from test_document_generation import generator, generate


def pdf_bytes():
    with pymupdf.open() as pdf:
        page=pdf.new_page()
        page.insert_text((45,80),'Unique original PDF source for staff review.')
        return pdf.tobytes()


@pytest.mark.parametrize('extension',['pdf','docx','md'])
def test_original_source_preserves_format_and_exact_bytes(catalog_client,staff_headers,extension):
    if extension=='pdf':
        raw=pdf_bytes()
    elif extension=='docx':
        doc=Document();doc.add_paragraph('Original Word course source');stream=BytesIO();doc.save(stream);raw=stream.getvalue()
    else:
        raw=b'# Original Markdown course source\nCourse information for review.'
    response=catalog_client.post('/api/v1/catalog/uploads',headers=staff_headers,files={'file':('course.'+extension,raw)})
    assert response.status_code==201,response.text
    record=response.json()
    assert record['file_type']==extension and record['uploaded_at']
    items=catalog_client.get('/api/v1/catalog/uploads',headers=staff_headers).json()['items']
    assert len(items)==1 and items[0]['filename']=='course.'+extension
    path='/api/v1/catalog/uploads/'+record['upload_id']+'/original'
    assert catalog_client.get(path).status_code==401
    download=catalog_client.get(path,headers=staff_headers)
    assert download.content==raw
    assert 'course.'+extension in download.headers['content-disposition']
    again=catalog_client.post('/api/v1/catalog/uploads',headers=staff_headers,files={'file':('renamed.'+extension,raw)}).json()
    assert again['already_uploaded'] and again['filename']=='course.'+extension
    assert len(catalog_client.get('/api/v1/catalog/uploads',headers=staff_headers).json()['items'])==1


def test_original_source_detects_integrity_change(catalog_client,staff_headers):
    from backend.app.catalog.upload_router import data_dir
    response=catalog_client.post('/api/v1/catalog/uploads',headers=staff_headers,files={'file':('source.pdf',pdf_bytes())}).json()
    (data_dir()/'uploads'/response['upload_id']/'source.pdf').write_bytes(b'changed')
    assert catalog_client.get('/api/v1/catalog/uploads/'+response['upload_id']+'/original',headers=staff_headers).status_code==409


def connect_ui(monkeypatch,client):
    def request(method,url,headers=None,timeout=None,**kwargs):
        result=client.request(method,url,headers=headers,**kwargs)
        response=requests.Response()
        response.status_code,response._content,response.url=result.status_code,result.content,url
        return response
    monkeypatch.setattr(requests,'request',request)


def app_page(staff_headers,page):
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'frontend/app.py'),default_timeout=30).run()
    app.session_state['staff_key']=staff_headers['X-API-Key']
    app.session_state['staff_name']='Usability Reviewer'
    app.switch_page('pages/'+page).run()
    assert not app.exception
    return app


def test_source_cards_open_correct_original_and_search(catalog_client,staff_headers,monkeypatch):
    connect_ui(monkeypatch,catalog_client)
    pdf=catalog_client.post('/api/v1/catalog/uploads',headers=staff_headers,files={'file':('z-original.pdf',pdf_bytes())}).json()
    catalog_client.post('/api/v1/catalog/uploads',headers=staff_headers,files={'file':('a-separate.md',b'Separate Markdown source, not a converted PDF.')})
    app=app_page(staff_headers,'4_Course_Approvals.py')
    next(b for b in app.button if b.label=='Open z-original.pdf').click().run()
    assert not app.exception
    assert app.session_state['review_upload']==pdf['upload_id']
    assert any('Unique original PDF' in t.value for t in app.text)
    assert not any('Separate Markdown source' in t.value for t in app.text)
    next(t for t in app.text_input if t.label=='Search source files').set_value('z-original').run()
    assert not app.exception
    assert not any('a-separate.md' in b.label for b in app.button)
    assert any(b.label=='Prepare original PDF download' for b in app.button)
    next(g for g in app.get('button_group') if g.label=='File format').select('PDF').run()
    assert not app.exception
    assert not any('a-separate.md' in b.label for b in app.button)


def test_document_history_versions_have_sources_and_keep_selection(catalog_client,staff_headers,published_course,generator,monkeypatch):
    connect_ui(monkeypatch,catalog_client)
    first=generate(catalog_client,staff_headers).json()
    second=generate(catalog_client,staff_headers,revision_of=first['artifact_id'],revision_instructions='Clarify the learning outcomes').json()
    metadata=catalog_client.get('/api/v1/documents',headers=staff_headers).json()['items']
    assert len(metadata)==2 and all(r['source_files']==['fixture.md'] for r in metadata)
    app=app_page(staff_headers,'5_Document_Generation.py')
    assert any(s.value=='Versions of this document' for s in app.subheader)
    assert not any(s.label=='Saved document' for s in app.selectbox)
    next(b for b in app.button if b.label=='Open version 1').click().run()
    assert not app.exception
    assert app.session_state['selected_document']==first['artifact_id']
    assert any(b.label=='Open version 2' for b in app.button)
    assert any('Draft created' in m.value for m in app.markdown)
    assert first['artifact_id']!=second['artifact_id']


def test_source_picker_pagination_and_empty_search(catalog_client,staff_headers,monkeypatch):
    connect_ui(monkeypatch,catalog_client)
    for i in range(8):
        catalog_client.post('/api/v1/catalog/uploads',headers=staff_headers,files={'file':(f'source-{i}.md',f'Course source number {i} for testing navigation.'.encode())})
    app=app_page(staff_headers,'4_Course_Approvals.py')
    next(b for b in app.button if b.label=='Next').click().run()
    assert not app.exception
    assert any('Page 2 of 2' in c.value for c in app.caption)
    assert any(b.label=='Open source-0.md' for b in app.button)
    assert not any(b.label=='Viewing source-7.md' for b in app.button)
    next(t for t in app.text_input if t.label=='Search source files').set_value('not-a-source').run()
    assert not app.exception
    assert any('No matching records' in v.value for v in app.info)


def test_human_history_time_uses_cairo():
    from frontend.components import date_label
    assert date_label('2026-10-29T08:00:00+00:00')=='29 Oct 2026 at 11:00 Cairo'
