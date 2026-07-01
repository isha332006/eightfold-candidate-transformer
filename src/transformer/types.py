"""Shared types and constants used across the pipeline."""
from dataclasses import dataclass, field
from typing import Any, List, Optional


# --- Source reliability weights -------------------------------------------------
# Higher weight = more authoritative when two sources disagree on a scalar field.
# These are deliberately explicit (not hidden in code) so they can be defended/tuned.
SOURCE_WEIGHTS = {
    "ats_json": 0.90,       # structured, owned by Eightfold's customer ATS
    "recruiter_csv": 0.85,  # structured, human-entered by recruiter
    "resume": 0.80,         # candidate-authored, usually accurate for exp/edu
    "linkedin": 0.75,       # candidate-curated profile, can be stale
    "github": 0.60,         # useful signal, often incomplete/out of date
    "recruiter_notes": 0.50,  # free text, most error-prone
}

SOURCE_GROUP = {
    "ats_json": "structured",
    "recruiter_csv": "structured",
    "github": "unstructured",
    "linkedin": "unstructured",
    "resume": "unstructured",
    "recruiter_notes": "unstructured",
}


@dataclass
class FieldValue:
    """A single observation of a field's value, tagged with where it came from."""
    value: Any
    source: str          # one of SOURCE_WEIGHTS keys
    method: str          # e.g. "csv_column:phone", "regex:email", "github_api:bio"
    raw: Optional[str] = None  # original, pre-normalization string (for audit)


@dataclass
class RawRecord:
    """Everything extracted from ONE source about ONE person, before merging."""
    source: str
    fields: dict = field(default_factory=dict)  # field_name -> list[FieldValue]

    def add(self, field_name: str, value: Any, method: str, raw: Optional[str] = None):
        if value is None or value == "" or value == []:
            return
        self.fields.setdefault(field_name, []).append(
            FieldValue(value=value, source=self.source, method=method, raw=raw)
        )


# Canonical skill name map: lowercase alias -> canonical display name
SKILL_SYNONYMS = {
    "js": "JavaScript", "javascript": "JavaScript", "node": "Node.js", "nodejs": "Node.js",
    "node.js": "Node.js", "ts": "TypeScript", "typescript": "TypeScript",
    "py": "Python", "python": "Python", "python3": "Python",
    "react": "React", "reactjs": "React", "react.js": "React",
    "golang": "Go", "go": "Go", "c++": "C++", "cpp": "C++", "c#": "C#", "csharp": "C#",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "mysql": "MySQL",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes", "docker": "Docker",
    "aws": "AWS", "amazon web services": "AWS", "gcp": "GCP",
    "google cloud platform": "GCP", "azure": "Azure",
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "nlp": "NLP", "deep learning": "Deep Learning", "tensorflow": "TensorFlow",
    "pytorch": "PyTorch", "sql": "SQL", "django": "Django", "flask": "Flask",
    "fastapi": "FastAPI", "java": "Java", "rest api": "REST APIs", "rest": "REST APIs",
    "graphql": "GraphQL", "redis": "Redis", "mongodb": "MongoDB", "mongo": "MongoDB",
    "git": "Git", "linux": "Linux", "ci/cd": "CI/CD", "cicd": "CI/CD",
    "css": "CSS", "html": "HTML", "ruby": "Ruby", "rails": "Ruby on Rails",
    "scala": "Scala", "rust": "Rust", "swift": "Swift", "kotlin": "Kotlin",
    "php": "PHP", "c": "C", "shell": "Shell", "bash": "Bash",
}
