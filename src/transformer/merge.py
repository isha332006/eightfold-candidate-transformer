"""Step 4 (+5): merge raw, normalized observations from multiple sources
into one canonical value per field, with provenance + confidence.

Design:
  - Scalar fields (full_name, headline, current company/title used inside
    experience, years_experience): pick the value from the highest-weight
    source; ties broken by corroboration count then lexicographic value for
    determinism (same inputs -> same output, always).
  - List fields (emails, phones, skills, links.other): UNION of all valid,
    normalized values across sources (deduplicated), each tagged with its
    contributing sources for provenance + per-skill confidence.
  - experience / education: collected as a list, de-duplicated by
    (company, title, start) / (institution, degree) since the same job or
    degree may be reported by more than one source.
"""
from collections import defaultdict

from . import confidence as conf
from .normalize import (
    normalize_email, normalize_phone, normalize_date_to_yyyymm,
    normalize_skill, normalize_country, normalize_name,
)
from .types import SOURCE_WEIGHTS


def _pick_scalar(values_by_source):
    """values_by_source: list of (value, source). Picks the value backed by the
    highest-weight source; ties broken by corroboration count, then by the
    value's string form for determinism. Returns (value, winning_source, corroborating_count)."""
    if not values_by_source:
        return None, None, 0
    groups = defaultdict(set)
    for value, source in values_by_source:
        groups[value].add(source)

    def rank(item):
        value, sources = item
        top_weight = max(SOURCE_WEIGHTS.get(s, 0.4) for s in sources)
        return (top_weight, len(sources), str(value))

    best_value, best_sources = max(groups.items(), key=rank)
    winning_source = max(best_sources, key=lambda s: SOURCE_WEIGHTS.get(s, 0.4))
    return best_value, winning_source, len(best_sources)


