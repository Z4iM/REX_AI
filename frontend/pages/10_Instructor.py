"""Conversational access to the existing reviewed academy workflows."""
from uuid import uuid4
import streamlit as st
from frontend.ui import api, header, require_staff
from frontend.components import record_picker, date_label, readable

header('Instructor workspace', 'Describe your goal. REX coordinates the academy agents and shows proposed changes before running them.')
reviewer = require_staff()
st.caption('Your existing staff sign-in applies here. Reviews, publication and source verification remain human decisions.')

with st.expander('Attach a course source'):
    source = st.file_uploader('Course document', type=['pdf', 'docx', 'md'])
    if st.button('Upload for staff review', disabled=source is None):
        if source.size > 10 * 1024 * 1024:
            st.error('Maximum upload size is 10 MiB.')
        else:
            result = api('POST', '/api/v1/catalog/uploads', files={'file': (source.name, source.getvalue())})
            if result:
                st.success(result['message'])
                st.code(result['upload_id'], language=None)

with st.expander('Import an opportunity export'):
    opportunity_file = st.file_uploader('Opportunity export', type=['json', 'csv', 'xlsx'])
    if st.button('Import and validate opportunities', disabled=opportunity_file is None):
        from backend.app.agents.rfp.sources import parse_upload, SourceError
        try:
            if opportunity_file.size > 10 * 1024 * 1024:
                raise ValueError('File too large')
            rows = parse_upload(opportunity_file.name, opportunity_file.getvalue())
            if not 1 <= len(rows) <= 200:
                raise ValueError('Invalid record count')
            result = api('POST', '/api/v1/rfp/import', json={'items': rows, 'use_gemini': False})
            if result:
                st.success(f'{result["new"]} saved; {result["rejected"]} rejected; {result["duplicates"]} duplicates.')
                readable(result)
        except (ValueError, TypeError, SourceError):
            st.error('Choose a valid JSON, CSV or Excel export with 1–200 records, no larger than 10 MiB.')

sessions = api('GET', '/api/v1/instructor/sessions')
if sessions is None:
    st.stop()
items = sessions['items']
left, right = st.columns([3, 1])
with right:
    if st.button('New conversation', type='primary'):
        created = api('POST', '/api/v1/instructor/sessions')
        if created:
            st.session_state['instructor_session'] = created['id']
            st.rerun()
if not items:
    st.info('Start a conversation to create a campaign, design a curriculum, prepare documents or manage training opportunities.')
    st.stop()
selected=record_picker([{**s,"title":s.get("title") or "Conversation · "+date_label(s["created_at"])} for s in items],
    key="instructor_session",label="conversations",statuses=False)
if selected is None:
    st.stop()
base = '/api/v1/instructor/sessions/' + selected
session = api('GET', base)
if not session:
    st.stop()
if not session['runs']:
    with st.chat_message('assistant', avatar=':material/assistant:'):
        st.write('What would you like to prepare? Start by naming a course or asking to see the published courses.')
        st.caption('You can request a curriculum, campaign, training document or opportunity search. Include your audience, language and goal. REX will ask for missing details and show changes for confirmation.')

