"""Cost-bounded LinkedIn profile and post scraping through Apify.

The default actor is configurable because Apify actor input schemas can differ.
The adapter sends both common post-limit keys and keeps the normalization layer
permissive across actor output versions.
"""

from __future__ import annotations

import os
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(override=True)

MAX_POSTS = 3


def _truthy(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"1", "true", "yes", "on"}


def normalize_linkedin_url(value: str) -> str:
    """Normalize a LinkedIn /in/ URL or username to a canonical URL."""
    candidate = value.strip()
    if not candidate:
        raise ValueError("LinkedIn URL or username cannot be empty")

    if "://" not in candidate:
        if candidate.startswith(("linkedin.com/", "www.linkedin.com/")):
            candidate = "https://" + candidate
        else:
            candidate = f"https://www.linkedin.com/in/{candidate.strip('/')}"

    parsed = urlparse(candidate)
    if parsed.netloc.casefold() not in {"linkedin.com", "www.linkedin.com"}:
        raise ValueError(f"Expected a LinkedIn profile URL or username, got: {value}")
    path = parsed.path.rstrip("/")
    if not re.fullmatch(r"/in/[A-Za-z0-9_%~-]+", path):
        raise ValueError(f"Expected a LinkedIn /in/ profile URL, got: {value}")
    username = path.removeprefix("/in/")
    return f"https://www.linkedin.com/in/{username}/"


