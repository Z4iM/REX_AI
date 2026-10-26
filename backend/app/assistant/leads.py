"""Consent-based lead capture. Contact data is never sent to Gemini."""
import json
import re
import time
from typing import Literal
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.app.catalog import catalog_service as store
from .session_store import get_session

CONSENT_VERSION = "training-follow-up-v1"
RETENTION_SECONDS = 30 * 24 * 60 * 60


class LeadRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Explicit consent must be true")
        return value

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        if value is not None and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value):
        if value is not None and (not re.fullmatch(r"\+?[\d ()-]{7,40}", value) or sum(c.isdigit() for c in value) < 7):
            raise ValueError("Enter a valid phone number")
        return value

    @model_validator(mode="after")
    def contact_required(self):
        if not self.email and not self.phone:
            raise ValueError("Provide an email address or phone number")
        return self


def _schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS learner_leads (
        lead_id TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE,
        record_json TEXT NOT NULL, expires_at REAL NOT NULL)""")
    con.execute("DELETE FROM learner_leads WHERE expires_at < ?", (time.time(),))


def save_lead(session_id: str, payload: LeadRequest):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Learner session not found or expired")
    if not session.completed:
        raise HTTPException(409, "Complete learner qualification before submitting contact information")
    with store.catalog_transaction() as con:
        _schema(con)
        active = con.execute("SELECT expires_at FROM qualification_sessions WHERE session_id=?", (session_id,)).fetchone()
        if not active or active["expires_at"] <= time.time():
            raise HTTPException(404, "Learner session not found or expired")
        row = con.execute("SELECT lead_id FROM learner_leads WHERE session_id=?", (session_id,)).fetchone()
        lead_id = row["lead_id"] if row else str(uuid4())
        record = {"lead_id": lead_id, **payload.model_dump(), "interest": session.initial_request,
                  "profile": session.answers, "consent_version": CONSENT_VERSION, "consented_at": store._now()}
        con.execute("INSERT INTO learner_leads VALUES (?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET record_json=excluded.record_json,expires_at=excluded.expires_at",
                    (lead_id, session_id, json.dumps(record, ensure_ascii=False), time.time() + RETENTION_SECONDS))
    return {"lead_id": lead_id, "status": "saved", "consent_version": CONSENT_VERSION,
            "retention_days": 30, "message": "Saved for academy staff follow-up. No message has been sent."}


def list_leads():
    with store.catalog_transaction() as con:
        _schema(con)
        return [json.loads(row["record_json"]) for row in con.execute("SELECT record_json FROM learner_leads ORDER BY rowid DESC")]


def delete_lead(session_id):
    with store.catalog_transaction() as con:
        _schema(con)
        con.execute("DELETE FROM learner_leads WHERE session_id=?", (session_id,))
