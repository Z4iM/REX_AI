"""Plain-language record cards, task guidance and readable audit timelines."""
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

STATUSES = {
    'pending_review': ('Needs review','orange'), 'blocked_incomplete': ('Fix unreadable pages','red'),
    'approved': ('Approved','green'), 'published': ('Live for learners','green'),
    'rejected': ('Rejected','red'), 'revision_requested': ('Changes requested','orange'),
    'withdrawn': ('Hidden from learners','gray'), 'draft': ('Draft','blue'),
    'index_failed': ('Publishing needs attention','red'), 'unapproved': ('Not approved','orange'),
    'completed': ('Completed','green'), 'failed': ('Needs attention','red'),
}


def status_label(status):
    return STATUSES.get(status, (str(status or 'Not reviewed').replace('_',' ').title(),'gray'))[0]


def badge(status):
    label, color = STATUSES.get(status, (status_label(status),'gray'))
    st.badge(label, color=color)


def date_label(value):
    if not value:
        return 'Date not recorded'
    try:
        dt = datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if dt.tzinfo:
            dt = dt.astimezone(ZoneInfo('Africa/Cairo'))
        return dt.strftime('%d %b %Y at %H:%M') + (' Cairo' if dt.tzinfo else '')
    except (ValueError, TypeError):
        return str(value)


def next_step(title, text, page=None, label='Continue'):
    with st.container(border=True):
        st.markdown('**' + title + '**')
        st.write(text)
        if page:
            st.page_link(page, label=label, icon=':material/arrow_forward:')


def record_picker(records, *, key, id_field='id', title_field='title', label='records', details=None, statuses=True, searchable=True):
    """Keep original IDs intact; filter and page visible cards without deleting data."""
    records = list(records)
    if any(r.get('created_at') or r.get('uploaded_at') for r in records):
        records.sort(key=lambda r:r.get('created_at') or r.get('uploaded_at') or '',reverse=True)
    if not records:
        st.info('No ' + label + ' yet.')
        return None
    query = st.text_input('Search ' + label, key=key+'-search', placeholder='Type a name or keyword').strip().casefold() if searchable else ''
    state_field = 'review_status' if 'review_status' in records[0] else 'status'
    status_values = list(dict.fromkeys(r.get(state_field) for r in records if r.get(state_field)))
    chosen = 'All'
    if statuses and len(status_values) > 1:
        chosen = st.pills('Show ' + label, ['All', *status_values], default='All',
                          format_func=lambda x: 'All' if x == 'All' else status_label(x), key=key+'-status') or 'All'
    shown = [r for r in records if (chosen == 'All' or r.get(state_field) == chosen)
             and (not query or query in ' '.join(str(r.get(k) or '') for k in
                  (title_field,id_field,'filename','document_type','course_titles','source_files','version')).casefold())]
    st.caption(f'{len(shown)} of {len(records)} {label}. Select a card to open it below.')
    if not shown:
        st.info('No matching records. Clear the search or choose All.')
        return None
    ids = [r[id_field] for r in shown]
    if st.session_state.get(key) not in ids:
        st.session_state[key] = ids[0]
    selected = st.session_state[key]
    if len(shown) == 1:
        st.caption('The matching record is open below.')
        return selected
    filter_key = (query, chosen, tuple(ids))
    if st.session_state.get(key+'-filter') != filter_key:
        st.session_state[key+'-filter'] = filter_key
        st.session_state[key+'-page'] = ids.index(selected)//6
    index = min(st.session_state.get(key+'-page',0), (len(shown)-1)//6)
    page = shown[index*6:(index+1)*6]
    for start in range(0,len(page),2):
        cols = st.columns(2)
        for col, r in zip(cols,page[start:start+2]):
            rid = r[id_field]
            with col, st.container(border=True):
                st.markdown('**' + str(r.get(title_field) or rid) + '**')
                if r.get(state_field):
                    badge(r[state_field])
                if details:
                    st.caption(details(r))
                else:
                    bits = []
                    if r.get('file_type'): bits.append(str(r['file_type']).upper()+' original')
                    if r.get('version'): bits.append('Version '+str(r['version']))
                    if r.get('language'): bits.append({'en':'English','ar':'Arabic'}.get(r['language'],r['language']))
                    if r.get('source_files'): bits.append('Source: '+', '.join(r['source_files']))
                    if r.get('created_at') or r.get('uploaded_at'): bits.append(date_label(r.get('created_at') or r.get('uploaded_at')))
                    st.caption(' · '.join(bits))
                if st.button(('Viewing ' if rid == selected else 'Open ') + str(r.get(title_field) or rid),
                             key=key+'-open-'+str(rid), disabled=rid == selected, width='stretch'):
                    st.session_state[key] = rid
                    st.rerun()
    if len(shown)>6:
        a,b,c = st.columns([1,2,1])
        if a.button('Previous',key=key+'-prev',disabled=index==0):
            st.session_state[key+'-page']=index-1;st.rerun()
        b.caption(f'Page {index+1} of {(len(shown)+5)//6}')
        if c.button('Next',key=key+'-next',disabled=(index+1)*6>=len(shown)):
            st.session_state[key+'-page']=index+1;st.rerun()
    return selected


def timeline(events, *, empty='No decisions recorded yet.'):
    if not events:
        st.info(empty)
    names = {'generated':'Draft created','created':'Created','approve':'Approved','approved':'Approved',
             'reject':'Rejected','rejected':'Rejected','request_revision':'Changes requested',
             'revised':'New draft version','submitted':'Sent for review','template_approved':'Template approved'}
    for event in reversed(events):
        action = event.get('action') or event.get('event') or 'Update'
        with st.container(border=True):
            st.markdown('**'+names.get(action,str(action).replace('_',' ').title())+'**')
            who = event.get('reviewer') or event.get('reviewer_name') or event.get('author') or ''
            when = event.get('recorded_at') or event.get('date') or event.get('created_at')
            st.caption(' · '.join(x for x in (str(who),date_label(when)) if x))
            text = event.get('reason') or event.get('note') or event.get('notes')
            if text:
                st.write(text)


def readable(value, title=None):
    """Display structured agent results in plain language, without a JSON editor."""
    if title:
        st.markdown('**'+str(title).replace('_',' ').title()+'**')
    if isinstance(value, dict):
        for key,item in value.items():
            if item is None or item == [] or item == {}:
                continue
            name=str(key).replace('_',' ').capitalize()
            if isinstance(item,(dict,list)):
                readable(item,name)
            else:
                st.write(name+': '+str(item))
    elif isinstance(value,list):
        for item in value:
            if isinstance(item,dict):
                with st.container(border=True):
                    readable(item)
            else:
                st.write('• '+str(item))
    else:
        st.write(value)
