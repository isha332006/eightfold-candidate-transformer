"""Extract from a LinkedIn profile.

IMPORTANT ASSUMPTION (documented in README/design doc): we do NOT scrape
linkedin.com live. LinkedIn has no public API for this purpose and scraping
it would violate their Terms of Service. Instead this extractor reads a
locally saved profile export (JSON), e.g. the kind a recruiting tool or the
candidate's own "Download your data" export would produce, containing
name/headline/experience/education. If only a bare LinkedIn URL is given
with no accompanying export file, we record the URL as a link and otherwise
treat the source as unavailable (degrade gracefully, never invent data).
"""
import json

from ..types import RawRecord


def extract_linkedin(path_or_url: str) -> list:
    if path_or_url.startswith("http"):
        rec = RawRecord(source="linkedin")
        rec.add("linkedin_link", path_or_url, "linkedin_url:as_given")
        return [rec] if rec.fields else []

    try:
        with open(path_or_url, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return []

    rec = RawRecord(source="linkedin")
    rec.add("full_name", data.get("name"), "linkedin_field:name")
    rec.add("headline", data.get("headline"), "linkedin_field:headline")
    rec.add("linkedin_link", data.get("profile_url"), "linkedin_field:profile_url")

    for exp in data.get("experience", []) or []:
        rec.add(
            "experience_raw",
            {
                "company": exp.get("company"),
                "title": exp.get("title"),
                "start": exp.get("start"),
                "end": exp.get("end"),
                "summary": exp.get("description"),
            },
            "linkedin_field:experience",
        )

    for edu in data.get("education", []) or []:
        rec.add(
            "education_raw",
            {
                "institution": edu.get("school"),
                "degree": edu.get("degree"),
                "field": edu.get("field_of_study"),
                "end_year": edu.get("end_year"),
            },
            "linkedin_field:education",
        )

    for skill in data.get("skills", []) or []:
        rec.add("skills_raw", skill, "linkedin_field:skills")

    return [rec] if rec.fields else []
