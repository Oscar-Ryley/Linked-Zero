import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

GPTZERO_URL = "https://api.gptzero.me/v2/predict/text"
BACKBOARD_URL = "https://app.backboard.io/api/threads/messages"
PROXYCURL_POSTS_URL = "https://nubela.co/proxycurl/api/v2/linkedin/profile/posts"


def _request_error(response: requests.Response, service: str) -> RuntimeError:
    try:
        detail = response.json()
    except ValueError:
        detail = response.text[:500]
    return RuntimeError(f"{service} returned HTTP {response.status_code}: {detail}")


def _validate_linkedin_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc not in {
        "linkedin.com",
        "www.linkedin.com",
    }:
        raise ValueError(f"Not a LinkedIn profile URL: {url}")
    if not parsed.path.rstrip("/").startswith("/in/"):
        raise ValueError(f"Expected a LinkedIn /in/ profile URL: {url}")
    return url


def _normalise_post(post: dict[str, Any]) -> dict[str, Any]:
    text = post.get("text") or post.get("post_content") or post.get("content") or ""
    return {
        "text": str(text).strip(),
        "url": post.get("url") or post.get("post_url"),
        "published_at": post.get("published_at") or post.get("posted_date"),
    }


def load_posts_file(path: str) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)
    posts = data.get("posts", data) if isinstance(data, dict) else data
    if not isinstance(posts, list):
        raise ValueError("Posts file must contain a JSON list or an object with a 'posts' list")
    return [_normalise_post(post) for post in posts if isinstance(post, dict)]


def fetch_last_three_posts(profile_url: str, posts_file: str | None = None) -> list[dict[str, Any]]:
    profile_url = _validate_linkedin_url(profile_url)
    if posts_file:
        posts = load_posts_file(posts_file)
    else:
        api_key = os.getenv("PROXYCURL_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Set PROXYCURL_API_KEY to fetch LinkedIn posts, or pass --posts-file for a local export"
            )
        response = requests.get(
            PROXYCURL_POSTS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            params={"linkedin_profile_url": profile_url, "page_size": 3, "sort_by": "CREATED"},
            timeout=60,
        )
        if not response.ok:
            raise _request_error(response, "LinkedIn post provider")
        payload = response.json()
        posts = [_normalise_post(post) for post in payload.get("results", payload)]
    posts = [post for post in posts if post["text"]]
    return posts[:3]


def analyze_text_for_slop(text: str) -> dict[str, Any]:
    api_key = os.getenv("GPTZERO_API_KEY")
    if not api_key:
        raise RuntimeError("Set GPTZERO_API_KEY before running an analysis")
    response = requests.post(
        GPTZERO_URL,
        headers={"Accept": "application/json", "x-api-key": api_key},
        json={"document": text},
        timeout=60,
    )
    if not response.ok:
        raise _request_error(response, "GPTZero")
    document = response.json()["documents"][0]
    return {
        "ai_probability": document.get("completely_generated_prob"),
        "classification": document.get("class"),
        "gptzero": document,
    }


def investigate_with_backboard(text: str, ai_probability: float) -> str:
    api_key = os.getenv("BACKBOARD_API_KEY")
    if not api_key:
        raise RuntimeError("Set BACKBOARD_API_KEY before running an analysis")
    prompt = (
        "Review this LinkedIn post as a writing-quality investigator. GPTZero estimated "
        f"{ai_probability:.1%} probability of full AI generation. Identify concrete signs "
        "of generic AI writing, unsupported factual claims, or manipulation. Be cautious: "
        "a detector score is not proof. Give a concise explanation.\n\nPost:\n" + text
    )
    response = requests.post(
        BACKBOARD_URL,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json={"content": prompt, "stream": False},
        timeout=90,
    )
    if not response.ok:
        raise _request_error(response, "Backboard")
    return response.json().get("content", "")


def load_badge_contacts(path: str) -> list[str]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        with file_path.open(newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
    else:
        with file_path.open(encoding="utf-8") as file:
            data = json.load(file)
        rows = data.get("contacts", data) if isinstance(data, dict) else data
    urls = []
    for row in rows:
        if isinstance(row, str):
            candidate = row
        else:
            candidate = row.get("linkedin_url") or row.get("linkedin") or row.get("profile_url")
        if candidate:
            urls.append(_validate_linkedin_url(candidate))
    return list(dict.fromkeys(urls))


def analyze_profile(profile_url: str, posts_file: str | None = None) -> dict[str, Any]:
    results = []
    for post in fetch_last_three_posts(profile_url, posts_file):
        detection = analyze_text_for_slop(post["text"])
        probability = detection["ai_probability"] or 0.0
        detection["backboard_report"] = investigate_with_backboard(post["text"], probability)
        results.append({**post, **detection})
    return {"profile_url": profile_url, "posts_analyzed": len(results), "posts": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the last three LinkedIn posts for AI slop.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--profile-url", help="LinkedIn /in/ profile URL")
    source.add_argument("--contacts-file", help="Badge contact export in JSON or CSV format")
    parser.add_argument("--posts-file", help="Local JSON posts fixture/export for one profile")
    args = parser.parse_args()

    profiles = [args.profile_url] if args.profile_url else load_badge_contacts(args.contacts_file)
    if not profiles:
        raise ValueError("No LinkedIn profile URLs found in the contacts file")
    reports = [analyze_profile(profile, args.posts_file if args.profile_url else None) for profile in profiles]
    print(json.dumps(reports[0] if args.profile_url else {"contacts": reports}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, requests.RequestException) as error:
        raise SystemExit(f"Error: {error}")