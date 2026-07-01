"""Step 6: project the canonical internal profile into whatever shape the
runtime config asks for. This is the ONLY place that knows about configs --
the canonical record (merge.py output) never changes shape. Config errors
or per-field issues are handled per the `on_missing` policy and never crash
the run.
"""
import re


def _get_path(obj, path):
    """Resolve a dotted/bracketed path like 'location.city', 'emails[0]',
    or 'skills[].name' against the canonical profile dict."""
    if "[]" in path:
        # e.g. skills[].name -> split into list part + subfield
        list_path, subfield = path.split("[].", 1)
        lst = _get_path(obj, list_path)
        if not isinstance(lst, list):
            return None
        return [_get_path(item, subfield) for item in lst]

    tokens = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    cur = obj
    for tok in tokens:
        if tok.startswith("["):
            idx = int(tok[1:-1])
            if isinstance(cur, list) and 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            if isinstance(cur, dict) and tok in cur:
                cur = cur[tok]
            else:
                return None
    return cur


def _apply_normalize(value, normalize):
    if value is None or not normalize:
        return value
    from . import normalize as norm_mod
    if normalize.upper() == "E164":
        if isinstance(value, list):
            return [norm_mod.normalize_phone(v) or v for v in value]
        return norm_mod.normalize_phone(value) or value
    if normalize == "canonical":
        if isinstance(value, list):
            return [norm_mod.normalize_skill(v) or v for v in value]
        return norm_mod.normalize_skill(value) or value
    return value


class ProjectionError(Exception):
    pass


def project_profile(profile: dict, config: dict = None) -> dict:
    """Apply a runtime config to one canonical profile. If config is None,
    returns the default canonical shape (full schema)."""
    if not config:
        return dict(profile)

    on_missing = config.get("on_missing", "null")
    include_confidence = config.get("include_confidence", True)
    include_provenance = config.get("include_provenance", True)

    out = {}
    for field_cfg in config.get("fields", []):
        target_path = field_cfg["path"]
        source_path = field_cfg.get("from", target_path)
        required = field_cfg.get("required", False)
        normalize = field_cfg.get("normalize")

        value = _get_path(profile, source_path)
        value = _apply_normalize(value, normalize)

        if value is None or value == [] or value == "":
            if required and on_missing == "error":
                raise ProjectionError(
                    f"Required field '{target_path}' (from '{source_path}') is missing "
                    f"for candidate_id={profile.get('candidate_id')}"
                )
            if on_missing == "omit":
                continue
            value = None  # default: "null" policy

        # support dotted target paths by nesting dicts (e.g. "contact.email")
        parts = target_path.split(".")
        cursor = out
        for p in parts[:-1]:
            cursor = cursor.setdefault(p, {})
        cursor[parts[-1]] = value

    if include_confidence:
        out.setdefault("overall_confidence", profile.get("overall_confidence"))
    else:
        out.pop("overall_confidence", None)

    if include_provenance:
        out.setdefault("provenance", profile.get("provenance"))
    else:
        out.pop("provenance", None)

    out.setdefault("candidate_id", profile.get("candidate_id"))
    return out