def _first(item: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None and value != "":
            return value
    return default


def _as_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(_first(value, "text", "content", "value", default=""))
    if isinstance(value, list):
        return " ".join(_as_text(part) for part in value)
    return str(value or "").strip()


def _as_count(value: Any) -> int:
    if isinstance(value, int):
        return max(0, value)
    match = re.search(r"\d[\d,]*", str(value or ""))
    return int(match.group(0).replace(",", "")) if match else 0


def _as_iso_date(value: Any) -> str:
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    return str(value or "")


def _mock_result(profile_url: str) -> dict[str, Any]:
    username = profile_url.rstrip("/").rsplit("/", 1)[-1]
    return {
        "profile": {
            "name": "Mock LinkedIn Profile",
            "headline": "Demo profile for local development",
            "about": "This fixture is returned without contacting Apify.",
            "profileUrl": profile_url,
            "avatarUrl": "https://images.example.test/avatar.png",
        },
        "posts": [
            {
                "text": f"A realistic mock post from {username}: shipping useful work beats shipping noise.",
                "publishedAt": "2026-09-18T12:00:00Z",
                "postUrl": f"{profile_url}#mock-post-1",
                "likesCount": 42,
                "commentsCount": 7,
            },
            {
                "text": "We learned more from one customer conversation than from a week of dashboards.",
                "publishedAt": "2026-09-15T12:00:00Z",
                "postUrl": f"{profile_url}#mock-post-2",
                "likesCount": 28,
                "commentsCount": 3,
            },
            {
                "text": "Small teams move faster when the next decision is visible to everyone.",
                "publishedAt": "2026-09-10T12:00:00Z",
                "postUrl": f"{profile_url}#mock-post-3",
                "likesCount": 19,
                "commentsCount": 2,
            },
        ],
    }


def _replace_placeholders(value: Any, profile_url: str) -> Any:
    if isinstance(value, str):
        return value.replace("{profile_url}", profile_url).replace("{max_posts}", str(MAX_POSTS))
    if isinstance(value, list):
        return [_replace_placeholders(item, profile_url) for item in value]
    if isinstance(value, dict):
        return {key: _replace_placeholders(item, profile_url) for key, item in value.items()}
    return value


def _actor_input(profile_url: str, env_name: str, default_input: dict[str, Any]) -> dict[str, Any]:
    raw_input = (os.getenv(env_name) or "").strip()
    if raw_input:
        try:
            actor_input = json.loads(raw_input)
        except json.JSONDecodeError as error:
            raise RuntimeError("APIFY_ACTOR_INPUT_JSON must be valid JSON copied from the actor input schema") from error
        if not isinstance(actor_input, dict):
            raise RuntimeError("APIFY_ACTOR_INPUT_JSON must be a JSON object")
        actor_input = _replace_placeholders(actor_input, profile_url)
    else:
        actor_input = default_input

    # Common schemas supported by LinkedIn actors. Unknown actor-specific limit
    # fields must be set to 3 in APIFY_ACTOR_INPUT_JSON by the developer.
    for key in ("maxPosts", "max_posts", "limit", "maxItems", "max_items", "postLimit", "post_limit"):
        if key in actor_input:
            actor_input[key] = MAX_POSTS
    return actor_input


def _run_actor(client: Any, actor_id: str, input_env: str, profile_url: str, default_input: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        run = client.actor(actor_id).call(
            run_input=_actor_input(profile_url, input_env, default_input)
        )
    except Exception as error:
        message = str(error)
        if "429" in message or "rate" in message.casefold():
            raise RuntimeError(f"Apify rate limit reached for actor {actor_id!r}") from error
        raise RuntimeError(f"Apify actor {actor_id!r} failed: {message}") from error
    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
    if not dataset_id:
        raise RuntimeError(f"Apify actor {actor_id!r} completed without a default dataset")
    try:
        return list(client.dataset(dataset_id).iterate_items())
    except Exception as error:
        raise RuntimeError(f"Could not read Apify dataset {dataset_id!r}: {error}") from error


def _normalize_items(profile_url: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        raise RuntimeError("Apify returned an empty dataset for the LinkedIn profile")

    profile_item = next((item for item in items if any(key in item for key in ("headline", "about", "fullName", "profileUrl"))), items[0])
    profile = {
        "name": _as_text(_first(profile_item, "name", "fullName", "full_name", default="Unknown")),
        "headline": _as_text(_first(profile_item, "headline", "occupation", "title")),
        "about": _as_text(_first(profile_item, "about", "summary", "bio", "description")),
        "profileUrl": normalize_linkedin_url(str(_first(profile_item, "profileUrl", "profile_url", "url", default=profile_url))),
        "avatarUrl": str(_first(profile_item, "avatarUrl", "avatar_url", "profilePicture", "profile_pic_url")),
    }

    posts = []
    for item in items:
        text = _as_text(_first(item, "text", "postText", "post_text", "content", "description"))
        if not text:
            continue
        posts.append({
            "text": text,
            "publishedAt": _as_iso_date(_first(item, "publishedAt", "published_at", "postedAt", "date")),
            "postUrl": str(_first(item, "postUrl", "post_url", "url")),
            "likesCount": _as_count(_first(item, "likesCount", "likes", "numLikes")),
            "commentsCount": _as_count(_first(item, "commentsCount", "comments", "numComments")),
        })

    return {"profile": profile, "posts": posts[:MAX_POSTS]}


def scrape_linkedin_profile(profile_or_username: str) -> dict[str, Any]:
    """Return normalized profile data and at most three recent posts.

    Set MOCK_LINKEDIN_DATA=true for local development. Live mode requires
    APIFY_API_TOKEN and charges the configured Apify actor according to its plan.
    """
    profile_url = normalize_linkedin_url(profile_or_username)
    if _truthy(os.getenv("MOCK_LINKEDIN_DATA")):
        return _mock_result(profile_url)

    token = (os.getenv("APIFY_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            "APIFY_API_TOKEN is missing or empty. Add it to .env before making a live Apify request."
        )

    single_actor_id = (os.getenv("APIFY_LINKEDIN_ACTOR_ID") or "").strip()
    profile_actor_id = (os.getenv("APIFY_PROFILE_ACTOR_ID") or "").strip()
    posts_actor_id = (os.getenv("APIFY_POSTS_ACTOR_ID") or "").strip()
    if not single_actor_id and not (profile_actor_id and posts_actor_id):
        raise RuntimeError(
            "Configure either APIFY_LINKEDIN_ACTOR_ID for one combined Actor, or "
            "both APIFY_PROFILE_ACTOR_ID and APIFY_POSTS_ACTOR_ID for separate "
            "profile and posts Actors."
        )

    try:
        from apify_client import ApifyClient
    except ImportError as error:
        raise RuntimeError(
            "The Apify SDK is not installed. Run 'pip install -r requirements.txt' "
            "before making a live Apify request."
        ) from error

    client = ApifyClient(token)
    if single_actor_id:
        items = _run_actor(
            client,
            single_actor_id,
            "APIFY_ACTOR_INPUT_JSON",
            profile_url,
            {"profileUrls": [profile_url], "maxPosts": MAX_POSTS},
        )
    else:
        profile_items = _run_actor(
            client,
            profile_actor_id,
            "APIFY_PROFILE_ACTOR_INPUT_JSON",
            profile_url,
            {"profileUrls": [profile_url]},
        )
        post_items = _run_actor(
            client,
            posts_actor_id,
            "APIFY_POSTS_ACTOR_INPUT_JSON",
            profile_url,
            {"profileUrls": [profile_url], "maxPosts": MAX_POSTS},
        )
        items = profile_items + post_items
    return _normalize_items(profile_url, items)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Scrape a LinkedIn profile through Apify")
    parser.add_argument("profile", help="LinkedIn /in/ URL or username")
    args = parser.parse_args()
    print(json.dumps(scrape_linkedin_profile(args.profile), indent=2))