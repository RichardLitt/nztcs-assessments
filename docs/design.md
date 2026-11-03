# Design

How `nztcs-wiki-bot` is built and why. For usage, see the
[README](../README.md).

## Goal and the main constraint

Most New Zealand species articles on Wikipedia have an infobox but no NZTCS
conservation status. Even [Pūriri moth](https://en.wikipedia.org/wiki/P%C5%ABriri_moth)
has a Speciesbox without `|status=` / `|status_system=NZTCS`.

**Goal:** for each species in an NZTCS report, produce a correct wikitext patch
that adds or updates the NZTCS status in its Wikipedia article's infobox.

**Main constraint:** the tool produces a *review queue*, never live edits. A
person pastes each patch by hand. This has three consequences:

1. There is no need for Wikipedia's bot approval process
   ([WP:BRFA](https://en.wikipedia.org/wiki/Wikipedia:Bots/Requests_for_approval)),
   which only covers automated editing.
2. The cost of a wrong match drops from "a bad edit on Wikipedia" to "a
   reviewer skips an entry".
3. The tool needs no credentials, so it can't affect anyone's account.

Everything below follows from preferring a *missing* patch over a *wrong* one.

## Pipeline

```
CSV ─▶ clean name ─▶ skip? ─▶ map status ─▶ resolve title ─▶ fetch wikitext
                                                                   │
            review/ ◀─ emit ◀─ patch infobox ◀─ verify taxon ◀─ find infobox
```

`pipeline.run()` walks every row, and each row ends in exactly one bucket.

| Step | Module | Failure goes to |
|---|---|---|
| Load rows, strip HTML | `csv_loader` | (error if columns are missing) |
| Extract binomial; skip undescribed (`sp.`) and quoted-genus names | `name_cleaner` | `skipped` |
| Map status title to code | `status_map` | `unmapped` |
| Resolve title, following redirects (batched, before the per-row loop) | `wiki_client` | `no_match` (`missing`) |
| Fetch current wikitext | `wiki_client` | `no_match` (`no-wikitext`) |
| Find a Speciesbox / Subspeciesbox / Infraspeciesbox / Taxobox / Automatic taxobox | `speciesbox` | `ambiguous` (`no-speciesbox`) |
| Check its genus + species (or `taxon`) match the row | `speciesbox` | `ambiguous` (`taxon-mismatch`) |
| Patch; a no-op patch means nothing to do | `speciesbox`, `citation` | `ambiguous` (`already-current`) |
| Success | `output` | `matched` |

## Module boundaries

```
src/nztcs_wiki_bot/
├── cli.py           argparse; dispatches `fetch` or runs the pipeline
├── fetch.py         nztcs.org.nz report → CSV (paginated)
├── csv_loader.py    CSV → Row; strips HTML from cells
├── name_cleaner.py  raw NZTCS name → binomial or skip reason
├── status_map.py    status title → Speciesbox code
├── wiki_client.py   the only module that talks to Wikipedia
├── speciesbox.py    find / verify / patch the infobox (mwparserfromhell)
├── citation.py      {{cite report}} scaffold from reportName / reportYear
├── pipeline.py      orchestration; no I/O of its own
└── output.py        Buckets → review/ files
```

`wiki_client` and `fetch` are the only modules that make network requests.

## Key decisions

### Parse templates, never regex them

Infobox parameters often contain nested templates and refs
(`status_ref = <ref>{{cite …}}</ref>`). `mwparserfromhell`, the parser
pywikibot uses, handles that; regex would mangle it. Parameter values are
normalised (links and italics stripped) only for comparison, never for writing.

### Verify the taxon, not just the title

Redirects are common (`Aenetus virescens` → `Pūriri moth`), and so are genus
pages, disambiguation pages, and synonyms that redirect to a different species.
After resolving a title, the bot requires the infobox's `genus` + `species` (or
its `taxon`) to match the CSV binomial, case-insensitively and ignoring markup.
Anything else goes to `ambiguous`.

### Three patch branches

`speciesbox.patch_status()`:

1. **Existing `status_system = NZTCS`:** update `status` and `status_ref` in
   place (action `update`).
2. **Another system, e.g. IUCN:** leave it alone and add `status2`,
   `status2_system = NZTCS`, `status2_ref` (action `add_secondary`, or
   `update` if an NZTCS secondary already exists).
3. **No status:** insert `status`, `status_system`, `status_ref` after the last
   of `authority` / `taxon` / `species` / `genus` / `name`, following the
   template's documented parameter order (action `insert`).

Patching is idempotent. `status_ref` is only rewritten if it doesn't already
cite this report's ref name, and if the article already defines that ref
elsewhere, the short `<ref name="…" />` form is used.

### Never guess a status code

`status_map.STATUS_CODES` maps each NZTCS `conservationStatusTitle` to the code
Speciesbox expects (e.g. Nationally Critical → `NC`, as on
[Powelliphanta augusta](https://en.wikipedia.org/wiki/Powelliphanta_augusta)).
"Uncommon", the 2025 manual's new name for "Naturally Uncommon", also maps to
`NU`. Titles that aren't conservation statuses ("Not assessed", "Taxonomically
indistinct") go to `unmapped` as `non-status`. A title the table has never seen
goes there as `unknown-status-title`, so a new NZTCS category shows up in the
output instead of becoming a wrong edit.

### Skip names that can't match

Undescribed species (`Archyala sp. A (NZAC04239001; Mataroa)`) have no article.
Scare-quoted genera (`"Acroclita" discariana`) mark an uncertain generic
placement that no article title uses. Both are skipped before any request is
made and listed in `skipped.tsv` with a reason.

### The citation is a scaffold

The CSV has the report name and year but not the authors or series number. The
generated `{{cite report}}` fills in what's known and puts a visible
`<!-- TODO … -->` in `author`, so the reviewer has to complete it before
saving. The ref name (`NZTCS-<taxon>-<year>`) is deterministic, so every species
from one report shares one reference.

## Wikipedia API policy compliance

All Wikipedia traffic goes through `wiki_client.WikiClient`.

**[User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy).**
Every request sends
`nztcs-wiki-bot/<version> (https://github.com/RichardLitt/nztcs-assessments; <contact>) python-requests/<version>`.
The contact belongs to whoever is *running* the tool, so it must be supplied
with `--contact` or `$NZTCS_BOT_CONTACT`, and the client refuses to start
without it. A fork can't accidentally send someone else's email address.

**[API etiquette](https://www.mediawiki.org/wiki/API:Etiquette).**

| Rule | Implementation |
|---|---|
| Make requests in series, not in parallel | One request in flight at a time, at most one per second. |
| Batch titles with `\|` | Title resolution sends up to 50 titles per request. |
| Use `maxlag` for non-interactive tasks | Every request sends `maxlag=5`; on a maxlag error the client waits (honouring `Retry-After`) and retries up to 3 times, then raises `MaxLagExhausted`. |
| Prefer GET for reads; use JSON | GET only, `format=json&formatversion=2`. |

**Caching.** Title resolutions and wikitext are cached as gzipped JSON under
`cache/`, keyed by a hash of the title. Delete the directory to force fresh
fetches.

**Read-only.** `WikiClient._request()` raises on any `action` other than
`query`, so the tool cannot edit, log in, or call any other write endpoint.

## Testing

| Tier | Where | What |
|---|---|---|
| Unit | `tests/unit/` | Each module on its own: name cleaning, status mapping, every patch branch, citation, output format, and the client's User-Agent, batching, maxlag retry and cache. |
| Integration | `tests/integration/` | The pipeline and CLI end to end against an in-memory fake client. |
| Doctests | `src/nztcs_wiki_bot/` | Small examples in docstrings. |
| Live | `tests/live/` | Opt-in (`pytest -m live`, needs `NZTCS_BOT_CONTACT`). One real lookup against Wikipedia. |

The default `pytest` run is offline.

## Non-goals

- Editing Wikipedia, or logging in, in any form.
- Creating articles or infoboxes where none exist.
- Wikidata. Its statements use a different data model and would need a separate tool.
- Wikipedias other than English. The template names are en.wiki's.
