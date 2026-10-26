"""Persistent qualification sessions. A random session ID is a private bearer token."""
from dataclasses import asdict
import json
import time
from uuid import uuid4, UUID

from fastapi import HTTPException
from backend.app.catalog.catalog_service import catalog_transaction
from .qualification import QualificationSession, process_qualification

TTL_SECONDS = 7 * 24 * 60 * 60


def _schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS qualification_sessions (
        session_id TEXT PRIMARY KEY, session_json TEXT NOT NULL, expires_at REAL NOT NULL
    )""")
    con.execute("DELETE FROM qualification_sessions WHERE expires_at < ?", (time.time(),))


def _read(con, session_id):
    try:
        if str(UUID(session_id)) != session_id:
            return None
    except (ValueError, TypeError, AttributeError):
        return None
    row = con.execute("SELECT session_json FROM qualification_sessions WHERE session_id=?", (session_id,)).fetchone()
    return QualificationSession(**json.loads(row["session_json"])) if row else None


def get_session(session_id):
    with catalog_transaction() as con:
        _schema(con)
        return _read(con, session_id)


def advance_session(session_id, message):
    with catalog_transaction() as con:
        _schema(con)
        if session_id is None:
            session_id, session = str(uuid4()), QualificationSession()
        else:
            session = _read(con, session_id)
            if session is None:
                raise HTTPException(404, "Conversation session not found")
        if session.completed:
            raise HTTPException(409, "Qualification already completed")
        result = process_qualification(session, message)
        con.execute("INSERT OR REPLACE INTO qualification_sessions VALUES (?,?,?)",
                    (session_id, json.dumps(asdict(session), ensure_ascii=False), time.time() + TTL_SECONDS))
    return session_id, result


def delete_session(session_id):
    with catalog_transaction() as con:
        _schema(con)
        # Remove the associated contact record and session under the same lock.
        if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learner_leads'").fetchone():
            con.execute("DELETE FROM learner_leads WHERE session_id=?", (session_id,))
        con.execute("DELETE FROM qualification_sessions WHERE session_id=?", (session_id,))
