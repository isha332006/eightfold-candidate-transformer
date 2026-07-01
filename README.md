# Eightfold Multi-Source Candidate Data Transformer

Turns messy, multi-source candidate data (recruiter CSV, ATS JSON, GitHub,
LinkedIn, resumes, recruiter notes) into one canonical, deduplicated,
provenance-tracked candidate profile — with a runtime-configurable output
shape and no code changes required to reshape it.

See `DESIGN.pdf` (or `DESIGN.md`) for the one-page technical design write-up
(pipeline breakdown, schema, merge/confidence policy, edge cases, scope
decisions).

## Quick start

```bash
git clone <this-repo>
cd eightfold-candidate-transformer
pip install -r requirements.txt

# Default canonical schema, end-to-end on the sample inputs:
PYTHONPATH=src python3 -m transformer.cli \
  --sources sample_inputs/recruiter_export.csv \
            sample_inputs/ats_export.json \
            sample_inputs/recruiter_notes.txt \
            sample_inputs/resume_alice_nguyen.docx \
            sample_inputs/resume_bob_carter.docx \
            sample_inputs/linkedin_export_priya.json \
            sample_inputs/corrupt_ats_export.json \
            sample_inputs/empty_recruiter_export.csv \
            https://github.com/octocat \
  --out sample_outputs/default_output.json

# Same engine, custom runtime config (rename/subset/normalize fields):
PYTHONPATH=src python3 -m transformer.cli \
  --sources sample_inputs/recruiter_export.csv sample_inputs/ats_export.json \
            sample_inputs/recruiter_notes.txt sample_inputs/resume_alice_nguyen.docx \
            sample_inputs/resume_bob_carter.docx https://github.com/octocat \
  --config configs/example_config.json \
  --out sample_outputs/custom_output_example_config.json

# Run the tests
python3 -m pytest tests/ -v
```

Output goes to the `--out` path as schema-valid JSON: `{"profiles": [...]}`.
Use `--out -` to print to stdout instead. Run-time warnings (skipped/garbage
sources, schema notices) print to stderr; the run never crashes on a bad
source.

## What's in the sample inputs

Three synthetic candidates engineered to exercise the required behaviors,
plus a fourth pulled live from the real GitHub API:

| Candidate | Sources | What it tests |
|---|---|---|
| **Alice Nguyen** | CSV, ATS JSON, recruiter notes, resume (.docx) | Full coverage; phone number appears in **3 different raw formats** across sources and must collapse into one E.164 value with boosted confidence; skills/experience/education merged from multiple sources |
| **Bob Carter** | CSV, resume (.docx) | Missing entirely from the ATS source — pipeline must still produce a valid, lower-confidence profile |
| **Priya Sharma** | CSV (garbage phone), ATS JSON, recruiter notes, LinkedIn export (.json) | A malformed phone number (`not-a-phone-number`) in one source must be **dropped, never invented**, while the valid phone from another source still comes through; experience/education populated from LinkedIn alone |
| **The Octocat** | GitHub API (live, `https://github.com/octocat`) | Real REST API call (`api.github.com`); single-source candidate (thin, low-confidence profile); demonstrates the unstructured-source group independent of resumes/notes |

Also included, to exercise robustness directly:
- `corrupt_ats_export.json` — truncated/invalid JSON (parse failure)
- `empty_recruiter_export.csv` — zero-byte file

Both are passed to the pipeline in the default run above and are **skipped
with a warning**, not a crash (see stderr output / `warnings` from
`run_pipeline`).

## Project layout

```
src/transformer/
  detect.py            # Step 1: identify source type from path/URL/content
  extractors/           # Step 2: one extractor per source type
    csv_extractor.py
    ats_extractor.py     # alias-based field mapping (ATS field names != ours)
    github_extractor.py  # live REST calls to api.github.com
    linkedin_extractor.py  # reads a local profile export (see note below)
    resume_extractor.py  # PDF/DOCX prose -> regex + section heuristics
    notes_extractor.py   # free-text recruiter notes, multi-candidate aware
  normalize.py          # Step 3: phone (E.164), dates (YYYY-MM), skills, country
  identity.py           # cross-source person matching (email, then name)
  merge.py              # Step 4: per-field conflict resolution + provenance
  confidence.py         # Step 5: source-weight + corroboration scoring
  schema.py             # default canonical JSON schema + validation
  project.py            # Step 6: runtime-config projection layer
  pipeline.py           # orchestrates all of the above
  cli.py                # command-line entry point
configs/                 # example runtime configs
sample_inputs/           # synthetic + live sample sources described above
sample_outputs/          # produced output, default + 2 custom configs
tests/                   # pytest suite (normalization, merge, edge cases, config)
```

## Runtime config

Same engine, no code changes — pass `--config path/to/config.json`. See
`configs/example_config.json` (rename + normalize + subset) and
`configs/contact_card_config.json` (a smaller field subset with
`on_missing: "omit"`). Config shape:

```json
{
  "fields": [
    { "path": "full_name", "type": "string", "required": true },
    { "path": "primary_email", "from": "emails[0]", "type": "string", "required": true },
    { "path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164" },
    { "path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical" }
  ],
  "include_confidence": true,
  "include_provenance": false,
  "on_missing": "null"
}
```

`on_missing`: `"null"` (default, fill with null), `"omit"` (drop the key),
or `"error"` (raise/skip the field if `required: true`).

## Assumptions & deliberate descopes (note these, per the assignment)

- **LinkedIn**: there is no public API, and live scraping linkedin.com would
  violate their Terms of Service, so `linkedin_extractor.py` reads a
  **locally saved profile export (JSON)** rather than scraping a live URL.
  If only a bare LinkedIn URL is given, the pipeline records it as a link
  and otherwise treats the source as unavailable — it never fabricates
  profile data. This is a conscious scope decision, documented in
  `DESIGN.pdf`.
- **GitHub** uses the real public REST API (`api.github.com`, no auth) — see
  the live Octocat sample above. The sandbox network occasionally returns a
  transient `403` on the first call or two; the extractor retries with
  backoff and degrades gracefully (treats the source as missing) if it still
  fails, rather than crashing the run.
- Resume parsing is regex/heuristic-based (no LLM call), since the
  assignment scopes this as a deterministic, explainable pipeline. It does
  well on reasonably-structured resumes (clear "Experience"/"Education"
  headers, `Title, Company` lines) and degrades to partial/null fields
  rather than guessing on free-form layouts.
- `region` (state/province) is left `null` in the samples since none of the
  source data disambiguates it from `city`/`country` — left null rather than
  guessed, per the "never invent" constraint.
- Years of experience is a simple heuristic (max span across detected date
  ranges in the resume), not a verified work-history calculation.

## Demo video

See submission email / form for the ~2 min walkthrough covering: default
output run, custom-config run, and a deep dive on the phone-format-merge +
garbage-phone-drop edge cases above.