def merge_cluster(cluster: list, candidate_id: str) -> dict:
    """cluster: list[RawRecord] for one person. Returns a canonical profile dict
    (pre-projection) plus 'provenance' and '_field_confidence' (internal)."""
    provenance = []
    field_conf = {}

    def record_provenance(field, source, method):
        provenance.append({"field": field, "source": source, "method": method})

    # ---- full_name ----
    name_candidates = []
    for rec in cluster:
        for fv in rec.fields.get("full_name", []):
            norm = normalize_name(str(fv.value))
            if norm:
                name_candidates.append((norm, rec.source))
                record_provenance("full_name", rec.source, fv.method)
    full_name, src, corro = _pick_scalar(name_candidates)
    field_conf["full_name"] = conf.score(src, corro) if src else 0.0

    # ---- emails (list) ----
    email_sources = defaultdict(set)
    for rec in cluster:
        for fv in rec.fields.get("email_raw", []):
            norm = normalize_email(str(fv.value))
            if norm:
                email_sources[norm].add(rec.source)
                record_provenance("emails", rec.source, fv.method)
    emails = sorted(email_sources.keys())

    # ---- phones (list, E.164) ----
    phone_sources = defaultdict(set)
    for rec in cluster:
        for fv in rec.fields.get("phone_raw", []):
            norm = normalize_phone(str(fv.value))
            if norm:
                phone_sources[norm].add(rec.source)
                record_provenance("phones", rec.source, fv.method)
    phones = sorted(phone_sources.keys())

    # ---- location ----
    city_candidates, country_candidates = [], []
    for rec in cluster:
        for fv in rec.fields.get("city", []):
            city_candidates.append((str(fv.value).strip(), rec.source))
            record_provenance("location", rec.source, fv.method)
        for fv in rec.fields.get("country", []):
            c = normalize_country(str(fv.value))
            if c:
                country_candidates.append((c, rec.source))
                record_provenance("location", rec.source, fv.method)
        for fv in rec.fields.get("location_raw", []):
            # e.g. github "City, ST" or "City, Country" free text
            parts = [p.strip() for p in str(fv.value).split(",")]
            if parts:
                city_candidates.append((parts[0], rec.source))
                record_provenance("location", rec.source, fv.method)
            if len(parts) > 1:
                c = normalize_country(parts[-1])
                if c:
                    country_candidates.append((c, rec.source))
    city, csrc, ccorro = _pick_scalar(city_candidates)
    country, cosrc, cocorro = _pick_scalar(country_candidates)
    location = {"city": city, "region": None, "country": country}
    loc_confs = [conf.score(csrc, ccorro)] if csrc else []
    loc_confs += [conf.score(cosrc, cocorro)] if cosrc else []
    field_conf["location"] = conf.overall_confidence(loc_confs)

    # ---- links ----
    links = {"linkedin": None, "github": None, "portfolio": None, "other": []}
    gh_candidates, li_candidates, pf_candidates = [], [], []
    for rec in cluster:
        for fv in rec.fields.get("github_link", []):
            gh_candidates.append((str(fv.value), rec.source))
            record_provenance("links.github", rec.source, fv.method)
        for fv in rec.fields.get("linkedin_link", []):
            li_candidates.append((str(fv.value), rec.source))
            record_provenance("links.linkedin", rec.source, fv.method)
        for fv in rec.fields.get("portfolio_link", []):
            pf_candidates.append((str(fv.value), rec.source))
            record_provenance("links.portfolio", rec.source, fv.method)
    links["github"], _, _ = _pick_scalar(gh_candidates)
    links["linkedin"], _, _ = _pick_scalar(li_candidates)
    links["portfolio"], _, _ = _pick_scalar(pf_candidates)

    # ---- headline ----
    headline_candidates = []
    for rec in cluster:
        for fv in rec.fields.get("headline", []):
            headline_candidates.append((str(fv.value).strip(), rec.source))
            record_provenance("headline", rec.source, fv.method)
    headline, hsrc, hcorro = _pick_scalar(headline_candidates)
    field_conf["headline"] = conf.score(hsrc, hcorro) if hsrc else 0.0

    # ---- years_experience ----
    yoe_candidates = []
    for rec in cluster:
        for fv in rec.fields.get("years_experience_raw", []):
            try:
                yoe_candidates.append((int(fv.value), rec.source))
                record_provenance("years_experience", rec.source, fv.method)
            except (TypeError, ValueError):
                continue
    years_experience, ysrc, ycorro = _pick_scalar(yoe_candidates)
    field_conf["years_experience"] = conf.score(ysrc, ycorro) if ysrc else 0.0

    # ---- skills (union, each with own confidence + sources) ----
    skill_sources = defaultdict(set)
    for rec in cluster:
        for fv in rec.fields.get("skills_raw", []):
            norm = normalize_skill(str(fv.value))
            if norm:
                skill_sources[norm].add(rec.source)
                record_provenance("skills", rec.source, fv.method)
    skills = []
    for name, sources in sorted(skill_sources.items()):
        winning = max(sources, key=lambda s: SOURCE_WEIGHTS.get(s, 0.4))
        skills.append({
            "name": name,
            "confidence": conf.score(winning, len(sources)),
            "sources": sorted(sources),
        })
    field_conf["skills"] = conf.overall_confidence([s["confidence"] for s in skills])

    # ---- experience (dedup by company+title+start) ----
    exp_seen = {}
    for rec in cluster:
        for fv in rec.fields.get("experience_raw", []):
            v = fv.value
            company = (v.get("company") or "").strip() or None
            title = (v.get("title") or "").strip() or None
            start = normalize_date_to_yyyymm(v.get("start")) if v.get("start") else None
            end = normalize_date_to_yyyymm(v.get("end")) if v.get("end") else None
            key = (company, title, start)
            entry = {"company": company, "title": title, "start": start, "end": end,
                      "summary": v.get("summary")}
            if key not in exp_seen or SOURCE_WEIGHTS.get(rec.source, 0) > exp_seen[key][1]:
                exp_seen[key] = (entry, SOURCE_WEIGHTS.get(rec.source, 0))
                record_provenance("experience", rec.source, fv.method)
    experience = [e for e, _ in exp_seen.values()]
    # also fold in CSV/ATS "current" company+title as an experience entry w/ no dates
    cur_candidates = []
    for rec in cluster:
        for fv in rec.fields.get("current_company", []):
            for tv in rec.fields.get("current_title", []):
                cur_candidates.append(((fv.value, tv.value), rec.source))
    if cur_candidates and not any(e["end"] is None and e["company"] for e in experience):
        (company, title), src = cur_candidates[0]
        if company and not any(e["company"] == company for e in experience):
            experience.append({"company": company, "title": title, "start": None, "end": None,
                                "summary": "Current role per recruiter/ATS record."})
            record_provenance("experience", src, "current_role_inference")
    field_conf["experience"] = conf.overall_confidence(
        [conf.score(src, 1) for src in {p["source"] for p in provenance if p["field"] == "experience"}]
    )

    # ---- education (dedup by institution+degree) ----
    edu_seen = {}
    for rec in cluster:
        for fv in rec.fields.get("education_raw", []):
            v = fv.value
            inst = (v.get("institution") or "").strip() or None
            degree = (v.get("degree") or "").strip() or None
            key = (inst, degree)
            if not inst:
                continue
            entry = {"institution": inst, "degree": degree, "field": v.get("field"),
                      "end_year": v.get("end_year")}
            if key not in edu_seen or SOURCE_WEIGHTS.get(rec.source, 0) > edu_seen[key][1]:
                edu_seen[key] = (entry, SOURCE_WEIGHTS.get(rec.source, 0))
                record_provenance("education", rec.source, fv.method)
    education = [e for e, _ in edu_seen.values()]
    field_conf["education"] = conf.overall_confidence(
        [conf.score(src, 1) for src in {p["source"] for p in provenance if p["field"] == "education"}]
    )

    field_conf["emails"] = conf.overall_confidence(
        [conf.score(max(s, key=lambda x: SOURCE_WEIGHTS.get(x, 0.4)), len(s)) for s in email_sources.values()]
    )
    field_conf["phones"] = conf.overall_confidence(
        [conf.score(max(s, key=lambda x: SOURCE_WEIGHTS.get(x, 0.4)), len(s)) for s in phone_sources.values()]
    )

    profile = {
        "candidate_id": candidate_id,
        "full_name": full_name,
        "emails": emails,
        "phones": phones,
        "location": location,
        "links": links,
        "headline": headline,
        "years_experience": years_experience,
        "skills": skills,
        "experience": experience,
        "education": education,
        "provenance": provenance,
        "overall_confidence": conf.overall_confidence(
            [v for v in field_conf.values() if v is not None]
        ),
    }
    return profile
