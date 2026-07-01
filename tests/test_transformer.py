import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from transformer.normalize import (
    normalize_phone, normalize_email, normalize_date_to_yyyymm,
    normalize_skill, normalize_country,
)
from transformer.detect import detect_source
from transformer.pipeline import run_pipeline
from transformer.project import project_profile, ProjectionError

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "sample_inputs")


# ---------------- normalization ----------------

def test_normalize_phone_various_formats_converge():
    assert normalize_phone("(415) 555-0142") == "+14155550142"
    assert normalize_phone("+14155550142") == "+14155550142"
    assert normalize_phone("415.555.0142") == "+14155550142"


def test_normalize_phone_garbage_returns_none():
    assert normalize_phone("not-a-phone-number") is None
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_normalize_email_valid_and_invalid():
    assert normalize_email("Alice.Nguyen@Example.com") == "alice.nguyen@example.com"
    assert normalize_email("not-an-email") is None
    assert normalize_email("") is None


def test_normalize_date_formats():
    assert normalize_date_to_yyyymm("Jan 2022") == "2022-01"
    assert normalize_date_to_yyyymm("2019-06") == "2019-06"
    assert normalize_date_to_yyyymm("present") is None


def test_normalize_skill_synonyms():
    assert normalize_skill("js") == "JavaScript"
    assert normalize_skill("python") == "Python"
    assert normalize_skill("Postgres") == "PostgreSQL"


def test_normalize_country():
    assert normalize_country("United States") == "US"
    assert normalize_country("IN") == "IN"
    assert normalize_country("Narnia") is None


# ---------------- detection ----------------

def test_detect_missing_file():
    assert detect_source("/tmp/does_not_exist_xyz.csv") == "missing"


def test_detect_csv_and_resume():
    assert detect_source(os.path.join(FIXTURES, "recruiter_export.csv")) == "recruiter_csv"
    assert detect_source(os.path.join(FIXTURES, "resume_alice_nguyen.docx")) == "resume"


def test_detect_malformed_json():
    assert detect_source(os.path.join(FIXTURES, "corrupt_ats_export.json")) == "malformed_json"


def test_detect_empty_file():
    assert detect_source(os.path.join(FIXTURES, "empty_recruiter_export.csv")) == "empty"


# ---------------- end-to-end pipeline ----------------

@pytest.fixture(scope="module")
def pipeline_result():
    sources = [
        os.path.join(FIXTURES, "recruiter_export.csv"),
        os.path.join(FIXTURES, "ats_export.json"),
        os.path.join(FIXTURES, "recruiter_notes.txt"),
        os.path.join(FIXTURES, "resume_alice_nguyen.docx"),
        os.path.join(FIXTURES, "resume_bob_carter.docx"),
        os.path.join(FIXTURES, "corrupt_ats_export.json"),
        os.path.join(FIXTURES, "empty_recruiter_export.csv"),
    ]
    return run_pipeline(sources)


def test_pipeline_produces_three_local_candidates(pipeline_result):
    names = sorted(p["full_name"] for p in pipeline_result["profiles"])
    assert names == ["Alice Nguyen", "Bob Carter", "Priya Sharma"]


def test_pipeline_does_not_crash_on_bad_sources(pipeline_result):
    assert pipeline_result["errors"] == []
    assert any("malformed_json" in w or "corrupt" in w for w in pipeline_result["warnings"])


def test_alice_phone_dedup_across_three_formats(pipeline_result):
    """Alice's phone appears differently formatted in CSV, ATS, and notes --
    after normalization these must collapse into ONE E.164 value, with
    corroboration raising confidence."""
    alice = next(p for p in pipeline_result["profiles"] if p["full_name"] == "Alice Nguyen")
    assert alice["phones"] == ["+14155550142"]
    skill_confs = [s["confidence"] for s in alice["skills"] if s["name"] == "Python"]
    assert skill_confs and skill_confs[0] >= 0.9  # corroborated by 3 sources


