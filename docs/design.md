# Design

This is how `nztcs-wiki-bot` is built and why. For usage, see the
[README](../README.md).

## Goal and the main constraint

**Goal:** for each species in an NZTCS report, produce a correct wikitext patch
that adds or updates the NZTCS conservation status in its Wikipedia article's
infobox.

**Main constraint:** the tool produces a *review queue*, never live edits. A
human pastes each patch. This has three consequences:

1. There is no need for Wikipedia's bot approval process (WP:BRFA), which only
   covers automated editing.
2. The cost of a wrong match drops from "a bad edit on Wikipedia" to "a
   reviewer skips an entry".
3. The tool needs no credentials, so it can't damage anyone's account.

Everything below follows from preferring a *missing* patch over a *wrong* one.

## Pipeline

```
CSV ─▶ clean name ─▶ skip? ─▶ map status ─▶ resolve title ─▶ fetch wikitext
                                                                   │
            review/ ◀─ emit ◀─ patch infobox ◀─ verify taxon ◀─ find infobox
```

`pipeline.run()` walks every row, and each row ends in exactly one bucket.
`stats.txt` checks the count with `balanced True`.

| Step | Module | Failure goes to |
|---|---|---|
| Load + strip HTML | `csv_loader` | (error if columns are missing) |
| Extract binomial; skip undescribed (`sp.`) and quoted-genus names | `name_cleaner` | `skipped` |
| Map status title to code | `status_map` | `unmapped` |
| Resolve title, following redirects (batched, before the per-row loop) | `wiki_client` | `no_match` (`missing`) |
| Fetch current wikitext | `wiki_client` | `no_match` (`no-wikitext`) |
| Find a Speciesbox/Taxobox/Subspeciesbox/Infraspeciesbox/Automatic taxobox | `speciesbox` | `ambiguous` (`no-speciesbox`) |
| Check its genus + species (or `taxon`) match the row | `speciesbox` | `ambiguous` (`taxon-mismatch`) |
| Patch; a no-op patch means nothing to do | `speciesbox`, `citation` | `ambiguous` (`already-current`) |
| Success | `output` | `matched` |

The pipeline takes any object with `resolve_titles()` and `fetch_wikitext()`
(the `WikiReader` protocol). Tests use an in-memory fake, and integration tests
use the real client against mocked HTTP.

## Module boundaries

```
src/nztcs_wiki_bot/
├── cli.py           argparse; dispatches `fetch` or runs the pipeline
├── fetch.py         nztcs.org.nz → CSV (paginated)
├── csv_loader.py    CSV → Row; owns EXPECTED_FIELDS and strip_html
├── name_cleaner.py  raw NZTCS name → binomial or skip reason
├── status_map.py    status title → Speciesbox code, or why there isn't one
├── wiki_client.py   the only module that talks to Wikipedia
├── speciesbox.py    find / verify / patch the infobox (mwparserfromhell)
├── citation.py      {{cite report}} scaffold from reportName / reportYear
├── pipeline.py      orchestration; no I/O of its own
└── output.py        Buckets → review/ files (deterministic ordering)
```

`wiki_client` is the only module that talks to Wikipedia, so its read-only
guard covers every Wikipedia request. All other modules are pure apart from
`fetch` (HTTP to NZTCS) and `output` (local files).

## Key decisions

### Parse templates, never regex them

Infobox parameters often contain nested templates and refs
(`status_ref = <ref>{{cite …}}</ref>`). `mwparserfromhell`, the parser
pywikibot uses, handles that. Regex would mangle it. Parameter values are only
normalised (links and italics stripped) for comparison, never for writing.

### Verify the taxon, not just the title

Redirects are common (`Aenetus virescens` → `Pūriri moth`), and so are genus
pages, disambiguation pages, and articles that redirect a synonym to a
different species. After resolving, the bot requires the infobox's
`genus` + `species` (or its `taxon`) to match the CSV binomial,
case-insensitively, ignoring markup. Anything else goes to `ambiguous`.

### Three patch branches

`speciesbox.patch_status()`:

1. **Existing `status_system = NZTCS`**: update `status` and `status_ref` in
   place (action `update`).
2. **Another system, e.g. IUCN**: leave it alone and add `status2`,
   `status2_system = NZTCS`, `status2_ref` (action `add_secondary`, or
   `update` if an NZTCS secondary already exists).
3. **No status**: insert `status`, `status_system`, `status_ref` after the last
   of `authority` / `taxon` / `species` / `genus` / `name`, matching the
   template's documented order (action `insert`).

Patching is idempotent. `status_ref` is only rewritten if it doesn't already
cite this report's ref name, and if the article already defines that ref
elsewhere, the short `<ref name="…" />` form is used.

### Only emit codes Wikipedia can render

The code table is restricted to what Wikipedia's `Module:Conservation status`
displays for NZTCS. Real categories the module doesn't render yet (Coloniser,
Migrant, Vagrant, Introduced and Naturalised) go to `unmapped` as
`no-wikipedia-code`; their proposed codes wait in `PENDING_WIKIPEDIA_CODES`
until the module supports them (see the
[edit request draft](proposals/module-conservation-status-nztcs.md)). Titles the
table has never seen go to `unmapped` as `unknown-status-title`. Nothing is
guessed. See [nztcs-status-codes.md](nztcs-status-codes.md).

### Skip names that can't match

Undescribed species (`Archyala sp. A (NZAC…)`) have no article. Scare-quoted
genera (`"Acroclita" discariana`) mark an uncertain generic placement that no
article title will use. Both are skipped before any request is made and listed
in `skipped.tsv` with a reason.

### Citation is a scaffold

The CSV has the report name and year but not the authors or series number. The
generated `{{cite report}}` fills in what's known and puts a visible
`<!-- TODO … -->` in `author`, so the reviewer has to complete it. The ref name
(`NZTCS-<taxon>-<year>`) is deterministic, so every species from one report
shares one reference.

### Contact belongs to the operator

Wikimedia's User-Agent policy wants a way to reach whoever is *running* the
tool. The project URL is fixed, but the contact must be supplied
(`--contact` / `$NZTCS_BOT_CONTACT`), and the client won't start without it. A
fork can't accidentally send someone else's email. See
[wikipedia-policy.md](wikipedia-policy.md).

### Deterministic output

Buckets are sorted before writing, JSON keys are sorted, and nothing
time-dependent is written. Two runs over the same input produce byte-identical
`review/` directories, which makes diffs between runs meaningful.

## Testing

| Tier | Where | What |
|---|---|---|
| Unit | `tests/unit/` | Each module on its own, including User-Agent shape, batching, maxlag retry, cache, every patch branch, and status mapping. |
| Integration | `tests/integration/` | The real `WikiClient` against a fake wiki (`fixtures/api_responses/site.json`) served by `responses`. Includes a byte-for-byte golden comparison of `review/` for a CSV with one row per outcome, idempotency (fresh and cached), and the no-write-requests boundary. |
| Doctests | `src/nztcs_wiki_bot/` | Small examples in docstrings. |
| Live | `tests/live/` | Opt-in (`pytest -m live`, needs `NZTCS_BOT_CONTACT`). One real lookup; worth running before processing a new report. |

CI runs `ruff`, `pyright`, then `pytest` with a 90% coverage floor, on Python
3.10–3.13 (Ubuntu) and 3.12 (macOS).

## Non-goals

- Editing Wikipedia, or logging in, in any form.
- Creating articles or infoboxes where none exist.
- Wikidata. Statements there have a different data model and would need a separate tool.
- Wikipedias other than English. The template and module names are en.wiki's.
