"""Extract from free-text recruiter notes. Lowest-confidence source -- we
only pull out clearly-patterned signals (email, phone, explicit skill
mentions) and tag the whole thing as low-reliability via SOURCE_WEIGHTS.
"""
import re

from ..types import RawRecord, SKILL_SYNONYMS

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\-\.\s()]{7,}\d)")
NAME_HINT_RE = re.compile(r"(?:re:|regarding|candidate:|notes on)\s+([A-Z][a-zA-Z'\-]+(?:\s[A-Z][a-zA-Z'\-]+){0,2})", re.IGNORECASE)


def _extract_block(text: str) -> RawRecord:
    rec = RawRecord(source="recruiter_notes")

    name_match = NAME_HINT_RE.search(text)
    if name_match:
        rec.add("full_name", name_match.group(1), "regex:name_hint")

    for e in EMAIL_RE.findall(text):
        rec.add("email_raw", e, "regex:email")

    for m in PHONE_RE.finditer(text):
        if sum(c.isdigit() for c in m.group(1)) >= 7:
            rec.add("phone_raw", m.group(1), "regex:phone")

    low_text = text.lower()
    for alias in SKILL_SYNONYMS:
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, low_text):
            rec.add("skills_raw", alias, "regex:skill_keyword")

    return rec


def extract_recruiter_notes(path: str) -> list:
    """A single notes file may contain free-text blurbs about MULTIPLE
    candidates (a common real-world pattern: one running notes doc per
    recruiter). We split on a '---' delimiter (or blank-line-separated
    blocks that each start with a name hint) so each candidate becomes
    its own record instead of getting incorrectly merged into one."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except (FileNotFoundError, UnicodeDecodeError):
        return []

    if not text.strip():
        return []

    if "---" in text:
        blocks = [b for b in text.split("---") if b.strip()]
    else:
        blocks = [text]

    records = [_extract_block(b) for b in blocks]
    return [r for r in records if r.fields]
