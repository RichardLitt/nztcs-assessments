# NZTCS → Wikipedia Speciesbox Bot

## Context

`fetch_nztcs_assessments.py` already pulls NZ Threat Classification System assessments
from the official API and writes them to a CSV (currently `nztcs_report_1176_20260505.csv`,
507 Lepidoptera species for the 2026 report). Each row carries a scientific name,
common name, conservation status, criteria, qualifiers, and the citation report.

That data is missing from most Wikipedia species articles. Even the flagship example
[Pūriri moth (Aenetus virescens)](https://en.wikipedia.org/wiki/P%C5%ABriri_moth) has
a Speciesbox but no `|status=` / `|status_system=NZTCS`. The goal: a bot that, for each
CSV row, finds the matching Wikipedia article and produces a wikitext patch that adds or
updates the NZTCS conservation status block in the Speciesbox/Taxobox.

Per discussion with the user, the bot will **generate a review queue** (no live edits).
The user will copy proposed diffs into Wikipedia's edit UI manually. This avoids any
Bot Approval Request (WP:BRFA) overhead and eliminates the risk of bad automated edits.

## Approach

A single new script `wiki_nztcs_bot.py` that, for each row of the CSV:

1. **Filters** out rows we cannot match (skip rules below).
2. **Resolves** the row's binomial to a Wikipedia article via the MediaWiki API,
   following redirects (e.g. `Aenetus virescens` → `Pūriri moth`).
3. **Verifies** the article actually contains a Speciesbox/Taxobox whose `genus` +
   `species` (or `taxon`) matches the row. Rejects disambiguation pages, list pages,
   and articles about a different taxon that happens to share a name fragment.
4. **Patches** the Speciesbox wikitext: inserts NZTCS status, or updates an existing
   NZTCS block, or appends as `status2_*` if the article already uses IUCN as `status_*`.
5. **Emits** a JSONL review queue plus a human-readable Markdown report.

Three buckets in the output:
- `matched/` — confident matches with a wikitext diff ready to paste.
- `ambiguous/` — title matched but speciesbox check failed; needs human eyes.
- `no_match/` — no Wikipedia article found for the binomial.

## Pipeline

| Step | Tool / API | Notes |
|---|---|---|
| Parse CSV | stdlib `csv` | Same module style as `fetch_nztcs_assessments.py:1`. |
| Clean binomial | `re` | Strip author + year: `"Aenetus virescens (Doubleday, 1843)"` → `"Aenetus virescens"`. Also normalises NBSP, en-dashes. |
| Resolve title | MediaWiki action API: `action=query&titles=...&redirects=1` | Follows redirects in one round-trip. Returns canonical title or `missing`. |
| Fetch wikitext | `action=query&prop=revisions&rvprop=content&rvslots=main` | Or `Special:Export/<title>` (no auth, simpler). |
| Parse Speciesbox | `mwparserfromhell` (PyPI) | Robust template parameter access; do NOT regex template params. |
| Verify taxon | Compare `genus`+`species` or `taxon` param against the cleaned binomial. | |
| Patch params | `mwparserfromhell` template node mutation | See "Patch logic" below. |
| Emit review | JSONL + Markdown | One file per bucket. |

`mwparserfromhell` is the standard library used by `pywikibot` for exactly this kind
of template editing. Avoids the trap of regex-mangling templates with nested
`{{...}}` parameters.

## Status code mapping

Speciesbox `|status=` expects an NZTCS short code (verified against
[Wikipedia:Conservation_status](https://en.wikipedia.org/wiki/Wikipedia:Conservation_status)
and a real-world example, [Powelliphanta augusta](https://en.wikipedia.org/wiki/Powelliphanta_augusta), which uses `status = NC`, `status_system = NZTCS`). Map the
`conservationStatusTitle` column:

| CSV value | `|status=` |
|---|---|
| Nationally Critical | `NC` |
| Nationally Endangered | `NE` |
| Nationally Vulnerable | `NV` |
| Nationally Increasing | `NI` |
| Declining | `D` |
| Recovering | `R` |
| Relict | `Rel` |
| Naturally Uncommon | `NU` |
| Uncommon | `NU` *(2025 manual rename, treat as Naturally Uncommon)* |
| Not Threatened | `NT` |
| Data Deficient | `DD` |
| Extinct | `EX` |
| Migrant | `M` |
| Vagrant | `V` |
| Coloniser | `C` |
| Introduced and Naturalised | `IN` |

The script must validate each cell against this table and refuse to patch on an
unknown value (rather than silently skipping). On first run, log any unmapped CSV
values so the table can be extended.

## Skip rules (per user)

Skip a row before any Wikipedia lookup if its `nztcsSpeciesName` matches:

- `\bsp\.\s*[A-Z]\b` — undescribed species, e.g. `Archyala sp. A (NZAC04239001; Mataroa)`.
- starts with `"` (double quote) — provisional / quoted-genus names, e.g.
  `"Acroclita" discariana Philpott, 1930`. The genus is in scare quotes because
  the assignment is uncertain; no Wikipedia article will match the quoted form.

Logged to `skipped.tsv` with reason for transparency.

## Patch logic

Given a parsed Speciesbox/Taxobox template node:

1. **Already has `status_system = NZTCS`**: update `status` and `status_ref`.
   Diff is shown so the user can sanity-check (and skip if their existing ref is
   to a newer source).
2. **Has `status_system = IUCN3.1` (or any non-NZTCS)**: add `status2 = …`,
   `status2_system = NZTCS`, `status2_ref = …`. Insert immediately after the
   primary status block.
3. **Has no status block**: insert `status` / `status_system` / `status_ref`
   immediately after the `authority`/`taxon` line, matching the template's
   documented parameter order.

`status_ref` content (use the CSV row's `reportName` and `reportYear`):

```
<ref name="NZTCS-Lepidoptera-2025">{{cite report
| author = Hoare, R. J. B.; ...
| date = 2026
| title = Conservation status of New Zealand butterflies and moths (Lepidoptera), 2025
| publisher = New Zealand Department of Conservation
| series = New Zealand Threat Classification Series
}}</ref>
```

The script generates the citation from `reportName` (e.g. `"Lepidoptera 2025
(Hoare et al. 2026)"`) — full author list isn't in the CSV, so the citation is a
template **scaffold**: the user fills in authors and series number when reviewing.
Mark the scaffold with an HTML comment `<!-- TODO: complete authors -->` so it's
visible in the diff.

## Output layout

```
review/
├── matched.jsonl       # one line per confident patch: {row, title, diff, before, after}
├── matched.md          # human-readable: per-species section with diff in fenced block
├── ambiguous.jsonl     # title found but speciesbox verification failed
├── ambiguous.md        # human-readable, with reason (no speciesbox / wrong taxon / disambig)
├── no_match.tsv        # binomial → "missing"
├── skipped.tsv         # binomial → reason (undescribed / quoted-genus)
└── stats.txt           # counts: rows in / matched / ambiguous / missing / skipped
```

## Wikipedia API policy compliance

We are bound by three Wikimedia documents. Each rule below cites its source and
states how the script implements it.

### 1. User-Agent — [foundation.wikimedia.org/wiki/Policy:User-Agent_policy](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy)

> "Wikimedia sites require a HTTP User-Agent header for all requests."
> Format: `<client name>/<version> (<contact information>) <library/framework name>/<version>`
> Example: `CoolBot/0.0 (https://example.org/coolbot/; coolbot@example.org) generic-library/0.0`
> "Scripts should use an informative User-Agent string with contact information,
> or they may be blocked without notice."

**How we comply:** every request sets

```
User-Agent: nztcs-wiki-bot/0.1 (https://github.com/<user>/nztcs-assessments; richard.littauer@gmail.com) python-requests/2.x
```

The string includes "bot" as recommended (so Wikimedia traffic analysis can
classify it correctly). The repo URL is filled in once the project is published.
The User-Agent is constructed in one place (`UserAgent.build()`) and a unit test
asserts the format.

### 2. API etiquette — [mediawiki.org/wiki/API:Etiquette](https://www.mediawiki.org/wiki/API:Etiquette)

| Rule (quoted from the page) | Implementation |
|---|---|
| "Make your requests in series rather than in parallel" | Single-threaded; one in-flight request at a time. |
| "Batch multiple items using the pipe character: `titles=PageA\|PageB\|PageC`" | Title resolution batches up to 50 titles per call (the API's default `apilimit`). |
| "Use the `maxlag` parameter [for] non-interactive tasks" | All requests pass `maxlag=5`; on a `maxlag` error response the script sleeps for the suggested `Retry-After` and retries (max 3 times, exponential backoff). |
| "Use GZip compression … `Accept-Encoding: gzip`" | `requests` sends this by default; we leave it on and verify in tests. |
| "Prefer GET over POST [for reads]" | All read calls use GET. |
| "All new API users should use JSON" | `format=json&formatversion=2`. |

We add a self-imposed 1 req/sec floor on top of `maxlag` because the script is
non-urgent; this also makes log output easier to follow during review.

### 3. Caching to avoid re-hitting the API

Title resolutions and revision fetches are cached on disk under `cache/` keyed
by canonical title. Re-runs after CSV updates only fetch articles whose
binomial changed. The cache is invalidated by deleting the directory.

### 4. Read-only scope

The bot **never** calls `action=edit`, `action=login`, or any write endpoint.
It is purely a read tool that produces local files. This sidesteps the entire
Bot Approval Request (WP:BRFA) process, which is required only for automated
edits. A boundary test in the suite asserts no write endpoint URL ever appears
in the request mock log.

## Project layout (open-source ready)

The current directory has only two files. The bot turns it into a small Python
package that's pip-installable, testable, and documented to a level appropriate
for an open-source release.

```
nztcs-assessments/
├── README.md                      # Quickstart, screenshots of a sample diff, install + run
├── LICENSE                        # MIT (default for small tooling — confirm with user)
├── CONTRIBUTING.md                # How to run tests, code style, how to add a new NZTCS taxon report
├── CODE_OF_CONDUCT.md             # Contributor Covenant 2.1 (standard)
├── CHANGELOG.md                   # Keep a changelog format
├── pyproject.toml                 # Project metadata, deps, ruff/pytest config
├── .github/
│   ├── workflows/ci.yml           # GitHub Actions: lint + tests on 3.10–3.13
│   └── ISSUE_TEMPLATE/            # bug.md, feature.md
├── docs/
│   ├── design.md                  # ← copy of THIS plan, the canonical design doc
│   ├── nztcs-status-codes.md      # Mapping table + provenance for each code
│   ├── wikipedia-policy.md        # How we comply with each policy point + links
│   ├── adding-a-report.md         # Walkthrough: fetch a new report ID, run the bot
│   └── reviewing-output.md        # How to apply diffs from review/matched.md to Wikipedia
├── src/
│   └── nztcs_wiki_bot/
│       ├── __init__.py
│       ├── __main__.py            # `python -m nztcs_wiki_bot`
│       ├── cli.py                 # argparse: --csv, --limit, --species, --out, --cache
│       ├── csv_loader.py          # parse + clean rows; depends on fetch script's column names
│       ├── name_cleaner.py        # binomial extraction, skip-rule predicates
│       ├── status_map.py          # CSV title → NZTCS code; raises on unknown
│       ├── wiki_client.py         # MediaWiki API wrapper (User-Agent, maxlag, batching, cache)
│       ├── speciesbox.py          # mwparserfromhell wrappers: parse, verify_taxon, patch
│       ├── citation.py            # builds the {{cite report}} scaffold from CSV row
│       ├── pipeline.py            # orchestrates: load → filter → resolve → verify → patch → emit
│       └── output.py              # JSONL + Markdown emitters
├── tests/
│   ├── conftest.py                # shared fixtures: tmp cache, sample CSV row, mock responses
│   ├── fixtures/
│   │   ├── csv/
│   │   │   ├── one_row.csv
│   │   │   ├── all_status_titles.csv         # one row per known status title
│   │   │   ├── undescribed.csv               # "Archyala sp. A …"
│   │   │   └── quoted_genus.csv              # '"Acroclita" discariana …'
│   │   ├── wikitext/
│   │   │   ├── puriri_moth.txt               # real export, has Speciesbox, no NZTCS
│   │   │   ├── powelliphanta_augusta.txt     # real export, has Speciesbox WITH NZTCS
│   │   │   ├── iucn_only.txt                 # synthetic: status_system=IUCN3.1, needs status2
│   │   │   ├── taxobox_legacy.txt            # uses {{Taxobox}} not {{Speciesbox}}
│   │   │   ├── disambig.txt                  # disambig page — verify_taxon must reject
│   │   │   ├── wrong_taxon.txt               # speciesbox for a different genus — must reject
│   │   │   └── no_infobox.txt                # plain article — must reject
│   │   └── api_responses/
│   │       ├── resolve_redirect.json         # Aenetus virescens → Pūriri moth
│   │       ├── resolve_missing.json          # title not found
│   │       ├── resolve_batch.json            # multi-title batch response
│   │       ├── maxlag_error.json             # triggers retry path
│   │       └── revisions.json                # wikitext fetch
│   ├── unit/
│   │   ├── test_csv_loader.py
│   │   ├── test_name_cleaner.py
│   │   ├── test_status_map.py
│   │   ├── test_speciesbox_parse.py
│   │   ├── test_speciesbox_verify_taxon.py
│   │   ├── test_speciesbox_patch.py
│   │   ├── test_citation.py
│   │   ├── test_wiki_client_user_agent.py
│   │   ├── test_wiki_client_batching.py
│   │   ├── test_wiki_client_maxlag_retry.py
│   │   ├── test_wiki_client_cache.py
│   │   └── test_output_format.py
│   ├── integration/
│   │   ├── test_pipeline_end_to_end.py       # full pipeline against mocked HTTP
│   │   ├── test_no_write_endpoints.py        # asserts no edit/login/csrf calls ever made
│   │   └── test_idempotent.py                # running twice produces identical review/ output
│   └── live/
│       └── test_live_smoke.py                # opt-in (`-m live`); hits real Wikipedia for one species
└── nztcs_report_1176_20260505.csv            # existing sample data
```

`fetch_nztcs_assessments.py` moves into `src/nztcs_wiki_bot/fetch.py` and gets a
small refactor to be importable (its `HTMLStripper` is reused by `csv_loader`).

## Documentation deliverables

This is open-source bound, so docs aren't a footnote. Each file has a defined
scope and audience:

- **`README.md`** — landing page for someone arriving from a search result.
  Sections: what it does (with a sample diff screenshot), why (link to the
  Wikipedia gap problem), install (`pip install -e .`), one-command quickstart
  on the bundled sample CSV, link to `docs/`. Under 200 lines.
- **`docs/design.md`** — verbatim copy of this plan file, kept up to date as
  the canonical design reference. **The user explicitly asked for this.** As
  part of implementation, copy `~/.claude/plans/i-have-the-exported-cheeky-turing.md`
  to `docs/design.md` and rename the heading.
- **`docs/nztcs-status-codes.md`** — the full status-title-to-code mapping
  table, with a column citing each row's source (Wikipedia template, NZTCS
  manual section, or our judgement call e.g. "Uncommon = NU"). Explains why
  the mapping must fail loudly on unknown values.
- **`docs/wikipedia-policy.md`** — the "Wikipedia API policy compliance"
  section above, expanded with full quotes and links to every cited document.
  The source of truth for "does this bot follow the rules" reviews.
- **`docs/adding-a-report.md`** — step-by-step: how to find a report ID on
  nztcs.org.nz, run `python -m nztcs_wiki_bot.fetch <report_id>`, then run
  the main bot against the resulting CSV.
- **`docs/reviewing-output.md`** — the human reviewer workflow: open
  `review/matched.md`, sanity-check each diff against the live article, paste
  into Wikipedia's edit UI, fill in citation TODO scaffolds, save with an
  edit summary template (provided).
- **In-code docstrings** — every public function in `src/nztcs_wiki_bot/`
  has a docstring with a one-line summary, args/returns, and a `>>> ` doctest
  for the simple ones. Doctests run as part of the pytest suite.
- **`CONTRIBUTING.md`** — covers: running tests, expected coverage threshold
  (90% for unit tests), how to add a fixture for a new species, ruff/pyright
  config, signing convention for commits.

## Critical files

- `/Users/richard/src/nztcs-assessments/src/nztcs_wiki_bot/` — **new** package.
- `/Users/richard/src/nztcs-assessments/docs/design.md` — **new** (this plan, copied in).
- `/Users/richard/src/nztcs-assessments/tests/` — **new**, full suite.
- `/Users/richard/src/nztcs-assessments/fetch_nztcs_assessments.py:1` —
  existing; relocated into the package as `fetch.py` and lightly refactored
  so its `HTMLStripper` is importable rather than module-local.
- `/Users/richard/src/nztcs-assessments/nztcs_report_1176_20260505.csv` —
  existing input; kept at repo root as a sample dataset for quickstart.

## Dependencies

`pyproject.toml`:

- Runtime: `requests`, `mwparserfromhell`.
- Dev: `pytest`, `pytest-cov`, `responses` (HTTP mocking), `ruff`, `pyright`.

## Testing strategy

The user asked for "excessive tests"; this is open-source code that other people
will fork and depend on, so the suite should leave nothing to guesswork. Three
tiers, all run by `pytest`:

### Tier 1 — unit tests (fast, hermetic, no network)

Each module gets its own test file; aim for ≥ 90% line coverage on
`src/nztcs_wiki_bot/`. The cases below are the floor, not the ceiling — add
parametrised cases as fixtures grow.

**`test_csv_loader.py`**
- Loads `fixtures/csv/one_row.csv`, asserts the parsed row has all 12 expected
  fields populated.
- Empty `commonName` and `popSizeTitle` cells survive as empty strings, not `None`.
- HTML entities in scientific names (e.g. `&amp;`, `<i>`) are stripped using
  the existing `HTMLStripper`.

**`test_name_cleaner.py`** — parametrised over a table of inputs/outputs:
| Input `nztcsSpeciesName` | Expected binomial | Skip? | Skip reason |
|---|---|---|---|
| `Aenetus virescens (Doubleday, 1843)` | `Aenetus virescens` | no | — |
| `Agrotis admirationis Guenée, 1868` | `Agrotis admirationis` | no | — |
| `Archyala sp. A (NZAC04239001; Mataroa)` | — | yes | `undescribed` |
| `Archyala sp. B (NZAC04239001; Mount Greenland)` | — | yes | `undescribed` |
| `"Acroclita" discariana Philpott, 1930` | — | yes | `quoted_genus` |
| `Pseudocoremia cineracia (Howes, 1942)` | `Pseudocoremia cineracia` | no | — |
| `Aoraia oreobolae Dugdale, 1994` | `Aoraia oreobolae` | no | — |

Plus edge cases: trailing whitespace, NBSP between genus and species, en-dash
in author year, names with subgenus parentheses.

**`test_status_map.py`**
- Every CSV `conservationStatusTitle` from the bundled report maps to a code.
- Unknown title raises `UnknownStatusError` (not silent skip).
- `categoryTitle` ("Threatened", "At Risk") is consistent with the mapped code
  (e.g. `NC` is in "Threatened"; `NU` is in "At Risk").

**`test_speciesbox_parse.py`**
- `puriri_moth.txt` parses; `genus = Aenetus`, `species = virescens`, no `status`.
- `powelliphanta_augusta.txt` parses; `status = NC`, `status_system = NZTCS`.
- `taxobox_legacy.txt` parses as `{{Taxobox}}` and the patcher recognises both
  template names.
- Article with no infobox returns `None` (not an exception).

**`test_speciesbox_verify_taxon.py`**
- `puriri_moth.txt` verifies for `Aenetus virescens` (genus + species match).
- `wrong_taxon.txt` rejects for `Aenetus virescens` (different genus).
- `disambig.txt` rejects (no speciesbox at all).
- Whitespace and italic markup in template params don't break the comparison.

**`test_speciesbox_patch.py`** — covers all three patch branches:
- *Insert new status*: `puriri_moth.txt` + `NV` → output contains exactly one
  `status = NV`, `status_system = NZTCS`, ref name `NZTCS-Lepidoptera-2025`.
- *Update existing NZTCS*: `powelliphanta_augusta.txt` + `NE` → `NC` becomes
  `NE`; the existing ref is replaced; only one `status_system = NZTCS` line
  remains.
- *Add as `status2`*: `iucn_only.txt` + `NU` → article keeps `status = LC` and
  `status_system = IUCN3.1`, gains `status2 = NU` and `status2_system = NZTCS`.
- *Idempotency*: applying the same patch twice is a no-op (asserts byte-equal
  output between the first and second pass).

**`test_citation.py`**
- Generated `<ref>` block contains `cite report`, the report year, the report
  name, and the `<!-- TODO: complete authors -->` scaffold marker.
- Ref name is deterministic and slug-safe (e.g. `NZTCS-Lepidoptera-2025`, no
  spaces or punctuation).

**`test_wiki_client_user_agent.py`**
- The User-Agent string matches the regex
  `^nztcs-wiki-bot/\d+\.\d+(\.\d+)?\s+\(https://[^)]+\)\s+python-requests/`.
- Contains the contact email and the literal substring `bot`.

**`test_wiki_client_batching.py`**
- Resolving 120 titles produces 3 API calls (50 + 50 + 20), not 120.
- Pipe-character titles (rare but legal) are correctly URL-encoded.

**`test_wiki_client_maxlag_retry.py`** — uses `responses` to mock HTTP:
- A `maxlag` error response triggers a sleep + retry.
- Three consecutive `maxlag` errors raise `MaxLagExhausted`.
- `Retry-After` header is honoured (mocked clock asserts the sleep duration).

**`test_wiki_client_cache.py`**
- First fetch hits HTTP; second fetch with same title hits disk only.
- Cache files are JSON, gzipped, named by SHA-256 of the canonical title.
- Deleting a cache file forces a re-fetch.

**`test_output_format.py`**
- `matched.jsonl`: each line is valid JSON with keys
  `{species_id, binomial, common_name, title, status_code, before, after, diff}`.
- `matched.md`: each entry has a stable anchor (`<a id="speciesId-12345">`)
  for cross-linking.
- `stats.txt` totals match the row count (matched + ambiguous + no_match +
  skipped == input rows).

### Tier 2 — integration tests (no network, full pipeline)

**`test_pipeline_end_to_end.py`** — wires the real modules together against
fully mocked HTTP using the `api_responses/` fixtures:
- A 5-row CSV (one of each: clean match, redirect-to-common-name, has-NZTCS
  already, IUCN-only, undescribed) produces exactly the expected files in
  `review/`. Compared to a checked-in `expected/` directory byte-for-byte.

**`test_no_write_endpoints.py`** — the safety boundary test the user implicitly
wants. Captures every URL the pipeline sends; asserts none contain `action=edit`,
`action=login`, `action=createaccount`, `action=rollback`, or any other write
endpoint listed in [API:Edit](https://www.mediawiki.org/wiki/API:Edit). Failing
this test should block CI.

**`test_idempotent.py`** — running the pipeline twice on the same CSV produces
byte-identical output directories. Catches non-determinism (e.g. dict iteration
order leaking into Markdown).

### Tier 3 — live tests (opt-in, hits real Wikipedia)

**`test_live_smoke.py`** — marked `@pytest.mark.live`; CI runs it once a week
on a cron, not on every PR. Resolves the binomial `Aenetus virescens` against
real Wikipedia and asserts:
- Title resolves through redirect to `Pūriri moth`.
- Fetched wikitext contains a Speciesbox.
- Patched output adds NZTCS status without touching any other line in the
  template.

This single test catches breakage from Wikipedia API changes that mocks would
miss; keeping it isolated keeps the rest of the suite hermetic.

### Coverage and CI

- `pytest --cov=src/nztcs_wiki_bot --cov-fail-under=90` in CI.
- `ruff check` and `pyright` run before tests.
- Doctests in module docstrings run as part of the same `pytest` invocation
  (`addopts = --doctest-modules`).
- GitHub Actions matrix: Python 3.10, 3.11, 3.12, 3.13 on Ubuntu; one job on
  macOS for parity with the dev environment.

## Manual acceptance (after the suite passes)

The automated suite proves the code works; these final checks prove the *output*
works for its purpose:

1. **Sample diff renders**: pick the `Aenetus virescens` entry from
   `review/matched.md`, paste the diff into Wikipedia's edit preview for
   [Pūriri moth](https://en.wikipedia.org/wiki/P%C5%ABriri_moth). The preview
   shows the NZTCS "Not Threatened" badge in the rendered Speciesbox.
2. **Status mapping coverage on real data**: run against the full
   `nztcs_report_1176_20260505.csv` and inspect `stats.txt`. Any unmapped
   `conservationStatusTitle` causes a hard error — do not let the script
   produce silent garbage diffs.
3. **Skip-rule correctness**: `skipped.tsv` contains every `sp. A`/`sp. B`
   row and every quoted-genus row from the CSV, with the correct reason.
4. **Design doc shipped**: `/Users/richard/src/nztcs-assessments/docs/design.md`
   exists and is identical (modulo the heading) to this plan file. The user
   asked for this explicitly.
