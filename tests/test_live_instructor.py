"""Opt-in provider check; all records use temporary test databases."""
import os
from pathlib import Path
from uuid import uuid4
import pytest
from dotenv import dotenv_values
from test_connected_workflows import approved_plan

pytestmark = pytest.mark.skipif(os.getenv('REX_RUN_LIVE_TESTS') != '1', reason='Live AI checks are explicitly opt-in')


def test_live_instructor_creates_campaign(catalog_client, staff_headers, approved_plan, monkeypatch):
    key = dotenv_values(Path(__file__).resolve().parents[1] / '.env').get('GROQ_API_KEY')
    if not key:
        pytest.skip('Configure the local provider key before live verification')
    monkeypatch.setenv('GROQ_API_KEY', key)
    monkeypatch.setenv('REX_AI_PROVIDER', 'groq')
    monkeypatch.setenv('REX_RETRIEVAL_BACKEND', 'sqlite')
    headers = {**staff_headers, 'X-REX-Reviewer':'Isolated provider test instructor'}
    sid = catalog_client.post('/api/v1/instructor/sessions', headers=headers).json()['id']
    base = '/api/v1/instructor/sessions/' + sid
    run = catalog_client.post(base + '/messages', headers=headers, json={
        'request_id':str(uuid4()),
        'message':f'Create a marketing campaign draft for existing published course PY-101, using approved curriculum {approved_plan["id"]}. '
                  'Audience: beginners learning Python. Goal: explain verified outcomes and invite admissions enquiries. '
                  'Language: English. Channel: linkedin only. No budget, no revision. Propose one generate_campaign call. Do not approve or send it.'}).json()
    assert run['state'] == 'pending', run.get('error') or run.get('plan')
    assert [c['tool'] for c in run['plan']['calls']] == ['generate_campaign']
    response = catalog_client.post(base + '/runs/' + run['id'] + '/execute', headers=headers,
                                   json={'confirmed':True, 'reviewed':False})
    assert response.status_code == 200, response.text
    assert response.json()['state'] == 'completed', response.text
    campaign = response.json()['results'][0]['result']
    assert campaign['status'] == 'pending_review'
    assert campaign['course']['course_id'] == 'PY-101'
    assert campaign['curriculum']['id'] == approved_plan['id']
