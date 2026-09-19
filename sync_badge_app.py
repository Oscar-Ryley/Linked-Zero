import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import requests

from main import analyze_profile


APP_FILE = Path("badge-app/main.lua")
DEFAULT_CACHE_FILE = Path("analysis-cache.json")
LINKEDIN_HOSTS = {"linkedin.com", "www.linkedin.com"}
OSCAR_PROFILE = {
    "name": "Oscar Ryley",
    "linkedin_url": "https://www.linkedin.com/in/oscar-ryley/",
    "role": "Owner",
}


def load_rows(path: str) -> list[dict[str, Any]]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        with file_path.open(newline="", encoding="utf-8-sig") as file:
            return [dict(row) for row in csv.DictReader(file)]
    with file_path.open(encoding="utf-8") as file:
        data = json.load(file)
    rows = data.get("contacts", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a list or an object with a contacts list")
    return [row if isinstance(row, dict) else {"name": str(row)} for row in rows]


def normalise_name(name: str) -> str:
    return " ".join(name.casefold().split())


def valid_linkedin_url(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate.startswith(("http://", "https://")):
        candidate = "https://www.linkedin.com/in/" + candidate.strip("/")
    parsed = urlparse(candidate)
    if parsed.netloc.casefold() not in LINKEDIN_HOSTS:
        return None
    if not parsed.path.rstrip("/").startswith("/in/"):
        return None
    return candidate.rstrip("/")


class SearchLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        parsed = urlparse(href)
        if parsed.path == "/l/":
            href = parse_qs(parsed.query).get("uddg", [""])[0]
        href = unquote(href)
        match = re.search(r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9_%~-]+", href)
        if match:
            self.links.append(match.group(0).rstrip("/"))


def search_linkedin_by_name(name: str, email: str | None = None) -> str | None:
    query = f'site:linkedin.com/in "{name}"'
    if email and "@" in email:
        query += f' "{email.rsplit("@", 1)[1]}"'
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "HackTheNorthSlopScanner/1.0"},
        timeout=15,
    )
    response.raise_for_status()
    parser = SearchLinkParser()
    parser.feed(response.text)
    candidates = list(dict.fromkeys(parser.links))
    return candidates[0] if len(candidates) == 1 else None


