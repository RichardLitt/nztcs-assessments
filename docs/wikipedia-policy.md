# Wikimedia API policy compliance

Use this page to check whether the bot follows Wikimedia's rules. Each rule
below quotes its source (checked 2026-11-03) and says how the code meets it.
Everything Wikipedia-facing lives in
[`src/nztcs_wiki_bot/wiki_client.py`](../src/nztcs_wiki_bot/wiki_client.py).

## 1. User-Agent

Source: [Wikimedia User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy)

> Scripts should use an informative User-Agent string with contact information,
> or they may be blocked without notice.

> If you operate a bot, please send a User-Agent header identifying the bot in a
> way that isn't going to be confused with many other bots, and supplying some
> way of contacting you, the operator […]

> The generic format is `<client name>/<version> (<contact information>) <library/framework name>/<version>`

> If you run an automated agent, please consider following the Internet-wide
> convention of including the string "bot" in the User-Agent string […]

**How we comply.** Every request sends:

```
nztcs-wiki-bot/0.1.0 (https://github.com/RichardLitt/nztcs-assessments; <operator contact>) python-requests/2.x
```

- The client name contains "bot" and is specific to this project.
- The contact is the person running the tool, as the policy asks, not the
  project's author. It comes from `--contact` or `$NZTCS_BOT_CONTACT`. There is
  deliberately no default: `WikiClient` raises `MissingContactError` and the CLI
  exits with status 2 if none is set.
- The string is built in one place (`build_user_agent()`), and a unit test
  checks its shape.

## 2. API etiquette

Source: [API:Etiquette](https://www.mediawiki.org/wiki/API:Etiquette)

| Rule (quoted) | Implementation |
|---|---|
| "Make your requests in series rather than in parallel, by waiting for one request to finish before sending a new request." | Single-threaded, with one request in flight at a time. A self-imposed floor of 1 second between requests (`MIN_INTERVAL`) adds margin. |
| "ask for multiple items in one request by: Using the pipe character … `titles=PageA\|PageB\|PageC`" | Title resolution batches up to 50 titles per request (`BATCH_SIZE`). A test checks that 120 titles take 3 requests. |
| "Use GZip compression when making API calls by setting `Accept-Encoding: gzip`" | `requests` sends this by default. We don't override it. |
| "If your task is not interactive … you should use the `maxlag` parameter." | Every request sends `maxlag=5`. On a `maxlag` error, or a 503 with `Retry-After`, the client waits `Retry-After` seconds (or 1, 2, 4… if absent) and retries, up to 3 times, then raises `MaxLagExhausted`. |
| "All new API users should use JSON." | `format=json&formatversion=2`. |

## 3. Caching

Not a quoted rule, but the obvious way to avoid re-asking for the same data.
Title resolutions and page wikitext are cached on disk under `cache/`, as
gzipped JSON files named `<kind>-<sha256 of key>.json.gz`. Re-runs over the same
CSV make no requests at all. Delete `cache/` to refetch.

## 4. Read-only scope

The bot **never** edits, logs in, or fetches tokens:

- `WikiClient._request()` raises `ValueError` for any `action` other than
  `query`, before anything is sent.
- `tests/integration/test_no_write_endpoints.py` runs the full CLI against a
  mocked Wikipedia and checks every request: it must be a `GET`, carry
  `action=query`, have no body, and include no `token` or password parameters.
  It also checks that the client refuses each of 15 write actions (`edit`,
  `login`, `createaccount`, `rollback`, …) without sending anything.

Because the tool makes no edits, Wikipedia's
[bot approval process](https://en.wikipedia.org/wiki/Wikipedia:Bots/Requests_for_approval)
doesn't apply to it. The edits you paste by hand are yours, and normal editing
policy applies. See the note on bot-like editing in
[reviewing-output.md](reviewing-output.md#doing-a-lot-of-these).

## 5. The NZTCS API

`nztcs-wiki-bot fetch` talks to `https://nztcs.org.nz/rest/assessmentSearch`,
not Wikipedia. It sends an identifying User-Agent (project URL, no operator
contact needed), uses a 60-second timeout, and makes one request per 1000
assessments.
