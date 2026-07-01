"""Step 1: detect what kind of source a given input path/URL is."""
import json
import os


def detect_source(path: str) -> str:
    """Return one of: recruiter_csv, ats_json, github, linkedin, resume, recruiter_notes, unknown.

    Detection is layered: URL pattern first, then file extension, then a peek
    at file content for ambiguous extensions (e.g. a .json could be ATS export
    or a saved LinkedIn export).
    """
    p = path.strip()
    low = p.lower()

    if low.startswith("http://") or low.startswith("https://"):
        if "github.com" in low:
            return "github"
        if "linkedin.com" in low:
            return "linkedin"
        return "unknown_url"

    if not os.path.exists(p):
        return "missing"

    if os.path.getsize(p) == 0:
        return "empty"

    ext = os.path.splitext(low)[1]

    if ext == ".csv":
        return "recruiter_csv"
    if ext in (".pdf", ".docx"):
        return "resume"
    if ext == ".txt":
        return "recruiter_notes"
    if ext == ".json":
        # Could be an ATS export or a saved LinkedIn profile export.
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return "malformed_json"
        sample = json.dumps(data).lower()
        if "headline" in sample and ("linkedin" in sample or "experience" in sample and "education" in sample and "candidate_name" not in sample):
            return "linkedin"
        return "ats_json"

    return "unknown"
