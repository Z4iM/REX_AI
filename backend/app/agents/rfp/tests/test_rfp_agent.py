"""Unit tests for rfp_agent.py  -  run with:  pytest -v"""
import json
from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from ..rfp_agent import (
    Tender, normalize_country, is_expired, is_relevant, fingerprint,
    filter_tenders, summarize_tender, classify_location,
)

TODAY = date(2026, 10, 19)  # fixed so tests don't break as real time passes
DATA = Path(__file__).parent.parent / "sample_tenders.json"


def make(**kw):
    base = dict(title="IT Training Program", issuer="Org", country="Egypt",
                deadline=date(2026, 12, 1), source_url="https://x.example/1")
    base.update(kw)
    return Tender(**base)


# ---------------- country ----------------
@pytest.mark.parametrize("raw,code", [
    ("Egypt", "EG"), ("egypt", "EG"), ("  EGYPT ", "EG"), ("مصر", "EG"), ("EG", "EG"),
    ("Saudi Arabia", "SA"), ("KSA", "SA"), ("السعودية", "SA"),
    ("المملكة العربية السعودية", "SA"), ("Kingdom of Saudi Arabia", "SA"),
])
def test_supported_countries(raw, code):
    assert normalize_country(raw) == code


@pytest.mark.parametrize("raw", ["Germany", "United States", "UAE", "Jordan", "", None, "   "])
def test_unsupported_or_missing_country_returns_none(raw):
    assert normalize_country(raw) is None


def test_foreign_country_is_rejected():
    r = filter_tenders([make(country="Germany")], today=TODAY)[0]
    assert r.status == "rejected" and "not supported" in r.reason


@pytest.mark.parametrize("country", [None, "", "   "])
def test_missing_country_needs_review_not_accepted(country):
    r = filter_tenders([make(country=country)], today=TODAY)[0]
    assert r.status == "needs_review"


# ---------------- priority ----------------
def test_egypt_is_high_priority():
    r = filter_tenders([make(country="Egypt")], today=TODAY)[0]
    assert (r.status, r.priority, r.country_code) == ("accepted", "high", "EG")


def test_saudi_is_monitor_priority():
    r = filter_tenders([make(country="KSA")], today=TODAY)[0]
    assert (r.status, r.priority, r.country_code) == ("accepted", "monitor", "SA")


# ---------------- expiry ----------------
def test_expired_is_rejected():
    r = filter_tenders([make(deadline=date(2026, 10, 18))], today=TODAY)[0]
    assert r.status == "rejected" and "Expired" in r.reason


def test_deadline_today_is_not_expired():
    assert not is_expired(make(deadline=TODAY), TODAY)


def test_no_deadline_is_a_lead_not_an_open_opportunity():
    r = filter_tenders([make(deadline=None)], today=TODAY)[0]
    assert r.status == "needs_review" and "Deadline unknown" in r.reason
    assert r.priority == "high"            # still flagged for Egypt priority review, but NOT verified as open


# ---------------- relevance ----------------
@pytest.mark.parametrize("title", ["Road Construction", "Supply of Medical Equipment", "Office Furniture"])
def test_unrelated_is_rejected(title):
    r = filter_tenders([make(title=title)], today=TODAY)[0]
    assert r.status == "rejected" and "Not related" in r.reason


def test_relevance_uses_category_and_description():
    assert is_relevant(make(title="Framework Agreement", category="Technical Training"))
    assert is_relevant(make(title="Services", description="تدريب الموظفين"))


# ---------------- duplicates ----------------
def test_exact_duplicate_in_same_batch_is_rejected():
    res = filter_tenders([make(), make(source_url="https://other.example/2")], today=TODAY)
    assert [r.status for r in res] == ["accepted", "rejected"]
    assert res[1].reason == "Duplicate opportunity"


def test_duplicate_ignores_case_and_spacing():
    assert fingerprint(make(title="IT  Training Program ")) == fingerprint(make(title="it training program"))


def test_duplicate_against_previously_seen():
    fp = fingerprint(make())
    r = filter_tenders([make()], seen_fingerprints={fp}, today=TODAY)[0]
    assert r.status == "rejected"


def test_different_deadline_is_not_duplicate():
    assert fingerprint(make()) != fingerprint(make(deadline=date(2027, 1, 1)))


def test_seen_set_passed_in_is_not_mutated():
    seen = set()
    filter_tenders([make()], seen_fingerprints=seen, today=TODAY)
    assert seen == set()


# ---------------- full sample dataset ----------------
@pytest.fixture(scope="module")
def dataset():
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    return raw, filter_tenders([Tender(**r) for r in raw], today=TODAY)


def test_dataset_every_record_matches_expected_status(dataset):
    raw, res = dataset
    wrong = [(r["title"], r["expected_status"], p.status) for r, p in zip(raw, res)
             if r["expected_status"] != p.status and r.get("source_url")]   # URL-less rows are a service rule
    assert wrong == []


def test_dataset_counts(dataset):
    _, res = dataset
    # filter level only: the record WITHOUT a URL is downgraded to needs_review later, by the service
    assert Counter(p.status for p in res) == {"accepted": 19, "rejected": 16, "needs_review": 5}
    assert Counter(p.priority for p in res if p.status == "accepted") == {"high": 11, "monitor": 8}


def test_dataset_only_egypt_and_saudi_are_accepted(dataset):
    _, res = dataset
    assert {p.country_code for p in res if p.status == "accepted"} <= {"EG", "SA"}


def test_dataset_no_expired_or_duplicates_accepted(dataset):
    _, res = dataset
    accepted = [p for p in res if p.status == "accepted"]
    assert all(not is_expired(p.tender, TODAY) for p in accepted)
    assert len({p.fingerprint for p in accepted}) == len(accepted)


# ---------------- Gemini (mocked, no API key needed) ----------------
class FakeClient:
    def __init__(self, text=None, error=None):
        self.models = self
        self._text, self._error = text, error

    def generate_content(self, **kwargs):
        if self._error:
            raise self._error
        return SimpleNamespace(text=self._text)


def test_summary_happy_path():
    txt = json.dumps({"summary": "Training for staff.", "eligibility_assessment": "unclear",
                      "eligibility_notes": "Registration status unknown."})
    out = summarize_tender(make(), client=FakeClient(txt))
    assert out["summary"] == "Training for staff." and out["eligibility_assessment"] == "unclear"


def test_summary_handles_markdown_fenced_json():
    txt = '```json\n{"summary": "S", "eligibility_assessment": "likely_eligible", "eligibility_notes": "n"}\n```'
    assert summarize_tender(make(), client=FakeClient(txt))["eligibility_assessment"] == "likely_eligible"


def test_summary_rejects_invalid_assessment_value():
    # the model must never be able to claim confirmed eligibility
    txt = json.dumps({"summary": "S", "eligibility_assessment": "eligible", "eligibility_notes": "n"})
    assert summarize_tender(make(), client=FakeClient(txt))["eligibility_assessment"] == "unclear"


def test_summary_falls_back_on_api_error():
    out = summarize_tender(make(), client=FakeClient(error=RuntimeError("429 rate limit")))
    assert out["summary"] is None and out["eligibility_assessment"] == "unclear"


def test_summary_falls_back_on_bad_json():
    out = summarize_tender(make(), client=FakeClient("not json at all"))
    assert out["summary"] is None


def test_missing_api_key_does_not_crash(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    out = summarize_tender(make())
    assert out["summary"] is None and "GEMINI_API_KEY" in out["eligibility_notes"]
