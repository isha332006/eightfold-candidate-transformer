"""Extract from a public GitHub profile URL via the REST API.
No auth required for public, low-volume use (rate-limited by GitHub).
"""
import re
import urllib.request
import json

from ..types import RawRecord

API_BASE = "https://api.github.com"


def _get_json(url):
    import time
    req = urllib.request.Request(url, headers={
        "User-Agent": "eightfold-candidate-transformer",
        "Accept": "application/vnd.github+json",
    })
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            time.sleep(0.6 * (attempt + 1))
    raise last_err


def extract_github(url: str) -> list:
    m = re.search(r"github\.com/([A-Za-z0-9\-]+)", url)
    if not m:
        return []
    username = m.group(1)
    try:
        user = _get_json(f"{API_BASE}/users/{username}")
        if "message" in user and "login" not in user:
            return []  # not found / rate-limited -> degrade, don't crash
        repos = _get_json(f"{API_BASE}/users/{username}/repos?per_page=100")
    except Exception:
        return []  # network/API failure: treat as missing source

    rec = RawRecord(source="github")
    rec.add("full_name", user.get("name"), "github_api:name")
    rec.add("headline", user.get("bio"), "github_api:bio")
    rec.add("github_link", user.get("html_url"), "github_api:html_url")
    if user.get("blog"):
        rec.add("portfolio_link", user.get("blog"), "github_api:blog")
    if user.get("company"):
        rec.add("current_company", user.get("company"), "github_api:company")
    if user.get("location"):
        rec.add("location_raw", user.get("location"), "github_api:location")
    if user.get("email"):
        rec.add("email_raw", user.get("email"), "github_api:email")

    languages = set()
    if isinstance(repos, list):
        for r in repos:
            if isinstance(r, dict) and r.get("language"):
                languages.add(r["language"])
    for lang in languages:
        rec.add("skills_raw", lang, "github_api:repo_language")

    return [rec] if rec.fields else []
