# NZTCS → Wikipedia Speciesbox Bot

A tool that helps add **New Zealand Threat Classification System (NZTCS)**
conservation statuses to Wikipedia species articles.

Most New Zealand species articles on Wikipedia have an information box (a
"Speciesbox") but no conservation status from the NZTCS — the official New
Zealand government assessment. Even the flagship
[Pūriri moth](https://en.wikipedia.org/wiki/P%C5%ABriri_moth) is missing it.
This tool reads an NZTCS report and, for each species, prepares a ready-to-paste
edit that fills that gap.

> **It does not edit Wikipedia.** It only *reads* Wikipedia and writes proposed
> edits to files on your computer. You review each one and paste it in by hand.
> See [Is this safe?](#is-this-safe) below.

---

## Table of contents

- [What it actually does](#what-it-actually-does)
- [Is this safe?](#is-this-safe)
- [Requirements](#requirements)
- [Install](#install)
- [Before your first run: set your contact info](#before-your-first-run-set-your-contact-info)
- [Quickstart](#quickstart)
- [Understanding the output](#understanding-the-output)
- [Applying a patch to Wikipedia](#applying-a-patch-to-wikipedia)
- [Command-line options](#command-line-options)
- [Getting a different NZTCS report](#getting-a-different-nztcs-report)
- [How status codes are mapped](#how-status-codes-are-mapped)
- [How it works (for the curious)](#how-it-works-for-the-curious)
- [Development & testing](#development--testing)
- [FAQ / troubleshooting](#faq--troubleshooting)
- [License](#license)

---

## What it actually does

Given a CSV of NZTCS assessments (one row per species), for each species it:

1. **Cleans the name** — turns `Aenetus virescens (Doubleday, 1843)` into the
   bare scientific name `Aenetus virescens`.
2. **Skips names it can't match** — undescribed species (`Archyala sp. A`) and
   uncertain genus names in quotes (`"Acroclita" discariana`).
3. **Finds the Wikipedia article** — looks up the name, following redirects
   (so `Aenetus virescens` correctly lands on `Pūriri moth`).
4. **Checks it's the right article** — confirms the article's Speciesbox is
   actually about that species, so it never proposes an edit to the wrong page.
5. **Writes a proposed edit** — produces the exact wikitext change that adds (or
   updates) the NZTCS status, as a diff you can read.
6. **Sorts everything into buckets** — confident matches, things that need a
   human to look, names with no article, and skipped names.

The result is a folder of review files. **Nothing is sent back to Wikipedia.**

---

## Is this safe?

Yes, by design. The important points:

- **It never edits Wikipedia.** The only network requests it makes are
  *read-only* lookups (`action=query`). There is a hard guard in the code that
  refuses any other kind of request, and a test that proves it.
- **It never logs in.** There is no login code and no place to put a password or
  token. To Wikipedia, this tool is just an anonymous reader — it cannot be
  associated with your account, and cannot affect it.
- **It is polite to Wikipedia's servers**, following the
  [Wikimedia API etiquette](https://www.mediawiki.org/wiki/API:Etiquette):
  - sends an honest, identifying `User-Agent` with contact info;
  - makes at most ~1 request per second;
  - uses the `maxlag` flag so it backs off automatically when the servers are
    busy;
  - batches lookups (up to 50 names per request);
  - caches results on disk, so re-runs don't re-fetch.

The worst thing a run can do is read a bit too eagerly and earn a temporary,
anonymous rate-limit on your IP address — not anything to do with your account.

**The one thing you must do first:** give it your contact info so Wikimedia
can reach you if they ever need to. See the next section.

---

## Requirements

- **Python 3.10 or newer** (`python3 --version` to check).
- An internet connection (only when you actually run it against Wikipedia).

---

## Install

From the project folder, create an isolated environment and install the tool
into it. This keeps it separate from your system Python.

```bash
# 1. create a virtual environment in a .venv/ folder
python3 -m venv .venv

# 2. activate it (do this each time you open a new terminal)
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows PowerShell

# 3. install the tool plus its development extras (tests, linter)
pip install -e ".[dev]"
```

To check it installed:

```bash
nztcs-wiki-bot --help
```

(If you don't want to activate the environment, you can always run it as
`.venv/bin/python -m nztcs_wiki_bot ...` instead.)

---

## Before your first run: set your contact info

Wikimedia policy asks every automated reader to identify itself with **working**
contact information, so they can email you instead of silently blocking you.
The tool refuses to run until you provide yours — either per run:

```bash
nztcs-wiki-bot --contact you@example.org --csv ...
```

or once per shell session:

```bash
export NZTCS_BOT_CONTACT=you@example.org
```

An email address or a reachable URL (e.g. your Wikipedia user page) both work.

---

## Quickstart

First download a report. Report `1176` is the 2026 Lepidoptera report (507
moths and butterflies):

```bash
nztcs-wiki-bot fetch 1176 --out lepidoptera.csv
```

**Start small.** Process just a handful of species first so you can see how it
behaves before running the whole file:

```bash
nztcs-wiki-bot --csv lepidoptera.csv --limit 5
```

This makes a few read-only requests to Wikipedia and writes a `review/` folder.
Open `review/matched.md` to see the proposed edits.

When you're comfortable, run the whole file:

```bash
nztcs-wiki-bot --csv lepidoptera.csv
```

The first full run will take a few minutes (it's deliberately rate-limited to be
polite). Re-runs are much faster because results are cached in `cache/`.

---

## Understanding the output

Everything lands in the `review/` folder (change with `--out`):

| File | What's in it |
|---|---|
| `matched.md` | **Start here.** Confident matches, each with a readable diff to paste into Wikipedia. |
| `matched.jsonl` | The same matches as machine-readable JSON (one per line), if you want to script over them. |
| `ambiguous.md` / `.jsonl` | An article was found but something didn't line up (no Speciesbox, the Speciesbox was about a different species, or it already has this status). **Needs your eyes.** |
| `unmapped.tsv` | The species' status wasn't a recognised conservation code (e.g. `Not assessed`). Nothing to patch. |
| `no_match.tsv` | No Wikipedia article was found for that name. |
| `skipped.tsv` | Names skipped before lookup (undescribed `sp.` names, quoted-genus names), with the reason. |
| `stats.txt` | A tally. `balanced True` confirms every input row was accounted for in exactly one bucket. |

Read `matched.md` top to bottom. Each entry shows the species, the Wikipedia
article it maps to, the NZTCS status code, and the exact change as a diff:

````markdown
## Aenetus virescens → Pūriri moth

- Common name: pūriri moth
- NZTCS status: `NT`
- Patch action: insert

```diff
 {{Speciesbox
 | genus = Aenetus
 | species = virescens
+| status = NT
+| status_system = NZTCS
+| status_ref = <ref name="NZTCS-Lepidoptera-2025">{{cite report ...}}</ref>
 | authority = (Doubleday, 1843)
 }}
```
````

---

## Applying a patch to Wikipedia

This is a manual, human step — that's the point.

1. Open the species' article on Wikipedia and click **Edit source**.
2. Find the `{{Speciesbox}}` (or `{{Taxobox}}`) near the top.
3. Apply the change shown in the diff — add the `+` lines.
4. **Complete the citation.** The generated reference is a *scaffold*: it
   contains a visible `<!-- TODO: complete author list ... -->` marker. Fill in
   the real authors and series number from the NZTCS report before saving.
5. Use **Show preview** to confirm the conservation-status badge renders.
6. Save with a clear edit summary, e.g.
   *"Add NZTCS conservation status (Lepidoptera 2025)"*.

Always sanity-check the diff against the live article — Wikipedia articles change,
and you are the editor of record, not the bot.

---

## Command-line options

```
nztcs-wiki-bot --csv PATH [--contact TEXT] [--out DIR] [--cache DIR] [--limit N] [--species TEXT]
```

| Option | Default | Meaning |
|---|---|---|
| `--csv PATH` | *(required)* | The NZTCS report CSV to process. |
| `--out DIR` | `review` | Where to write the review files. |
| `--cache DIR` | `cache` | Where to cache Wikipedia responses. Delete this folder to force fresh fetches. |
| `--limit N` | *(none)* | Process at most `N` species. Great for a test run. |
| `--species TEXT` | *(none)* | Only process species whose name contains `TEXT` (e.g. `--species Aenetus`). |
| `--contact TEXT` | `$NZTCS_BOT_CONTACT` | Your email or contact URL, sent in the User-Agent. Required. |

---

## Getting a different NZTCS report

To fetch another taxon group, pass that report's ID from
[nztcs.org.nz](https://nztcs.org.nz):

```bash
nztcs-wiki-bot fetch <report_id>
```

Without `--out`, this writes `nztcs_report_<id>_<date>.csv`, which you then pass
to `--csv`.

> If the new report uses a conservation-status label this tool hasn't seen
> before, it won't guess — that species goes into `unmapped.tsv` so you can add
> the mapping deliberately. See the next section.

---

## How status codes are mapped

NZTCS status names are translated to the short codes Wikipedia's Speciesbox
expects. The full table lives in
[`src/nztcs_wiki_bot/status_map.py`](src/nztcs_wiki_bot/status_map.py). A sample:

| NZTCS status | Speciesbox code |
|---|---|
| Nationally Critical | `NC` |
| Nationally Endangered | `NE` |
| Nationally Vulnerable | `NV` |
| Declining | `D` |
| Naturally Uncommon / Uncommon | `NU` |
| Not Threatened | `NT` |
| Data Deficient | `DD` |

The tool **never guesses**. If it meets a status name not in the table, it
refuses to produce a (possibly wrong) edit and lists the species in
`unmapped.tsv`. To support a new status, add a line to the table in
`status_map.py`.

---

## How it works (for the curious)

The code is a small Python package under `src/nztcs_wiki_bot/`. Each file does
one job:

| File | Responsibility |
|---|---|
| `fetch.py` | Download a report from nztcs.org.nz into a CSV. |
| `csv_loader.py` | Read and clean rows from the NZTCS CSV. |
| `name_cleaner.py` | Extract the scientific name; decide what to skip. |
| `status_map.py` | Translate status names to Speciesbox codes. |
| `wiki_client.py` | **The only file that talks to Wikipedia.** Read-only, polite, cached. |
| `speciesbox.py` | Parse, verify, and patch the Wikipedia infobox template. |
| `citation.py` | Build the citation reference scaffold. |
| `pipeline.py` | Tie it all together; sort each species into a bucket. |
| `output.py` | Write the `review/` files. |
| `cli.py` | The command-line interface. |

All Wikipedia access goes through `wiki_client.py`, and every request in it is a
read-only `GET` with a hard guard that rejects anything else. The rest of the
package is pure local computation and can be tested with no internet at all.

---

## Development & testing

The test suite is extensive and runs entirely **offline** by default (network
calls are mocked), so it's safe to run anytime.

```bash
# run the whole suite (offline)
pytest

# include the doctests embedded in the modules, with a coverage report
pytest tests --doctest-modules src/nztcs_wiki_bot --cov=nztcs_wiki_bot --cov-report=term-missing

# lint
ruff check
```

There is **one** test that genuinely contacts Wikipedia, to catch real-world API
changes. It is **excluded by default** and only runs if you ask for it:

```bash
pytest -m live      # opt-in: makes a single real read-only request
```

---

## FAQ / troubleshooting

**Will this get my Wikipedia account in trouble?**
No. It never logs in and never edits — it only reads. See
[Is this safe?](#is-this-safe).

**It said `MaxLagExhausted`.**
Wikipedia's servers were busy and asked the tool to back off, and it gave up
after a few polite retries. Just run it again later; cached results mean it
picks up where it left off.

**A species I expected isn't in `matched.md`.**
Check the other buckets. It's probably in `skipped.tsv` (undescribed/quoted
name), `no_match.tsv` (no article), `unmapped.tsv` (unrecognised status), or
`ambiguous.md` (article found but needs a human).

**I changed the CSV / want fresh data.**
Delete the `cache/` folder and run again.

**Re-running produces the same edits — is that a bug?**
No, that's intended. The patcher is idempotent: a species that's already been
patched produces no further change.

---

## License

MIT — see [LICENSE](LICENSE).
