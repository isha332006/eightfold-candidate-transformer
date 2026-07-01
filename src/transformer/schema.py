"""Canonical default output schema + validation step."""

DEFAULT_SCHEMA = {
    "type": "object",
    "required": ["candidate_id", "full_name", "emails", "phones", "location",
                  "links", "headline", "years_experience", "skills",
                  "experience", "education", "provenance", "overall_confidence"],
    "properties": {
        "candidate_id": {"type": "string"},
        "full_name": {"type": ["string", "null"]},
        "emails": {"type": "array", "items": {"type": "string"}},
        "phones": {"type": "array", "items": {"type": "string"}},
        "location": {
            "type": "object",
            "properties": {
                "city": {"type": ["string", "null"]},
                "region": {"type": ["string", "null"]},
                "country": {"type": ["string", "null"]},
            },
        },
        "links": {
            "type": "object",
            "properties": {
                "linkedin": {"type": ["string", "null"]},
                "github": {"type": ["string", "null"]},
                "portfolio": {"type": ["string", "null"]},
                "other": {"type": "array"},
            },
        },
        "headline": {"type": ["string", "null"]},
        "years_experience": {"type": ["number", "null"]},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "confidence": {"type": "number"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "experience": {"type": "array"},
        "education": {"type": "array"},
        "provenance": {"type": "array"},
        "overall_confidence": {"type": "number"},
    },
}


def validate_profile(profile: dict, schema: dict = None) -> list:
    """Returns a list of validation error strings (empty = valid). We use
    jsonschema if available, but keep this independent of *which* schema is
    passed so it also validates config-projected output."""
    import jsonschema
    schema = schema or DEFAULT_SCHEMA
    validator = jsonschema.Draft7Validator(schema)
    return [e.message for e in validator.iter_errors(profile)]
