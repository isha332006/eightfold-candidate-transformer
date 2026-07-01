"""Extract from resume prose (PDF or DOCX). Best-effort regex/heuristics --
resumes are unstructured text, so we extract what we can confidently find
and leave the rest null rather than guessing.
"""
import re

from ..types import RawRecord, SKILL_SYNONYMS

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\-\.\s()]{7,}\d)")
YEAR_RANGE_RE = re.compile(
    r"(?P<start>[A-Za-z]{3,9}\.?\s\d{4}|\d{4})\s*[-–to]+\s*(?P<end>[A-Za-z]{3,9}\.?\s\d{4}|\d{4}|[Pp]resent|[Cc]urrent)"
)


def _read_pdf(path):
    import pdfplumber
    text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            text.append(t)
    return "\n".join(text)


def _read_docx(path):
    import docx
    d = docx.Document(path)
    return "\n".join(p.text for p in d.paragraphs)


def _extract_section(text, header_names):
    """Grab the block of text under a heading like 'Experience' or 'Education'
    until the next ALL-CAPS-ish heading or end of doc."""
    lines = text.splitlines()
    out = []
    capturing = False
    for line in lines:
        stripped = line.strip()
        if any(stripped.lower().startswith(h) for h in header_names) and len(stripped) < 40:
            capturing = True
            continue
        if capturing:
            if stripped and stripped.isupper() and len(stripped.split()) <= 4:
                break  # hit next section heading
            if stripped and stripped.istitle() and len(stripped.split()) <= 3 and len(stripped) < 30 and out:
                # likely a new section header in title case
                pass
            out.append(line)
    return "\n".join(out).strip()


def extract_resume(path: str) -> list:
    try:
        if path.lower().endswith(".pdf"):
            text = _read_pdf(path)
        elif path.lower().endswith(".docx"):
            text = _read_docx(path)
        else:
            return []
    except Exception:
        return []  # corrupt/unreadable file: degrade gracefully

    if not text or not text.strip():
        return []

    rec = RawRecord(source="resume")

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        # heuristic: first non-empty line that looks like a name (2-4 words, no @, no digits)
        for l in lines[:3]:
            if "@" not in l and not any(c.isdigit() for c in l) and 1 <= len(l.split()) <= 4:
                rec.add("full_name", l, "resume_heuristic:first_line")
                break

    emails = EMAIL_RE.findall(text)
    for e in emails:
        rec.add("email_raw", e, "regex:email")

    for m in PHONE_RE.finditer(text):
        candidate = m.group(1)
        if sum(c.isdigit() for c in candidate) >= 7:
            rec.add("phone_raw", candidate, "regex:phone")

    # skills: scan for known synonym keys as whole words/phrases
    found_skills = set()
    low_text = text.lower()
    for alias in SKILL_SYNONYMS:
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, low_text):
            found_skills.add(alias)
    for s in found_skills:
        rec.add("skills_raw", s, "regex:skill_keyword")

    # experience section (very best-effort)
    exp_text = _extract_section(text, ["experience", "work experience", "professional experience"])
    if exp_text:
        exp_lines = [l for l in exp_text.splitlines() if l.strip()]
        blocks = []
        current = []
        for line in exp_lines:
            looks_like_header = (
                ("," in line or "|" in line)
                and not YEAR_RANGE_RE.fullmatch(line.strip())
                and len(line) < 80
                and not line.strip().endswith(".")
            )
            if looks_like_header and current:
                blocks.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(current)

        for block_lines in blocks:
            block = "\n".join(block_lines)
            date_match = YEAR_RANGE_RE.search(block)
            header = block_lines[0]
            company, title = None, None
            if "," in header:
                parts = [p.strip() for p in header.split(",", 1)]
                title, company = parts[0], parts[1]
            elif "|" in header:
                parts = [p.strip() for p in header.split("|", 1)]
                title, company = parts[0], parts[1]
            else:
                title = header
            summary_lines = [l for l in block_lines[1:] if not YEAR_RANGE_RE.fullmatch(l.strip())]
            rec.add(
                "experience_raw",
                {
                    "company": company,
                    "title": title,
                    "start": date_match.group("start") if date_match else None,
                    "end": date_match.group("end") if date_match else None,
                    "summary": " ".join(summary_lines)[:300] or None,
                },
                "resume_section:experience",
            )

    # education section
    edu_text = _extract_section(text, ["education"])
    if edu_text:
        for block in [b.strip() for b in edu_text.split("\n\n") if b.strip()] or [edu_text]:
            block_lines = [l for l in block.splitlines() if l.strip()]
            if not block_lines:
                continue
            year_match = re.search(r"(19|20)\d{2}", block)
            rec.add(
                "education_raw",
                {
                    "institution": block_lines[0],
                    "degree": block_lines[1] if len(block_lines) > 1 else None,
                    "field": None,
                    "end_year": int(year_match.group(0)) if year_match else None,
                },
                "resume_section:education",
            )

    # naive years-of-experience: count distinct year range spans, take max span
    spans = []
    for m in YEAR_RANGE_RE.finditer(text):
        try:
            start_y = int(re.search(r"\d{4}", m.group("start")).group(0))
            end_raw = m.group("end")
            end_y = 2026 if end_raw.lower() in ("present", "current") else int(re.search(r"\d{4}", end_raw).group(0))
            spans.append((start_y, end_y))
        except Exception:
            continue
    if spans:
        total_years = max(e for _, e in spans) - min(s for s, _ in spans)
        if total_years > 0:
            rec.add("years_experience_raw", total_years, "resume_heuristic:date_span")

    return [rec] if rec.fields else []
