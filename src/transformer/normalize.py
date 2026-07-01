"""Step 3: normalize raw extracted values into canonical formats."""
import re
from datetime import datetime
from typing import Optional

import phonenumbers

from .types import SKILL_SYNONYMS

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

COUNTRY_ALPHA2 = {
    "united states": "US", "usa": "US", "u.s.a.": "US", "u.s.": "US",
    "india": "IN", "united kingdom": "GB", "uk": "GB", "canada": "CA",
    "germany": "DE", "france": "FR", "australia": "AU", "singapore": "SG",
}


def normalize_email(raw: str) -> Optional[str]:
    if not raw:
        return None
    candidate = raw.strip().lower()
    if EMAIL_RE.match(candidate):
        return candidate
    return None  # malformed -> dropped, never invented


def normalize_phone(raw: str, default_region: str = "US") -> Optional[str]:
    """Best-effort E.164 normalization. Returns None (never guesses) on failure."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        parsed = phonenumbers.parse(raw, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None


def normalize_date_to_yyyymm(raw: str) -> Optional[str]:
    """Normalize a variety of date strings to YYYY-MM. Returns None if unparseable."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower() in ("present", "current", "now", "ongoing"):
        return None  # represents "ongoing"; caller treats missing end as present
    formats = ["%Y-%m", "%Y/%m", "%B %Y", "%b %Y", "%m/%Y", "%Y-%m-%d", "%B %d, %Y", "%Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue
    # last resort: pull a 4-digit year
    m = re.search(r"(19|20)\d{2}", raw)
    if m:
        return f"{m.group(0)}-01"
    return None


def normalize_skill(raw: str) -> Optional[str]:
    if not raw:
        return None
    key = raw.strip().lower().strip(".,")
    if not key:
        return None
    return SKILL_SYNONYMS.get(key, raw.strip().title() if key.isalpha() else raw.strip())


def normalize_country(raw: str) -> Optional[str]:
    if not raw:
        return None
    key = raw.strip().lower()
    if len(raw.strip()) == 2 and raw.strip().isalpha():
        return raw.strip().upper()
    return COUNTRY_ALPHA2.get(key)


def normalize_name(raw: str) -> Optional[str]:
    if not raw:
        return None
    return " ".join(w.capitalize() if w.islower() or w.isupper() else w for w in raw.strip().split())
