# HackTheNorth2026

**Challenges:** GPTZero, Backboard.io, Best use of Badge

## LinkedIn Slop Analyzer

This CLI accepts a LinkedIn profile URL, uses Apify to fetch the profile and at most
three recent posts, scores each post with GPTZero, and asks Backboard for a cautious
explanation of the result. It also accepts a CSV export of badge contacts. The public
badge site currently documents local badge-to-badge contact exchange, not a contacts
API, so the export file is the integration boundary for the hardware prototype.

Install dependencies and configure `.env`:

```text
APIFY_API_TOKEN=...
MOCK_LINKEDIN_DATA=false
APIFY_LINKEDIN_ACTOR_ID=...
APIFY_ACTOR_INPUT_JSON={"profileUrls":["{profile_url}"],"maxPosts":3}
GPTZERO_API_KEY=...
BACKBOARD_API_KEY=...
```

### Configure Apify once

1. Open the Apify Console and choose a LinkedIn profile/post Actor from the Store.
2. Open that Actor's **Input** tab and copy its input JSON schema/example.
3. Put the Actor ID in `APIFY_LINKEDIN_ACTOR_ID`.
4. Put the matching input JSON in `APIFY_ACTOR_INPUT_JSON`. Replace the profile
	URL value with `{profile_url}` and set the actor's post limit to `3`.
5. Set `MOCK_LINKEDIN_DATA=true` while developing UI or downstream behavior;
	this bypasses Apify entirely.

The code does not assume one Actor's schema. If the selected Actor uses a limit
field not recognized by the adapter, set that field to `3` in the JSON yourself.
The Actor must return a default dataset containing profile and/or post records;
the adapter normalizes common field names into the app's schema.

The Apify Store screenshot supports a two-Actor setup: configure the profile
Actor (`harvestapi/linkedin-profile-scraper`) with `APIFY_PROFILE_ACTOR_INPUT_JSON`,
and the posts Actor (`harvestapi/linkedin-profile-posts`) with
`APIFY_POSTS_ACTOR_INPUT_JSON`. The service runs both and merges their datasets.
Copy the exact input examples from each Actor's Input tab because schemas can
change; keep the posts limit at `3`.

Analyze one profile through Apify:

```bash
python main.py --profile-url https://www.linkedin.com/in/example
```

For zero-cost local development, set `MOCK_LINKEDIN_DATA=true`. This bypasses
Apify and returns a realistic normalized fixture. `APIFY_API_TOKEN` is required
for live mode; the actor input caps post retrieval at three.

For local development, avoid a LinkedIn provider request with a posts fixture:

```bash
python main.py --profile-url https://www.linkedin.com/in/example --posts-file posts.json
```

Analyze a Badge Connect CSV export:

```bash
python sync_badge_app.py --contacts-file hack-the-north-contacts-2026-09-19.csv --resolve-only
python sync_badge_app.py --contacts-file hack-the-north-contacts-2026-09-19.csv --cache-file analysis-cache.json
```

The sync workflow uses `LinkedIn link`, then `LinkedIn`, then cautious exact-name
resolution. Your profile, Oscar Ryley, is always placed first. Reports are stored
in `analysis-cache.json`; profiles already present there skip GPTZero and Backboard
on later runs. GPTZero is an indicator, not proof that a person used AI, and the
output should be treated as a review aid rather than a definitive judgment.

## Reference

This project is informed by the Financial Times article [AI is creating ghostwriting
jobs on LinkedIn](https://www.ft.com/content/7a5e15e4-799a-4476-ba9f-018b1d82c76f?syn-25a6b1a6=1),
published September 16, 2026, by Georgina Quach. The article describes the growth of
generic, AI-assisted LinkedIn posts and the parallel demand for human ghostwriters
who interview founders and add personal perspective.

In the interview, Bernie Hogan of the Oxford Internet Institute makes an important
distinction for this project: hiring a ghostwriter can be rational, and the underlying
message can still be sincere, but readers may still experience the post as inauthentic
when they cannot tell who actually wrote it. That means this tool should report signals
and context, not label a person as dishonest. GPTZero scores and Backboard commentary
are review aids; they cannot distinguish AI generation from human ghostwriting or prove
who authored a post.