def test_priya_garbage_phone_is_dropped_not_invented(pipeline_result):
    """Priya's CSV phone is garbage ('not-a-phone-number'); it must be
    dropped, not guessed at -- and her valid ATS phone should still appear."""
    priya = next(p for p in pipeline_result["profiles"] if p["full_name"] == "Priya Sharma")
    assert "not-a-phone-number" not in priya["phones"]
    assert priya["phones"] == ["+919812345678"]


def test_bob_missing_from_ats_still_has_profile(pipeline_result):
    """Bob is absent from the ATS export entirely -- pipeline must still
    produce a (thinner, lower-confidence) profile from CSV + resume alone."""
    bob = next(p for p in pipeline_result["profiles"] if p["full_name"] == "Bob Carter")
    assert bob["emails"] == ["bob.carter@example.com"]
    assert bob["overall_confidence"] < 0.9  # fewer corroborating sources


def test_every_field_has_provenance(pipeline_result):
    alice = next(p for p in pipeline_result["profiles"] if p["full_name"] == "Alice Nguyen")
    assert len(alice["provenance"]) > 0
    assert all({"field", "source", "method"} <= set(p.keys()) for p in alice["provenance"])


def test_determinism_same_inputs_same_output(pipeline_result):
    sources = [
        os.path.join(FIXTURES, "recruiter_export.csv"),
        os.path.join(FIXTURES, "ats_export.json"),
        os.path.join(FIXTURES, "recruiter_notes.txt"),
        os.path.join(FIXTURES, "resume_alice_nguyen.docx"),
        os.path.join(FIXTURES, "resume_bob_carter.docx"),
    ]
    r1 = run_pipeline(sources)
    r2 = run_pipeline(sources)
    ids1 = sorted(p["candidate_id"] for p in r1["profiles"])
    ids2 = sorted(p["candidate_id"] for p in r2["profiles"])
    assert ids1 == ids2
    assert json.dumps(r1["profiles"], sort_keys=True) == json.dumps(r2["profiles"], sort_keys=True)


# ---------------- projection / runtime config ----------------

def test_projection_subset_and_rename(pipeline_result):
    alice = next(p for p in pipeline_result["profiles"] if p["full_name"] == "Alice Nguyen")
    config = {
        "fields": [
            {"path": "full_name", "type": "string", "required": True},
            {"path": "primary_email", "from": "emails[0]", "type": "string", "required": True},
        ],
        "include_confidence": False,
        "include_provenance": False,
    }
    projected = project_profile(alice, config)
    assert projected["primary_email"] == "alice.nguyen@example.com"
    assert "provenance" not in projected
    assert "overall_confidence" not in projected
    assert "phones" not in projected  # subset selection


def test_projection_on_missing_omit():
    profile = {"candidate_id": "x", "full_name": "Test", "emails": []}
    config = {"fields": [{"path": "email", "from": "emails[0]"}], "on_missing": "omit"}
    out = project_profile(profile, config)
    assert "email" not in out


def test_projection_on_missing_error_raises():
    profile = {"candidate_id": "x", "full_name": "Test", "emails": []}
    config = {"fields": [{"path": "email", "from": "emails[0]", "required": True}], "on_missing": "error"}
    with pytest.raises(ProjectionError):
        project_profile(profile, config)


def test_projection_normalize_skills_canonical():
    profile = {"candidate_id": "x", "skills": [{"name": "js", "confidence": 0.9, "sources": ["resume"]}]}
    config = {"fields": [{"path": "skills", "from": "skills[].name", "normalize": "canonical"}]}
    out = project_profile(profile, config)
    assert out["skills"] == ["JavaScript"]


def test_linkedin_export_merges_into_priya_profile():
    sources = [
        os.path.join(FIXTURES, "recruiter_export.csv"),
        os.path.join(FIXTURES, "ats_export.json"),
        os.path.join(FIXTURES, "recruiter_notes.txt"),
        os.path.join(FIXTURES, "linkedin_export_priya.json"),
    ]
    result = run_pipeline(sources)
    priya = next(p for p in result["profiles"] if p["full_name"] == "Priya Sharma")
    assert priya["links"]["linkedin"] == "https://www.linkedin.com/in/priya-sharma-example"
    assert len(priya["experience"]) == 2
    assert any(e["company"] == "Vertex Health" for e in priya["experience"])
