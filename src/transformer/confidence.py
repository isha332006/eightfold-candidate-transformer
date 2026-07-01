"""Step 5: confidence scoring.

A field's confidence reflects (a) how reliable its winning source is and
(b) how many independent sources corroborate the same value. This keeps the
"wrong-but-confident" failure mode in check: a single low-weight source
(e.g. recruiter notes) never produces a high-confidence value on its own.
"""
from .types import SOURCE_WEIGHTS


def score(winning_source: str, corroborating_sources: int) -> float:
    base = SOURCE_WEIGHTS.get(winning_source, 0.4)
    bonus = min(0.10 * max(0, corroborating_sources - 1), 0.20)
    return round(min(base + bonus, 1.0), 2)


def overall_confidence(field_confidences: list) -> float:
    if not field_confidences:
        return 0.0
    return round(sum(field_confidences) / len(field_confidences), 2)
