"""Settings, read from the environment (or a .env file) at call time so tests can override them.
All RFP-specific variables are prefixed RFP_ so they cannot collide with the host REX AI application."""
import os
from pathlib import Path

try:  # optional
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

BASE_DIR = Path(__file__).parent  # package resources: sources.yaml, sample_tenders.json


def data_dir() -> Path:
    """Runtime data (SQLite file, imports/ drop folder). Override with RFP_DATA_DIR."""
    from backend.app.runtime import rfp_dir
    return rfp_dir()


def database_url() -> str:
    from backend.app.runtime import is_demo
    return (None if is_demo() else os.getenv("RFP_DATABASE_URL")) or f"sqlite:///{data_dir() / 'rfp.db'}"


def gemini_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or None


def gemini_model() -> str:
    return os.getenv("RFP_GEMINI_MODEL") or os.getenv("GEMINI_MODEL") or os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash")


def gemini_timeout_ms() -> int:
    return int(os.getenv("RFP_GEMINI_TIMEOUT_MS", "60000"))


def rfp_api_key() -> str | None:
    """Shared secret for the default API auth (n8n). Replace with the host app's staff auth via build_router(auth_dependency=...)."""
    return os.getenv("RFP_API_KEY") or None


def dashboard_password() -> str | None:
    return os.getenv("RFP_DASHBOARD_PASSWORD") or None


def require_dashboard_login() -> bool:
    return os.getenv("RFP_REQUIRE_LOGIN", "").lower() in ("1", "true", "yes")


def user_agent() -> str:
    return os.getenv("SCRAPER_USER_AGENT", "REX-AI-RFP-Research/1.0 (academy research prototype)")


def smtp_settings() -> dict | None:
    from backend.app.runtime import is_demo
    if is_demo():
        return None
    host = os.getenv("SMTP_HOST")
    recipients = [e.strip() for e in os.getenv("ALERT_EMAILS", "").split(",") if e.strip()]
    if not host or not recipients:
        return None
    return {
        "host": host, "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER"), "password": os.getenv("SMTP_PASSWORD"),
        "sender": os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "rex-ai@localhost")),
        "recipients": recipients,
    }


def n8n_webhook_url() -> str | None:
    from backend.app.runtime import is_demo
    if is_demo():
        return None
    return os.getenv("N8N_WEBHOOK_URL") or None
