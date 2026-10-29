"""SQLite conversation/audit storage, isolated with the catalog runtime."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4
from fastapi import HTTPException
from backend.app import runtime


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    directory = runtime.catalog_dir()
    directory.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(directory / 'instructor.sqlite3', timeout=15)
    con.row_factory = sqlite3.Row
    try:
        con.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, reviewer TEXT NOT NULL, created_at TEXT NOT NULL)')
        con.execute('''CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, request_id TEXT NOT NULL,
            state TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(session_id, request_id))''')
        con.commit()
        con.execute('BEGIN IMMEDIATE')
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def authorize(con, sid, reviewer):
    row = con.execute('SELECT * FROM sessions WHERE id=? AND reviewer=?', (sid, reviewer)).fetchone()
    if not row:
        raise HTTPException(404, 'Instructor conversation not found')
    return dict(row)


def create(reviewer):
    record = {'id': str(uuid4()), 'reviewer': reviewer, 'created_at': now()}
    with connection() as con:
        con.execute('INSERT INTO sessions VALUES (:id,:reviewer,:created_at)', record)
    return {**record, 'runs': []}


def sessions(reviewer):
    with connection() as con:
        items = []
        for row in con.execute('SELECT * FROM sessions WHERE reviewer=? ORDER BY created_at DESC LIMIT 100', (reviewer,)):
            first = con.execute('SELECT data FROM runs WHERE session_id=? ORDER BY rowid LIMIT 1', (row['id'],)).fetchone()
            title = json.loads(first['data'])['message'][:90] if first else 'New conversation'
            items.append({**dict(row), 'title': title})
        return items


def get(sid, reviewer):
    with connection() as con:
        record = authorize(con, sid, reviewer)
        record['runs'] = [json.loads(r['data']) for r in con.execute('SELECT data FROM runs WHERE session_id=? ORDER BY rowid', (sid,))]
        return record


def reserve(sid, reviewer, request_id, message):
    with connection() as con:
        authorize(con, sid, reviewer)
        row = con.execute('SELECT data FROM runs WHERE session_id=? AND request_id=?', (sid, request_id)).fetchone()
        if row:
            value = json.loads(row['data'])
            if value['message'] != message:
                raise HTTPException(409, 'Request identifier was already used for a different message')
            return value, False
        if con.execute("SELECT 1 FROM runs WHERE session_id=? AND state IN ('planning','pending','executing')", (sid,)).fetchone():
            raise HTTPException(409, 'Finish or cancel the current proposed actions first')
        record = {'id': str(uuid4()), 'session_id': sid, 'request_id': request_id,
                  'message': message, 'state': 'planning', 'created_at': now(), 'updated_at': now(),
                  'plan': None, 'results': [], 'error': None}
        con.execute('INSERT INTO runs VALUES (?,?,?,?,?)', (record['id'], sid, request_id, 'planning', json.dumps(record, ensure_ascii=False)))
        return record, True


def update(record, expected=None):
    record['updated_at'] = now()
    with connection() as con:
        row = con.execute('SELECT state FROM runs WHERE id=?', (record['id'],)).fetchone()
        if not row or expected is not None and row['state'] != expected:
            raise HTTPException(409, 'Action state changed; refresh the conversation')
        con.execute('UPDATE runs SET state=?,data=? WHERE id=?', (record['state'], json.dumps(record, ensure_ascii=False), record['id']))
    return record


def run(sid, rid, reviewer):
    session = get(sid, reviewer)
    found = next((r for r in session['runs'] if r['id'] == rid), None)
    if not found:
        raise HTTPException(404, 'Instructor action not found')
    return found