def render_result(result, key):
    if not isinstance(result, dict):
        readable(result)
        return
    if path := result.get('download_path'):
        if st.button('Prepare download', key=key):
            raw = api('GET', path, binary=True)
            if raw:
                ext = 'docx' if path.endswith('/docx') else 'json' if path.endswith('/export') else 'pdf'
                st.download_button('Download file', raw, file_name='andalusia-output.' + ext,
                                   mime=result.get('media_type'), key=key + '-file')
        return
    if result.get('answer'):
        st.write(result['answer'])
    if result.get('modules'):
        st.subheader(result.get('title', 'Curriculum'))
        st.write(result.get('description', ''))
        st.caption(str(result.get('training_hours', '')) + ' training hours · ' + str(result.get('status', '')))
        for field in ('objectives', 'prerequisites', 'learning_outcomes'):
            if result.get(field):
                st.markdown('**' + field.replace('_', ' ').title() + '**')
                for item in result[field]:
                    st.write(item)
        for module in result['modules']:
            with st.container(border=True):
                st.markdown('**'+module.get('title','Module')+'**')
                st.write(module.get('description', ''))
                st.caption(str(module.get('duration_hours', '')) + ' hours')
                for field in ('topics', 'learning_outcomes', 'activities'):
                    if module.get(field):
                        st.markdown('**' + field.replace('_', ' ').title() + '**')
                        for item in module[field]:
                            st.write(item)
        for field in ('practical_exercises', 'assessments', 'capstone_project'):
            if result.get(field):
                with st.container(border=True):
                    readable(result[field],field)
    if result.get('filename'):
        st.markdown('**Source: ' + result['filename'] + '**')
        st.caption(str(result.get('review_status', '')))
        with st.expander('Read extracted source content'):
            for chunk in result.get('chunks', []):
                st.write(chunk.get('text', ''))
    if isinstance(result.get('content'), dict):
        content = result['content']
        st.subheader(content.get('title', result.get('title', 'Saved output')))
        if content.get('strategy'):
            st.write(content['strategy'])
        for section in content.get('sections', []):
            st.markdown('**' + section['heading'] + '**')
            st.write(section['text'])
        for channel in content.get('channels', []):
            st.markdown('**' + channel['channel'].replace('_', ' ').title() + '**')
            for text in channel['variations']:
                st.write(text)
    if not result.get('content') and not result.get('modules'):
        readable(result)
    elif st.session_state.get('show_technical_details'):
        st.json(result, expanded=False)
    if result.get('artifact_id'):
        st.session_state['selected_document'] = result['artifact_id']
        st.page_link('pages/5_Document_Generation.py', label='Open document studio', icon=':material/description:')
    elif result.get('id') and 'channels' in result.get('content', {}):
        st.session_state['campaign_selected'] = result['id']
        st.page_link('pages/9_Marketing.py', label='Open campaign studio', icon=':material/campaign:')
    elif result.get('id') and result.get('modules'):
        st.session_state['curriculum_selected'] = result['id']
        st.page_link('pages/8_Curriculum.py', label='Open curriculum studio', icon=':material/account_tree:')

busy = False
for run in session['runs']:
    with st.chat_message('user', avatar=':material/person:'):
        st.write(run['message'])
    with st.chat_message('assistant', avatar=':material/assistant:'):
        st.caption(run['state'].replace('_', ' ').title())
        if run.get('plan'):
            st.write(run['plan']['reply'])
        if run.get('error'):
            st.error(str(run['error']))
        for index, result in enumerate(run['results']):
            st.markdown('**' + result['tool'].replace('_', ' ').title() + '**')
            if result['state'] == 'completed':
                render_result(result['result'], run['id'] + str(index))
            else:
                st.error(str(result.get('detail', 'Action failed')))
        if run['state'] == 'pending':
            busy = True
            st.write('Proposed actions')
            for call in run['plan']['calls']:
                st.markdown('**' + call['tool'].replace('_', ' ').title() + '**')
                for group in ('path', 'query', 'body'):
                    for field, value in call[group].items():
                        if field in ('requester', 'reviewer', 'reviewer_name'):
                            continue
                        if isinstance(value, dict) or isinstance(value, list) and any(isinstance(x, dict) for x in value):
                            with st.container(border=True):
                                readable(value,field)
                        else:
                            st.write(field.replace('_', ' ').title() + ': ' + (', '.join(map(str, value)) if isinstance(value, list) else str(value)))
            reviewed = False
            if run.get('decision'):
                st.warning('Inspect the current record and decision before confirming. This changes its review or publication status.')
                render_result(run['review_record'], run['id'] + '-record')
                reviewed = st.checkbox('I inspected this record and authorize the proposed decision', key=run['id'] + '-review')
            a, b = st.columns(2)
            if a.button('Run proposed actions', key=run['id'] + '-execute', type='primary', disabled=run.get('decision', False) and not reviewed):
                with st.spinner('Running the existing agent workflows...'):
                    result = api('POST', base + '/runs/' + run['id'] + '/execute',
                                 json={'confirmed': True, 'reviewed': reviewed}, request_timeout=600)
                if result:
                    st.rerun()
            if b.button('Cancel proposed actions', key=run['id'] + '-cancel'):
                if api('POST', base + '/runs/' + run['id'] + '/cancel'):
                    st.rerun()
        if run['state'] in ('planning', 'executing'):
            busy = True
            st.info('An action is in progress. Refresh to check saved results. If the server was interrupted, inspect the agent records before starting a new conversation; do not repeat a generation blindly.')
if st.button('Refresh conversation'):
    st.rerun()
if prompt := st.chat_input('For example: create an Arabic campaign for Python Foundations', disabled=busy, max_chars=6000):
    with st.spinner('Checking the available courses and planning the next steps...'):
        result = api('POST', base + '/messages', json={'message': prompt, 'request_id': str(uuid4())})
    if result:
        st.rerun()
