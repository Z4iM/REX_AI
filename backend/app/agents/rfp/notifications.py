"""
Alerts for NEW opportunities.
  1) Dashboard notifications (rows in SQLite) - always
  2) Email digest via SMTP                     - only if SMTP_* + ALERT_EMAILS are configured
  3) Optional webhook to n8n                   - only if N8N_WEBHOOK_URL is configured
n8n may notify but never approves anything. A UNIQUE(opportunity_id, kind) constraint plus "only alert on rows
inserted in this run" means a retried run can never send the same alert twice.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

import requests
from sqlalchemy.orm import Session

from . import config
from .db import Notification, Opportunity

KIND_LABEL = {
    "egypt_priority": "EGYPT - PRIORITY REVIEW",
    "saudi_monitor": "Saudi Arabia - monitored",
    "egypt_verify": "EGYPT - PRIORITY FOR VERIFICATION (not confirmed open / not verified)",
    "saudi_verify": "Saudi Arabia - needs verification (not confirmed open / not verified)",
    "needs_review": "Needs verification (not confirmed open / not verified)",
}


def kind_for(opp: Opportunity) -> str:
    """Alerts never call an unverified lead a ready-to-apply opportunity."""
    verified = opp.filter_status == "accepted"
    if opp.priority == "high":
        return "egypt_priority" if verified else "egypt_verify"
    if opp.priority == "monitor":
        return "saudi_monitor" if verified else "saudi_verify"
    return "needs_review"


def make_message(opp: Opportunity) -> str:
    dl = opp.deadline.isoformat() if opp.deadline else "deadline unknown"
    tag = f" [{opp.data_mode}]" if opp.data_mode in ("synthetic_demo", "search_discovered", "llm_extracted") else ""
    return f"{KIND_LABEL[kind_for(opp)]}: {opp.title} - {opp.issuer} (deadline: {dl}){tag}"


def create_notifications(session: Session, new_opps: list[Opportunity]) -> list[Notification]:
    created = []
    for o in new_opps:
        n = Notification(opportunity_id=o.id, kind=kind_for(o), message=make_message(o))
        session.add(n)
        created.append(n)
    session.commit()
    return created


def send_email_digest(session: Session, notifs: list[Notification]) -> bool:
    """One email per run. Egypt first. Returns True if sent."""
    cfg = config.smtp_settings()
    if not cfg or not notifs:
        return False
    order = {"egypt_priority": 0, "egypt_verify": 1, "saudi_monitor": 2, "saudi_verify": 3, "needs_review": 4}
    notifs = sorted(notifs, key=lambda n: order.get(n.kind, 3))
    lines = []
    for n in notifs:
        o = n.opportunity
        lines.append(f"- {n.message}\n  Source: {o.source_url or '(no verifiable source URL - import reference: ' + str(o.import_reference) + ')'}")
    msg = EmailMessage()
    msg["Subject"] = f"REX AI: {len(notifs)} new tender opportunit{'y' if len(notifs) == 1 else 'ies'}"
    msg["From"] = cfg["sender"]
    msg["To"] = ", ".join(cfg["recipients"])
    msg.set_content("New leads found by the REX AI RFP agent.\n"
                    "Items marked 'verification' have NOT been confirmed. Eligibility notes are unverified AI opinions.\n\n" + "\n".join(lines))
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
            s.starttls()
            if cfg["user"]:
                s.login(cfg["user"], cfg["password"] or "")
            s.send_message(msg)
    except Exception as e:  # never crash the pipeline because of email
        print(f"[notifications] email failed: {type(e).__name__}")
        return False
    for n in notifs:
        n.email_sent = True
    session.commit()
    return True


def post_webhook(notifs: list[Notification]) -> bool:
    url = config.n8n_webhook_url()
    if not url or not notifs:
        return False
    payload = {"count": len(notifs),
               "items": [{"kind": n.kind, "message": n.message, "source_url": n.opportunity.source_url, "verified": n.opportunity.filter_status == "accepted",
                          "deadline": n.opportunity.deadline.isoformat() if n.opportunity.deadline else None}
                         for n in notifs]}
    try:
        return requests.post(url, json=payload, timeout=15).ok
    except requests.RequestException as e:
        print(f"[notifications] webhook failed: {type(e).__name__}")
        return False
