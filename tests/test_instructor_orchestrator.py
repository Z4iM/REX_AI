"""Real internal agent calls with temporary storage and an offline planner."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from backend.app.instructor import service, store, tools
from test_connected_workflows import approved_plan, campaign_generator, campaign_body
from test_document_generation import generator

BASE = '/api/v1/instructor/sessions'


@pytest.fixture
def instructor(catalog_client, staff_headers):
    headers = {**staff_headers, 'X-REX-Reviewer': 'Instructor Reviewer'}
    result = catalog_client.post(BASE, headers=headers)
    assert result.status_code == 201
    return headers, result.json()['id']


def plan(monkeypatch, calls, reply='Here are the proposed actions.'):
    monkeypatch.setattr(service, 'generate_json', lambda *args: {'reply': reply, 'calls': calls})


def send(client, instructor, message='Create a campaign', request_id=None):
    headers, sid = instructor
    result = client.post(f'{BASE}/{sid}/messages', headers=headers,
                         json={'message': message, 'request_id': request_id or str(uuid4())})
    assert result.status_code == 200, result.text
    return result.json()


def execute(client, instructor, run, reviewed=False):
    headers, sid = instructor
    return client.post(f'{BASE}/{sid}/runs/{run["id"]}/execute', headers=headers,
                       json={'confirmed': True, 'reviewed': reviewed})


def test_authentication_identity_and_session_scope(catalog_client, staff_headers, instructor):
    assert catalog_client.get(BASE).status_code == 401
    assert catalog_client.get(BASE, headers=staff_headers).status_code == 422
    headers, sid = instructor
    foreign = {**headers, 'X-REX-Reviewer': 'Different Instructor'}
    assert catalog_client.get(f'{BASE}/{sid}', headers=foreign).status_code == 404
    assert catalog_client.get(BASE, headers=foreign).json()['items'] == []
    assert catalog_client.get(BASE, headers=headers).json()['items'][0]['id'] == sid


def test_clarification_and_history_are_persistent(catalog_client, instructor, monkeypatch):
    observed = []
    def planner(system, payload):
        observed.append(payload)
        return {'reply': 'Which audience and channels should the campaign use?', 'calls': []}
    monkeypatch.setattr(service, 'generate_json', planner)
    first = send(catalog_client, instructor)
    assert first['state'] == 'completed' and first['results'] == []
    second = send(catalog_client, instructor, 'Beginners on LinkedIn')
    assert second['state'] == 'completed'
    assert first['message'] in observed[-1]['history']
    assert 'X-API-Key' not in str(observed)
    assert len(store.get(instructor[1], instructor[0]['X-REX-Reviewer'])['runs']) == 2


def test_read_tools_run_without_confirmation(catalog_client, instructor, monkeypatch, published_course):
    plan(monkeypatch, [{'tool': 'courses'}])
    run = send(catalog_client, instructor, 'List published courses')
    assert run['state'] == 'completed'
    assert run['results'][0]['result']['items'][0]['course_id'] == 'PY-101'
    assert run['confirmed_by'] is None


def test_campaign_generation_confirmation_and_duplicate_protection(catalog_client, instructor, monkeypatch, approved_plan, campaign_generator):
    from backend.app.marketing import service as marketing
    body = campaign_body(approved_plan)
    body['requester'] = 'Forged name'
    plan(monkeypatch, [{'tool': 'generate_campaign', 'body': body}])
    request_id = str(uuid4())
    run = send(catalog_client, instructor, request_id=request_id)
    assert run['state'] == 'pending'
    assert marketing.list_campaigns() == []
    assert run['plan']['calls'][0]['body']['requester'] == 'Instructor Reviewer'
    assert send(catalog_client, instructor, request_id=request_id)['id'] == run['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(catalog_client, instructor, run), range(2)))
    assert all(r.status_code in (200,409) for r in results)
    assert any(r.status_code == 200 and r.json()['state'] == 'completed' for r in results)
    assert len(marketing.list_campaigns()) == 1
    assert execute(catalog_client, instructor, run).json()['state'] == 'completed'
    assert len(marketing.list_campaigns()) == 1


def test_missing_approved_curriculum_stops_generation(catalog_client, instructor, monkeypatch, published_course):
    from backend.app.marketing import service as marketing
    body = {'course_id':'PY-101','curriculum_id':999,'audience':'Beginners','objective':'Explain course benefits',
            'language':'en','channels':['linkedin']}
    plan(monkeypatch, [{'tool':'generate_campaign','body':body}])
    run = send(catalog_client, instructor)
    result = execute(catalog_client, instructor, run).json()
    assert result['state'] == 'failed'
    assert marketing.list_campaigns() == []


@pytest.mark.parametrize('call', [
    {'tool':'shell','body':{'command':'anything'}},
    {'tool':'course','path':{'course_id':'../secrets'}},
    {'tool':'courses','query':{'unknown':'value'}},
    {'tool':'generate_campaign','body':{'course_id':'PY-101'}},
    {'tool':'search_opportunities','body':{'notify':True}},
    {'tool':'download_document','path':{'artifact_id':'abcd','fmt':'exe'}},
])
def test_disallowed_or_invalid_calls_never_execute(catalog_client, instructor, monkeypatch, call):
    plan(monkeypatch, [call])
    run = send(catalog_client, instructor)
    assert run['state'] == 'failed' and run['results'] == []


def test_external_notifications_are_forced_off(catalog_client, instructor, monkeypatch):
    plan(monkeypatch, [{'tool':'search_opportunities','body':{}}])
    run = send(catalog_client, instructor, 'Search configured training opportunity sources')
    assert run['state'] == 'pending'
    assert run['plan']['calls'][0]['body']['notify'] is False


def test_cancel_and_pending_message_conflict(catalog_client, instructor, monkeypatch):
    plan(monkeypatch, [{'tool':'submit_curriculum','path':{'curriculum_id':1}}])
    run = send(catalog_client, instructor)
    headers, sid = instructor
    assert catalog_client.post(f'{BASE}/{sid}/messages', headers=headers,
        json={'message':'Another action','request_id':str(uuid4())}).status_code == 409
    assert catalog_client.post(f'{BASE}/{sid}/runs/{run["id"]}/cancel',headers=headers).json()['state'] == 'cancelled'
    assert execute(catalog_client, instructor, run).status_code == 409


def test_review_requires_record_preview_confirmation_and_fresh_state(catalog_client, instructor, monkeypatch):
    from backend.app.catalog import catalog_service as catalog
    upload = catalog_client.post('/api/v1/catalog/uploads', headers=instructor[0],
        files={'file':('source.md',b'A fictional isolated source for the test.')}).json()['upload_id']
    plan(monkeypatch, [{'tool':'reject_upload','path':{'upload_id':upload},
                        'body':{'reviewer':'spoof','reason':'Missing required source information'}}])
    run = send(catalog_client, instructor, 'Reject this upload because the required information is missing')
    assert run['review_record']['upload_id'] == upload and run['decision'] is True
    assert execute(catalog_client, instructor, run).status_code == 422
    catalog.reject_upload(upload, catalog.DocumentRejection(reviewer='Other reviewer', reason='Another reviewer rejected this source'))
    result = execute(catalog_client, instructor, run, reviewed=True).json()
    assert result['state'] == 'failed'
    assert 'changed since the preview' in result['results'][0]['detail']


def test_explicit_review_uses_existing_service_and_audit(catalog_client, instructor, monkeypatch):
    from backend.app.catalog import catalog_service as catalog
    upload = catalog_client.post('/api/v1/catalog/uploads', headers=instructor[0],
        files={'file':('source.md',b'A test source lacking mandatory course information.')}).json()['upload_id']
    plan(monkeypatch, [{'tool':'reject_upload','path':{'upload_id':upload},
                       'body':{'reason':'Required course details are missing'}}])
    run = send(catalog_client, instructor, 'Reject this source')
    result = execute(catalog_client, instructor, run, reviewed=True).json()
    assert result['state'] == 'completed'
    record = catalog.load_upload(upload)
    assert record['review_status'] == 'rejected' and record['rejected_by'] == 'Instructor Reviewer'
    assert record['review_history']


def test_generation_and_approval_cannot_share_a_plan(catalog_client, instructor, monkeypatch):
    plan(monkeypatch, [{'tool':'courses'}, {'tool':'approve_template','path':{'template_id':'course_description'},'body':{}}])
    run = send(catalog_client, instructor)
    assert run['state'] == 'failed' and run['results'] == []


def test_partial_failure_preserves_completed_results_and_stops(catalog_client, instructor, monkeypatch):
    plan(monkeypatch, [{'tool':'courses'}, {'tool':'submit_curriculum','path':{'curriculum_id':999}}, {'tool':'templates'}])
    run = send(catalog_client, instructor)
    result = execute(catalog_client, instructor, run).json()
    assert result['state'] == 'failed'
    assert [(r['tool'],r['state']) for r in result['results']] == [('courses','completed'),('submit_curriculum','failed')]


def test_provider_failure_is_saved_without_execution(catalog_client, instructor, monkeypatch):
    from fastapi import HTTPException
    def unavailable(*args):
        raise HTTPException(503, 'Provider quota reached')
    monkeypatch.setattr(service, 'generate_json', unavailable)
    run = send(catalog_client, instructor)
    assert run['state'] == 'failed' and run['error'] == 'Provider quota reached'


def test_read_execution_conflict_does_not_rewrite_planning_state(catalog_client, instructor, monkeypatch):
    from fastapi import HTTPException
    plan(monkeypatch, [{'tool': 'courses'}])
    async def conflict(*args, **kwargs):
        raise HTTPException(409, 'Execution already claimed; refresh the saved action')
    monkeypatch.setattr(service, 'execute', conflict)
    headers, sid = instructor
    response = catalog_client.post(f'{BASE}/{sid}/messages', headers=headers,
        json={'message': 'List courses', 'request_id': str(uuid4())})
    assert response.status_code == 409
    assert 'Execution already claimed' in response.json()['detail']
    saved = store.get(sid, headers['X-REX-Reviewer'])['runs'][-1]
    assert saved['state'] == 'pending' and saved['error'] is None


def test_tool_schemas_match_real_endpoints(catalog_client):
    definitions = tools.definitions(catalog_client.app)
    assert len(definitions) == 44
    assert all(d['path'].startswith('/api/v1/') for d in definitions)
    assert not any('instructor' in d['path'] or 'lead' in d['path'] for d in definitions)


def test_curriculum_generate_submit_review_and_pdf(catalog_client, instructor, monkeypatch, published_course):
    from backend.app.agents.curriculum import service as curriculum
    from test_curriculum_integration import valid_content
    monkeypatch.setattr(curriculum, 'generate_curriculum', lambda *args, **kwargs: valid_content())
    plan(monkeypatch, [{'tool':'generate_curriculum','body':{'subject':'Python','course_ids':['PY-101']}}])
    generated = execute(catalog_client, instructor, send(catalog_client, instructor)).json()
    assert generated['state'] == 'completed', generated
    cid = generated['results'][0]['result']['id']
    plan(monkeypatch, [{'tool':'submit_curriculum','path':{'curriculum_id':cid}}])
    assert execute(catalog_client, instructor, send(catalog_client, instructor)).json()['state'] == 'completed'
    plan(monkeypatch, [{'tool':'review_curriculum','path':{'curriculum_id':cid},
                       'body':{'action':'approve','notes':'Verified all teaching hours and assessments'}}])
    reviewed = execute(catalog_client, instructor, send(catalog_client, instructor), reviewed=True).json()
    assert reviewed['state'] == 'completed'
    assert curriculum.get_curriculum(cid)['status'] == 'approved'
    plan(monkeypatch, [{'tool':'download_curriculum','path':{'curriculum_id':cid}}])
    downloaded = send(catalog_client, instructor, 'Download the curriculum')
    path = downloaded['results'][0]['result']['download_path']
    assert catalog_client.get(path).status_code == 401
    assert catalog_client.get(path, headers=instructor[0]).content.startswith(b'%PDF')


def test_document_template_generation_review_and_download(catalog_client, instructor, monkeypatch, published_course, generator):
    plan(monkeypatch, [{'tool':'approve_template','path':{'template_id':'course_description'}}])
    approved = execute(catalog_client, instructor, send(catalog_client, instructor), reviewed=True).json()
    assert approved['state'] == 'completed'
    plan(monkeypatch, [{'tool':'generate_document','body':{'document_type':'course_description','course_ids':['PY-101']}}])
    generated = execute(catalog_client, instructor, send(catalog_client, instructor)).json()
    assert generated['state'] == 'completed', generated
    aid = generated['results'][0]['result']['artifact_id']
    plan(monkeypatch, [{'tool':'review_document','path':{'artifact_id':aid},
                       'body':{'decision':'approve','reason':'Verified every section against approved source evidence'}}])
    reviewed = execute(catalog_client, instructor, send(catalog_client, instructor), reviewed=True).json()
    assert reviewed['state'] == 'completed'
    plan(monkeypatch, [{'tool':'download_document','path':{'artifact_id':aid,'fmt':'docx'}}])
    downloaded = send(catalog_client, instructor)
    path = downloaded['results'][0]['result']['download_path']
    assert catalog_client.get(path, headers=instructor[0]).content.startswith(b'PK')


def test_instructor_conversations_are_isolated_in_demo(instructor, monkeypatch, tmp_path):
    monkeypatch.setenv('REX_APP_MODE','demo')
    monkeypatch.setenv('REX_DEMO_DATA_DIR',str(tmp_path/'demo'))
    assert store.sessions(instructor[0]['X-REX-Reviewer']) == []
