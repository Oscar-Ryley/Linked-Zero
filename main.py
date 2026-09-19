import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from services.linkedin_scraper import scrape_linkedin_profile

load_dotenv(override=True)

GPTZERO_URL = "https://api.gptzero.me/v2/predict/text"
BACKBOARD_URL = "https://app.backboard.io/api/threads/messages"
BACKBOARD_LLM_PROVIDER = os.getenv("BACKBOARD_LLM_PROVIDER", "google")
BACKBOARD_MODEL_NAME = os.getenv("BACKBOARD_MODEL_NAME", "gemini-2.5-flash")
REPORT_FILE = Path("analysis-cache.json")
BADGE_APP_FILE = Path("badge-app/main.lua")
OSCAR_URL = "https://www.linkedin.com/in/oscar-ryley/"


class BackboardBillingError(RuntimeError):
    """Raised when Backboard cannot run chat because the account lacks credits."""


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
    username = parsed.path.rstrip("/").removeprefix("/in/")
    return f"https://www.linkedin.com/in/{username}/"


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
        posts = scrape_linkedin_profile(profile_url)["posts"]
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
        "classification": document.get("class") or document.get("predicted_class"),
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
        json={
            "content": prompt,
            "llm_provider": BACKBOARD_LLM_PROVIDER,
            "model_name": BACKBOARD_MODEL_NAME,
            "stream": False,
        },
        timeout=90,
    )
    if not response.ok:
        raise _request_error(response, "Backboard")
    result = response.json()
    content = result.get("content", "")
    lowered = content.casefold()
    if any(marker in lowered for marker in ("add credits", "billing page", "free credit is reserved")):
        raise BackboardBillingError(
            "Backboard cannot run chat with this account's current credits. "
            "Add chat credits or enable a paid Backboard plan, then rerun; "
            "the Apify scrape and GPTZero results were not saved as a complete report."
        )
    if not content.strip():
        raise RuntimeError("Backboard returned an empty investigation report")
    return content


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
            candidate = (
                row.get("LinkedIn link")
                or row.get("linkedin_url")
                or row.get("profile_url")
                or row.get("LinkedIn")
                or row.get("linkedin")
            )
        if candidate:
            if not str(candidate).startswith(("http://", "https://")):
                candidate = f"https://www.linkedin.com/in/{str(candidate).strip('/')}/"
            urls.append(_validate_linkedin_url(candidate))
    return list(dict.fromkeys(urls))


def load_badge_contact_records(path: str) -> list[dict[str, str]]:
    file_path = Path(path)
    if file_path.suffix.lower() != ".csv":
        raise ValueError("--contacts-file must be the Hack the North CSV export")
    with file_path.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    records = []
    for row in rows:
        candidate = row.get("LinkedIn link") or row.get("LinkedIn")
        if not candidate:
            continue
        if not str(candidate).startswith(("http://", "https://")):
            candidate = f"https://www.linkedin.com/in/{str(candidate).strip('/')}/"
        records.append({
            "name": row.get("Name") or candidate,
            "profile_url": _validate_linkedin_url(candidate),
        })
    return records


def _load_report_cache() -> dict[str, dict[str, Any]]:
    if not REPORT_FILE.exists():
        return {}
    data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    reports = data.get("reports", data) if isinstance(data, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}
    for key, report in reports.items():
        if not isinstance(report, dict):
            continue
        posts = report.get("posts", [])
        if any("A realistic mock post from" in str(post.get("text", "")) for post in posts):
            continue
        canonical = _validate_linkedin_url(str(report.get("profile_url") or key))
        for post in posts:
            if not post.get("classification"):
                post["classification"] = (post.get("gptzero") or {}).get("predicted_class")
        report["profile_url"] = canonical
        normalized[canonical] = report
    return normalized


