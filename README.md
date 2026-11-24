# nztcs-wiki-bot

Prepare ready-to-paste Wikipedia edits that add **New Zealand Threat
Classification System (NZTCS)** conservation statuses to species articles.

Most New Zealand species articles on Wikipedia have an infobox (a
"Speciesbox") but no NZTCS status, the official New Zealand government
assessment. Even the flagship
[Pūriri moth](https://en.wikipedia.org/wiki/P%C5%ABriri_moth) is missing one.
This tool takes an NZTCS report and, for each species, finds the Wikipedia article,
checks it's the right one, and writes the exact wikitext change as a diff.

> **It does not edit Wikipedia.** It only reads Wikipedia and writes proposed
> edits to files on your computer. You review each one and paste it in by hand.

## Is this safe?

Yes, by design:

- **Read-only.** Every request is a `GET` with `action=query`. The client
  refuses anything else, and a test checks every request a full run makes.
- **No login.** There is no login code and nowhere to put a password or token.
  To Wikipedia, this is an anonymous reader. It cannot touch your account.
- **Polite.** It follows Wikimedia's API etiquette: an identifying User-Agent,
  at most one request per second, `maxlag` backoff, batches of 50 titles, and an
  on-disk cache. Details are in [docs/wikipedia-policy.md](docs/wikipedia-policy.md).

The worst a run can do is earn your IP a temporary, anonymous rate-limit.

## Install

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
nztcs-wiki-bot --help
```

## Set your contact info

Wikimedia asks every automated reader to include **working** contact details
in its User-Agent, so they can reach you instead of blocking you. The tool
won't run without them:

```bash
export NZTCS_BOT_CONTACT=you@example.org     # or pass --contact each run
```

An email address or a reachable URL (such as your Wikipedia user page) both work.

## Quickstart

```bash
# 1. Download a report. 1176 = Lepidoptera 2025, 507 moths and butterflies.
nztcs-wiki-bot fetch 1176 --out lepidoptera.csv

# 2. Try a handful of species first.
nztcs-wiki-bot --csv lepidoptera.csv --limit 5

# 3. Open review/matched.md. When you're happy, run the whole file.
nztcs-wiki-bot --csv lepidoptera.csv
```

A full run takes a few minutes because it is deliberately rate-limited.
Re-runs are fast, because responses are cached in `cache/`. To find other
reports, see [docs/adding-a-report.md](docs/adding-a-report.md).

## Understanding the output

Everything goes into `review/` (change it with `--out`). Every input row ends up
in exactly one bucket:

| File | What's in it |
|---|---|
| `matched.md` / `.jsonl` | **Start here.** Confident matches, each with a diff to paste. |
| `ambiguous.md` / `.jsonl` | An article was found but needs your eyes: no infobox, an infobox for a different taxon, or the status is already current. |
| `unmapped.tsv` | No Wikipedia code for this status: not assessed, a category Wikipedia can't display (e.g. Vagrant), or a title the tool has never seen. |
| `no_match.tsv` | No Wikipedia article for that name. |
| `skipped.tsv` | Undescribed (`sp. A`) or quoted-genus names, skipped before lookup. |
| `stats.txt` | Tallies, including `filtered` rows left out by `--species`/`--limit`. `balanced True` means every row was accounted for. |

Each entry in `matched.md` looks like this:

````markdown
## Aenetus virescens → Pūriri moth

- **Common name:** pūriri moth
- **NZTCS status:** `NT`
- **Patch action:** insert

```diff
 | image = Aenetus virescens.jpg
+| status = NT
+| status_system = NZTCS
+| status_ref = <ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>
 | genus = Aenetus
```
````

To apply one, open the article, click **Edit source**, add the `+` lines to the
infobox, preview, and save. For reports the bot knows, the citation is complete:
`{{CiteQ}}` builds it from the report's Wikidata item. For any other report it's
a scaffold with a TODO marker you fill in before saving. The full
walkthrough is in [docs/reviewing-output.md](docs/reviewing-output.md). You are
the editor of record, not the bot.

## Command-line options

```
nztcs-wiki-bot --csv PATH [--contact TEXT] [--out DIR] [--cache DIR] [--limit N] [--species TEXT]
nztcs-wiki-bot fetch [REPORT_ID] [--out PATH]
```

| Option | Default | Meaning |
|---|---|---|
| `--csv PATH` | *(required)* | The NZTCS report CSV to process. |
| `--contact TEXT` | `$NZTCS_BOT_CONTACT` | Your email or contact URL for the User-Agent. Required. |
| `--out DIR` | `review` | Where to write the review files. |
| `--cache DIR` | `cache` | Where to cache Wikipedia responses. Delete it to force fresh fetches. |
| `--limit N` | *(none)* | Process at most `N` species (after skips). |
| `--species TEXT` | *(none)* | Only species whose name contains `TEXT`, e.g. `Aenetus`. |

## Documentation

- [docs/reviewing-output.md](docs/reviewing-output.md): applying patches to Wikipedia, step by step.
- [docs/adding-a-report.md](docs/adding-a-report.md): finding and running other NZTCS reports.
- [docs/nztcs-status-codes.md](docs/nztcs-status-codes.md): how statuses map to Speciesbox codes, and why some don't.
- [docs/wikipedia-policy.md](docs/wikipedia-policy.md): how the tool follows Wikimedia's API rules.
- [docs/design.md](docs/design.md): architecture and design decisions.

## FAQ

**A species I expected isn't in `matched.md`.** Check the other buckets.
Each row lands in exactly one, with a reason.

**It said `MaxLagExhausted`.** Wikipedia's servers were busy. Run it again
later. Cached results mean it picks up where it left off.

**I already pasted an edit but the species is still in `matched.md`.** The run
used cached wikitext from before your edit. Delete `cache/` and run again: an
up-to-date article moves to `ambiguous` as `already-current`.

## Contributing

Bug reports and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
The offline suite is the quick check:

```bash
ruff check && pyright && pytest
```

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Data

Assessment data comes from the [NZTCS database](https://nztcs.org.nz), maintained
by the New Zealand Department of Conservation. This repository doesn't
redistribute report CSVs: `nztcs-wiki-bot fetch` downloads them on demand.
Cite the original NZTCS report, as the generated `status_ref` does.

## License

MIT. See [LICENSE](LICENSE).
