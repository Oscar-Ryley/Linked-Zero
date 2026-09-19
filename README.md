# HackTheNorth2026

**Challenges:** GPTZero, Backboard.io, Best use of Badge

## LinkedIn Slop Analyzer

This CLI accepts a LinkedIn profile URL, fetches up to its three newest posts through
Proxycurl, scores each post with GPTZero, and asks Backboard for a cautious explanation
of the result. It also accepts a JSON or CSV export of badge contacts. The public badge
site currently documents local badge-to-badge contact exchange, not a contacts API, so
the export file is the integration boundary for the hardware prototype.

Install dependencies and configure `.env`:

```text
GPTZERO_API_KEY=...
BACKBOARD_API_KEY=...
PROXYCURL_API_KEY=...
```

Analyze one profile:

```bash
python main.py --profile-url https://www.linkedin.com/in/example
```

For local development, avoid a LinkedIn provider request with a posts fixture:

```bash
python main.py --profile-url https://www.linkedin.com/in/example --posts-file posts.json
```

Analyze badge contacts from either format:

```bash
python main.py --contacts-file badge-contacts.json
python main.py --contacts-file badge-contacts.csv
```

JSON contacts can be an array of `{ "linkedin_url": "..." }` objects or an object
with a `contacts` array. CSV files should include a `linkedin_url` column. GPTZero is
an indicator, not proof that a person used AI, and the output should be treated as a
review aid rather than a definitive judgment.

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