def load_linkedin_map(path: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in load_rows(path):
        name = row.get("name") or row.get("full_name")
        url = row.get("linkedin_url") or row.get("linkedin") or row.get("profile_url")
        if name and url:
            key = normalise_name(name)
            if key in mapping and mapping[key] != url:
                raise ValueError(f"Duplicate LinkedIn mapping for {name}")
            mapping[key] = url
    return mapping


def lua_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "nil"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "{" + ",".join(lua_value(item) for item in value) + "}"
    if isinstance(value, dict):
        fields = []
        for key, item in value.items():
            fields.append(f"{key}={lua_value(item)}")
        return "{" + ",".join(fields) + "}"
    raise TypeError(f"Cannot encode {type(value).__name__} as Lua")


def to_badge_profile(name: str, profile_url: str, report: dict[str, Any]) -> dict[str, Any]:
    posts = report["posts"]
    probabilities = [post.get("ai_probability") or 0.0 for post in posts]
    average = sum(probabilities) / len(probabilities) if probabilities else 0.0
    classification_counts: dict[str, int] = {}
    for post in posts:
        classification = post.get("classification") or "unknown"
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
    classification = max(classification_counts, key=classification_counts.get) if classification_counts else "unknown"
    return {
        "name": name,
        "linkedin": profile_url.removeprefix("https://www.").removeprefix("http://www."),
        "posts": len(posts),
        "average": round(average, 4),
        "classification": classification,
        "posts_data": [
            {
                "text": post["text"],
                "probability": post.get("ai_probability") or 0.0,
                "class": post.get("classification") or "unknown",
                "report": post.get("backboard_report") or "No Backboard report returned.",
            }
            for post in posts
        ],
    }


def load_analysis_cache(path: str) -> dict[str, dict[str, Any]]:
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    with cache_path.open(encoding="utf-8") as file:
        data = json.load(file)
    reports = data.get("reports", data) if isinstance(data, dict) else data
    if not isinstance(reports, dict):
        raise ValueError(f"{path} must contain an object keyed by LinkedIn URL")
    return reports


def save_analysis_cache(path: str, reports: dict[str, dict[str, Any]]) -> None:
    cache_path = Path(path)
    payload = {"version": 1, "reports": reports}
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(cache_path)


def resolve_contact_url(contact: dict[str, Any], linkedin_map: dict[str, str], allow_search: bool) -> str | None:
    direct = valid_linkedin_url(contact.get("LinkedIn link") or contact.get("linkedin_url"))
    if direct:
        return direct
    handle = valid_linkedin_url(contact.get("LinkedIn") or contact.get("linkedin"))
    if handle:
        return handle
    name = contact.get("Name") or contact.get("name") or contact.get("full_name")
    if not name:
        return None
    mapped = valid_linkedin_url(linkedin_map.get(normalise_name(name)))
    if mapped:
        return mapped
    if allow_search:
        return search_linkedin_by_name(name, contact.get("Email") or contact.get("email"))
    return None


def resolve_contacts(contacts_file: str, mapping_file: str | None, allow_search: bool) -> tuple[list[dict[str, Any]], list[str]]:
    contacts = load_rows(contacts_file)
    linkedin_map = load_linkedin_map(mapping_file) if mapping_file else {}
    resolved = []
    missing = []
    for contact in contacts:
        name = contact.get("Name") or contact.get("name") or contact.get("full_name")
        if not name:
            continue
        profile_url = resolve_contact_url(contact, linkedin_map, allow_search)
        if profile_url:
            resolved.append({"name": name, "linkedin_url": profile_url, "role": contact.get("Role") or contact.get("role")})
        else:
            missing.append(name)
    return resolved, missing


def _embed_profiles(
    resolved: list[dict[str, Any]],
    cache_file: str,
    posts_file: str | None = None,
) -> tuple[int, int]:
    cache = load_analysis_cache(cache_file)
    profiles = []
    cached_count = 0
    for contact in resolved:
        profile_url = valid_linkedin_url(contact["linkedin_url"])
        if not profile_url:
            continue
        if profile_url in cache:
            report = cache[profile_url]
            cached_count += 1
        else:
            report = analyze_profile(profile_url, posts_file)
            cache[profile_url] = report
        profiles.append(to_badge_profile(contact["name"], contact["linkedin_url"], report))
    if not profiles:
        raise ValueError("No mapped contacts found")

    source = APP_FILE.read_text(encoding="utf-8").replace("\r\n", "\n")
    start_marker = "local profiles = {"
    start = source.find(start_marker)
    mode_start = source.find("local mode", start)
    if start < 0 or mode_start < 0:
        raise ValueError(f"Could not find the profiles table in {APP_FILE}")
    table = "local profiles = " + lua_value(profiles)
    APP_FILE.write_text(source[:start] + table + "\n\n" + source[mode_start:], encoding="utf-8")
    save_analysis_cache(cache_file, cache)
    return len(profiles), cached_count


def sync_badge_app(
    contacts_file: str,
    mapping_file: str | None,
    cache_file: str,
    posts_file: str | None = None,
    allow_search: bool = True,
) -> tuple[int, int]:
    resolved, missing = resolve_contacts(contacts_file, mapping_file, allow_search)
    resolved = [OSCAR_PROFILE] + [
        contact for contact in resolved
        if valid_linkedin_url(contact["linkedin_url"]) != valid_linkedin_url(OSCAR_PROFILE["linkedin_url"])
    ]
    if missing:
        raise ValueError("Could not resolve LinkedIn profiles for: " + ", ".join(missing))
    return _embed_profiles(resolved, cache_file, posts_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a Hack the North badge CSV and embed reports in the badge app.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--contacts-file", help="CSV export from my.hackthenorth.com/badge/connect")
    source.add_argument("--profile-url", help="Analyze and embed one LinkedIn profile directly")
    parser.add_argument("--name", default="Oscar Ryley", help="Display name for --profile-url")
    parser.add_argument("--mapping-file", help="Optional verified name-to-LinkedIn mapping in JSON or CSV format")
    parser.add_argument("--cache-file", default=str(DEFAULT_CACHE_FILE), help="JSON report cache; analyzed profiles are skipped on later runs")
    parser.add_argument("--posts-file", help="Use one local posts fixture for every mapped profile")
    parser.add_argument("--resolve-only", action="store_true", help="Resolve URLs and print them without calling analysis APIs")
    parser.add_argument("--no-name-search", action="store_true", help="Do not use public exact-name search for missing LinkedIn links")
    args = parser.parse_args()
    if args.resolve_only:
        if args.profile_url:
            print(json.dumps({"resolved": [{"name": args.name, "linkedin_url": args.profile_url}], "unresolved": []}, indent=2))
            return
        resolved, missing = resolve_contacts(args.contacts_file, args.mapping_file, not args.no_name_search)
        print(json.dumps({"resolved": resolved, "unresolved": missing}, indent=2))
        return
    if args.profile_url:
        count, cached_count = _embed_profiles(
            [{"name": args.name, "linkedin_url": args.profile_url}],
            args.cache_file,
            args.posts_file,
        )
        print(f"Embedded {count} profiles into {APP_FILE}; reused {cached_count} cached reports")
        return
    count, cached_count = sync_badge_app(
        args.contacts_file,
        args.mapping_file,
        args.cache_file,
        args.posts_file,
        not args.no_name_search,
    )
    print(f"Embedded {count} profiles into {APP_FILE}; reused {cached_count} cached reports")


if __name__ == "__main__":
    main()