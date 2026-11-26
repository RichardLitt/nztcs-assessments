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
| Extract binomial; skip undescribed, quoted-genus, `cf.`/`aff.`, subspecies and `s.l.`/`s.s.` names | `name_cleaner` | `skipped` |
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
├── wiki_client.py   reads Wikipedia for the review run (read-only, cached)
├── editor.py        the only module that writes to Wikipedia (used by apply)
├── apply.py         `apply`: confirm and save reviewed patches, one at a time
├── speciesbox.py    find / verify / patch the infobox (mwparserfromhell)
├── reports.yaml     known reports → Wikidata item and shared ref name
├── reports.py       loads and checks reports.yaml
├── citation.py      status_ref: {{CiteQ}} for known reports, else a scaffold
├── pipeline.py      orchestration; no I/O of its own
└── output.py        Buckets → review/ files (deterministic ordering)
```

The review run talks to Wikipedia only through `wiki_client`, whose read-only
guard covers every request it makes. Writing is confined to `editor`, which
only `apply` uses, and `apply` saves nothing without the operator confirming
each edit (see [assisted-editing.md](assisted-editing.md)). All other modules
are pure apart from `fetch` (HTTP to NZTCS) and `output` (local files).

### Assisted editing, not a bot

`apply` saves from the operator's own account, through a bot password with only
the "Edit existing pages" grant. Every save needs a `y`. That keeps it within
Wikipedia's rules for assisted editing, which don't need bot approval. Before
asking, it fetches the live article and skips it unless the text still equals
the run's `before`, so a stale patch can't overwrite a newer edit. The save
also sends `baserevid` / `basetimestamp` / `starttimestamp` so MediaWiki
catches a conflict in the gap between fetch and save. It never creates pages
(`nocreate`), fails rather than edit logged out (`assert=user`), honours
`{{bots}}`, keeps at least 5 seconds (default 10) between saves, and stops on a
new talk-page message. Fully automatic editing would need a bot account and
approval, and is out of scope.

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

1. **A block already has system NZTCS** (`status`, `status2` or `status3`):
   update its code and ref in place (action `update`).
2. **Other systems, e.g. IUCN or CITES**: leave them alone and add NZTCS in the
   first empty block, `status2*` then `status3*` (action `add_secondary`). Only
   `{{Speciesbox}}` and `{{Subspeciesbox}}` display `status3`. With no empty
   block, nothing changes and the article goes to `ambiguous`
   (`no-free-status-slot`).
3. **No status**: insert `status`, `status_system`, `status_ref` just before
   the first taxon parameter (`taxon`, `genus`, `species`, `regnum`, an
   `unranked_*` rank and so on), so they sit after the name and image lines.
   That's where the Speciesbox and Taxobox documentation and most articles put
   them (80 of the 88 moth articles citing the 2025 report). With no taxon
   parameter, they're appended (action `insert`).

New `status2*` or `status3*` lines go straight after the existing status blocks. Lines that
already exist are updated where they are and never moved.

Patching is idempotent. `status_ref` is only rewritten if it doesn't already
cite this report's ref name, and if the article already defines that ref
elsewhere, the short `<ref name="…" />` form is used.

Replacing `status_ref` can remove the full definition of an old citation that
the article also reuses elsewhere as `<ref name="X" />`. When that happens, the
patch moves the full definition to the first remaining reuse, so no reuse is
left as a cite error.

### Only emit codes Wikipedia can render

The code table is restricted to what Wikipedia's `Module:Conservation status`
displays for NZTCS. Real categories the module doesn't render yet (Coloniser,
Migrant, Vagrant, Introduced and Naturalised) go to `unmapped` as
`no-wikipedia-code`; their proposed codes wait in `PENDING_WIKIPEDIA_CODES`
until the module supports them (see the
[edit request draft](proposals/module-conservation-status-nztcs.md)). Titles the
table has never seen go to `unmapped` as `unknown-status-title`. Nothing is
guessed. See [nztcs-status-codes.md](nztcs-status-codes.md).

"Uncommon" depends on the row's criteria code. The 2022 NZTCS manual replaced
"Naturally Uncommon" with "Uncommon", which also covers populations that are
small because of human impact, and records the population state in the criteria
code (`UNCn` natural, `UNCu` unnatural, `UNCx` unknown). Wikipedia's `NU`
renders "Naturally Uncommon", so `status_map.code_for()` emits it only for
`UNCn`. Other Uncommon rows go to `unmapped` as `no-wikipedia-code` until the
module has an "Uncommon" code. The manual treats an unknown state as unnatural,
and a blank criteria code is handled the same way.

### Skip names that can't match, or whose status isn't the species'

These are skipped before any request is made and listed in `skipped.tsv` with a
reason:

| Reason | Example | Why |
|---|---|---|
| `undescribed` | `Archyala sp. A (NZAC…)` | No article exists. |
| `quoted_genus` | `"Acroclita" discariana` | An uncertain generic placement that no article title will use. |
| `uncertain_identification` | `Chalastra cf. pellurgata` | `cf.` / `aff.`: a provisional identification, not the named species. |
| `subspecies` | `Vanessa gonerilla ida` | The status is for the subspecies. Putting it on the species article would claim it for the whole species. |
| `taxon_concept` | `Pyrgotis pyramidias s.s.` | The report assesses a broad (`s.l.`) and a narrow (`s.s.`) concept separately, with different statuses. Neither belongs to the article as such. |

A `s.l.` / `s.s.` straight after the genus (`Hierodoris s.l. insignis`) only
qualifies the genus, so it is dropped and *Hierodoris insignis* is looked up as
normal.

### Citations come from Wikidata where possible

The CSV has the report name and year but not the authors or series number, so
it can't produce a full citation by itself.

For reports listed in `reports.yaml`, the citation is `{{CiteQ|<item>}}`, which
renders the full reference from the report's Wikidata item. That's how existing
articles already cite these reports. The default ref name is the one most of
those articles use (`NZTCS2025` for Lepidoptera 2025), so the bot's citations
look like theirs. If the
article already cites the report under a different name (matched by Wikidata ID
or full-text URL in a named ref), the bot reuses that name and emits only
`<ref name="..." />`. Ref names are matched case-sensitively, whether they're
quoted or bare, as MediaWiki does.

For any other report, the bot falls back to a `{{cite report}}` scaffold: it
fills in what's known and puts a visible `<!-- TODO … -->` in `author`, so the
reviewer has to complete it. The scaffold's ref name (`NZTCS-<taxon>-<year>`) is
deterministic, so every species from one report shares one reference.

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
