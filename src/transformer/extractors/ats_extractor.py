"""Extract from an ATS JSON blob. Field names are the ATS's own and do NOT
match our canonical schema, so we map via a small alias table instead of
assuming a fixed structure.
"""
import json

from ..types import RawRecord

# canonical_field -> list of possible (dotted) paths / keys the ATS might use
ALIASES = {
    "full_name": ["candidate_name", "name", "full_name"],
    "email_raw": ["contact.email_address", "email", "contact.email", "email_address"],
    "phone_raw": ["contact.mobile", "phone", "contact.phone", "mobile"],
    "current_company": ["employer", "company", "current_employer"],
    "current_title": ["role", "job_title", "title"],
    "skills_raw": ["skills_list", "skills", "tech_skills"],
    "headline": ["summary", "headline", "tagline"],
    "city": ["location.city", "city"],
    "country": ["location.country", "country"],
}


def _dig(obj, dotted_path):
    cur = obj
    for part in dotted_path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _first_match(obj, paths):
    for p in paths:
        val = _dig(obj, p)
        if val not in (None, "", []):
            return val, p
    return None, None


def extract_ats_json(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return []  # malformed/missing source: degrade gracefully

    entries = data if isinstance(data, list) else data.get("candidates", [data])
    records = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rec = RawRecord(source="ats_json")
        for canonical_field, paths in ALIASES.items():
            val, used_path = _first_match(entry, paths)
            if val is None:
                continue
            if canonical_field == "skills_raw" and isinstance(val, list):
                for s in val:
                    rec.add("skills_raw", s, f"ats_json_field:{used_path}")
            else:
                rec.add(canonical_field, val, f"ats_json_field:{used_path}", raw=str(val))
        if rec.fields:
            records.append(rec)
    return records
