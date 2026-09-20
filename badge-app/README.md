https://badge.hackthenorth.com/ide/

# Linked-Zero

This self-contained demo app visualizes four fake LinkedIn profiles with their
average GPTZero probability, then shows each profile summary and all three post
reports. The data is embedded directly in `main.lua` because badge apps cannot
make HTTP requests or read JSON files.

Controls:

- `UP` / `DOWN`: choose a profile
- `A`: open a profile, then cycle overview and post reports
- `LEFT` / `RIGHT`: move between post reports
- `B`: return to the profile list
- `HOME`: exit

LEDs are blue on the profile list, amber on the profile overview, green for a
low-probability post, amber for a mixed signal, and red for a high-probability
post. These colors are signals, not proof of authorship.

## Computer-to-badge sync workflow

The badge cannot read JSON, access LinkedIn, or run a sync callback. The app does
export the badge fields it can access to `appdata/contacts.csv` when it opens.
Run this workflow on the computer instead. It hard-codes the resulting reports
into `badge-app/main.lua`, which is then pushed back to the badge.

1. Connect with someone using the badge's normal Connect flow.
2. Open Linked-Zero once. It snapshots the current badge contacts.
3. Plug the badge into the laptop, connect in the Badge IDE, and run this in
   the IDE console:

```text
cat /littlefs/appdata/gpt-linkedin/contacts.csv
```

Copy that CSV output into `badge-contacts.csv` on the laptop.
4. Run URL resolution without using GPTZero or Backboard:

```bash
python sync_badge_app.py --contacts-file badge-contacts.csv --resolve-only
```

The resolver uses `LinkedIn link` first, then `LinkedIn`, then an exact-name
public search constrained by the email domain. Ambiguous results are reported
instead of guessed. Supply a verified mapping with `--mapping-file` when needed.
5. Once every profile has a verified URL and local post data is available, run from the repository root:

```bash
python sync_badge_app.py --contacts-file hack-the-north-contacts-2026-09-19.csv --cache-file analysis-cache.json --posts-file posts.json
```

Your profile, `https://www.linkedin.com/in/oscar-ryley/`, is always placed first.
The second JSON file, `analysis-cache.json`, is keyed by LinkedIn URL. If a URL
already has a saved report, the workflow reuses it and skips both GPTZero and
Backboard. New URLs are analyzed and their complete reports are added to the
cache. Keep this file private because it contains copied post text and reports.

For offline testing, use the existing local posts fixture:

```bash
python sync_badge_app.py --contacts-file badge-contacts.example.json --mapping-file linkedin-map.example.csv --posts-file posts.json
```

The command reads each profile's latest available posts, sends each post to
GPTZero, then sends the post and GPTZero score to Backboard. It replaces the
embedded Lua profile table and reports how many profiles were embedded. Review
the generated app, Push the same `gpt-linkedin` slug in the Badge IDE, then
unplug the badge and open the app. The reports are now readable offline.

### How Backboard is used

GPTZero supplies a probabilistic detection result. Backboard is the second-pass
reviewer: it receives the post text and score, then produces a concise explanation
of generic phrasing, unsupported claims, or other context. Its prompt says that a
detector score is not proof, so the badge shows Backboard as commentary rather than
a definitive accusation. The response is embedded in each post's `report` field
in `main.lua`; the badge does not call Backboard directly.

NinjaPear replaced Proxycurl, but its documented API does not currently expose
LinkedIn profile posts. The public badge API also does not provide an automatic
serial export or LinkedIn URL field, so local post data, the `cat` copy step, and
verified name resolution remain necessary.