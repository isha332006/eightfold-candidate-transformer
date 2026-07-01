"""Orchestrates the full pipeline: detect -> extract -> normalize -> merge
-> confidence -> project -> validate. Deterministic: same inputs, same
config -> same output JSON, every time.
"""
import hashlib
import json

from .detect import detect_source
from .extractors.csv_extractor import extract_recruiter_csv
from .extractors.ats_extractor import extract_ats_json
from .extractors.github_extractor import extract_github
from .extractors.linkedin_extractor import extract_linkedin
from .extractors.resume_extractor import extract_resume
from .extractors.notes_extractor import extract_recruiter_notes
from .identity import cluster_records
from .merge import merge_cluster
from .project import project_profile
from .schema import validate_profile, DEFAULT_SCHEMA

EXTRACTOR_MAP = {
    "recruiter_csv": extract_recruiter_csv,
    "ats_json": extract_ats_json,
    "github": extract_github,
    "linkedin": extract_linkedin,
    "resume": extract_resume,
    "recruiter_notes": extract_recruiter_notes,
}


def _candidate_id(profile_seed: str) -> str:
    h = hashlib.sha1(profile_seed.encode("utf-8")).hexdigest()[:10]
    return f"cand_{h}"


def run_pipeline(source_paths: list, config: dict = None, strict: bool = False) -> dict:
    """Returns {'profiles': [...], 'warnings': [...], 'errors': [...]}."""
    warnings, errors = [], []
    all_records = []

    for path in source_paths:
        kind = detect_source(path)
        if kind in ("missing", "empty", "malformed_json", "unknown", "unknown_url"):
            warnings.append(f"Skipped source (reason={kind}): {path}")
            continue
        extractor = EXTRACTOR_MAP.get(kind)
        if not extractor:
            warnings.append(f"No extractor for detected type '{kind}': {path}")
            continue
        try:
            records = extractor(path)
        except Exception as e:  # never let one bad source crash the run
            warnings.append(f"Extractor error on {path} ({kind}): {e}")
            records = []
        if not records:
            warnings.append(f"No data extracted from {path} ({kind})")
        all_records.extend(records)

    clusters = cluster_records(all_records)

    profiles = []
    for cluster in clusters:
        # deterministic id seed: prefer first email, else first name, else source list
        seed = None
        for rec in cluster:
            if "email_raw" in rec.fields:
                seed = str(rec.fields["email_raw"][0].value).lower().strip()
                break
        if not seed:
            for rec in cluster:
                if "full_name" in rec.fields:
                    seed = str(rec.fields["full_name"][0].value).lower().strip()
                    break
        if not seed:
            seed = "|".join(sorted(r.source for r in cluster))

        candidate_id = _candidate_id(seed)
        profile = merge_cluster(cluster, candidate_id)

        errs = validate_profile(profile, DEFAULT_SCHEMA)
        if errs:
            warnings.append(f"Schema warnings for {candidate_id}: {errs}")

        try:
            projected = project_profile(profile, config)
        except Exception as e:
            msg = f"Projection failed for {candidate_id}: {e}"
            if strict:
                errors.append(msg)
                continue
            warnings.append(msg)
            projected = profile

        profiles.append(projected)

    return {"profiles": profiles, "warnings": warnings, "errors": errors}