def _save_report_cache(reports: dict[str, dict[str, Any]]) -> None:
    REPORT_FILE.write_text(
        json.dumps({"version": 1, "reports": reports}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _lua_value(value: Any) -> str:
    if isinstance(value, str):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return '"' + escaped + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nil"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "{" + ",".join(_lua_value(item) for item in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(f"{key}={_lua_value(item)}" for key, item in value.items()) + "}"
    raise TypeError(f"Cannot encode {type(value).__name__} as Lua")


def _badge_clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


def _badge_profile(name: str, profile_url: str, report: dict[str, Any]) -> dict[str, Any]:
    posts = report.get("posts", [])
    probabilities = [post.get("ai_probability") or 0.0 for post in posts]
    classes = [post.get("classification") or "unknown" for post in posts]
    classification = max(set(classes), key=classes.count) if classes else "unknown"
    return {
        "name": name,
        "linkedin": profile_url.removeprefix("https://www.").removeprefix("http://www."),
        "posts": len(posts),
        "average": round(sum(probabilities) / len(probabilities), 4) if probabilities else 0.0,
        "classification": classification,
        "posts_data": [
            {
                "text": _badge_clip(post.get("text"), 100),
                "probability": post.get("ai_probability") or 0.0,
                "class": post.get("classification") or "unknown",
                "report": _badge_clip(post.get("backboard_report"), 360),
            }
            for post in posts
        ],
    }


def _update_badge_app(records: list[dict[str, str]], reports: dict[str, dict[str, Any]]) -> None:
    ordered = [{"name": "Oscar Ryley", "profile_url": OSCAR_URL}]
    ordered.extend(record for record in records if record["profile_url"].rstrip("/") != OSCAR_URL.rstrip("/"))
    profiles = [_badge_profile(record["name"], record["profile_url"], reports[record["profile_url"]]) for record in ordered if record["profile_url"] in reports]
    source = BADGE_APP_FILE.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = source.find("local profiles = {")
    mode_start = source.find("local mode", start)
    if start < 0 or mode_start < 0:
        raise RuntimeError(f"Could not find the profiles table in {BADGE_APP_FILE}")
    BADGE_APP_FILE.write_text(source[:start] + "local profiles = " + _lua_value(profiles) + "\n\n" + source[mode_start:], encoding="utf-8")


def analyze_profile(profile_url: str, posts_file: str | None = None) -> dict[str, Any]:
    results = []
    profile_details = None
    if not posts_file:
        scraped = scrape_linkedin_profile(profile_url)
        profile_details = scraped["profile"]
        posts = scraped["posts"]
    else:
        posts = fetch_last_three_posts(profile_url, posts_file)
    for post in posts:
        detection = analyze_text_for_slop(post["text"])
        probability = detection["ai_probability"] or 0.0
        detection["backboard_report"] = investigate_with_backboard(post["text"], probability)
        results.append({**post, **detection})
    report = {"profile_url": profile_url, "posts_analyzed": len(results), "posts": results}
    if profile_details is not None:
        report["profile"] = profile_details
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the last three LinkedIn posts for AI slop.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--profile-url", help="LinkedIn /in/ profile URL")
    source.add_argument("--contacts-file", help="Badge contact export in JSON or CSV format")
    parser.add_argument("--posts-file", help="Local JSON posts fixture/export for one profile")
    parser.add_argument("--output-file", help="Write the final JSON report to this file")
    args = parser.parse_args()

    cache = _load_report_cache()
    if args.profile_url:
        records = [{"name": "Oscar Ryley", "profile_url": _validate_linkedin_url(args.profile_url)}]
    else:
        records = load_badge_contact_records(args.contacts_file)
        if not any(record["profile_url"].rstrip("/") == OSCAR_URL.rstrip("/") for record in records):
            records.insert(0, {"name": "Oscar Ryley", "profile_url": OSCAR_URL})
    if not records:
        raise ValueError("No LinkedIn profile URLs found in the contacts file")

    reports = []
    for record in records:
        profile_url = record["profile_url"]
        if profile_url not in cache:
            cache[profile_url] = analyze_profile(profile_url, args.posts_file if args.profile_url else None)
        reports.append(cache[profile_url])

    _save_report_cache(cache)
    _update_badge_app(records, cache)
    report = reports[0] if args.profile_url else {"contacts": reports}
    formatted = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output_file:
        Path(args.output_file).write_text(formatted + "\n", encoding="utf-8")
        print(f"Report written to {args.output_file}")
    else:
        print(formatted)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, requests.RequestException) as error:
        raise SystemExit(f"Error: {error}")