# nztcs-wiki-bot

Add **New Zealand Threat Classification System (NZTCS)** conservation statuses
to Wikipedia species articles, from the Department of Conservation's published
assessments.

Most New Zealand species articles on Wikipedia have an infobox (a
"Speciesbox") but no NZTCS status, the official New Zealand government
assessment. Even the flagship
[Pūriri moth](https://en.wikipedia.org/wiki/P%C5%ABriri_moth) is missing one.
This tool takes an NZTCS report and, for each species, finds the Wikipedia
article, checks it's the right one, and prepares the exact change. You then
review each change and save it, from your own account.

## How it works

It's two steps:

1. **Review run** (`nztcs-wiki-bot --csv …`). Reads the report and Wikipedia,
   and writes the proposed edits to files on your computer (`review/`). It's
   read-only: it never logs in or edits anything.
2. **Save the edits**, either:
   - **with `nztcs-wiki-bot apply`**: it shows you each article's infobox with
     the change marked, and saves it from your account when you press `y`.
     Nothing is saved without a `y`.
   - **by hand**: copy the block from `review/matched.md` into the article.

Because you approve every edit, this is *assisted editing*, not a bot, and
doesn't need Wikipedia's bot approval. You're responsible for each edit, just
as if you'd made it by hand.

## Is this safe?

Yes, by design:

- **The review run is read-only.** Every request is a `GET` with
  `action=query`. The client refuses anything else, and a test checks every
  request a full run makes. It doesn't log in.
- **Edits only happen in `apply`, one confirmed edit at a time.** Writing lives
  in a separate module that the review run never uses. `apply` logs in with a
  limited [bot password](https://en.wikipedia.org/wiki/Special:BotPasswords)
  that you create and can revoke. It re-checks each article before asking, and
  skips any that changed since your run, so it can't overwrite someone else's
  edit.
- **Polite.** It follows Wikimedia's API etiquette: an identifying User-Agent,
  at most one request per second, `maxlag` backoff, batches of 50 titles, and an
  on-disk cache. `apply` also waits at least 10 seconds between saves. Details
  are in [docs/wikipedia-policy.md](docs/wikipedia-policy.md).

## Install

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
nztcs-wiki-bot --help
```

Wikimedia asks every automated reader to include **working** contact details,
so they can reach you instead of blocking you. The tool won't run without them:

```bash
export NZTCS_BOT_CONTACT=you@example.org     # or pass --contact each run
```

An email address or a reachable URL (such as your Wikipedia user page) both
work.

## Quickstart

```bash
# 1. Download a report. 1176 = Lepidoptera 2025, 507 moths and butterflies.
nztcs-wiki-bot fetch 1176 --out lepidoptera.csv

# 2. Run the review. Takes a few minutes; it's deliberately rate-limited.
nztcs-wiki-bot --csv lepidoptera.csv

# 3. Save edits, confirming each one. Start small.
export NZTCS_BOT_USERNAME=YourName@nztcs     # see "One-time setup" below
nztcs-wiki-bot apply --limit 5
```

Check your first few saved edits on Wikipedia before doing more. To find other
reports, see [docs/adding-a-report.md](docs/adding-a-report.md).

## Saving edits with `apply`

### One-time setup: a bot password

`apply` logs in with a *bot password*: a separate, limited password for your
own account, not your main one.

1. Logged in to Wikipedia, open
   [Special:BotPasswords](https://en.wikipedia.org/wiki/Special:BotPasswords).
2. Enter a bot name, such as `nztcs`, and click **Create**.
3. Tick only the **Edit existing pages** grant, then click **Create**.
4. Copy the password it shows (it isn't shown again). Your username for `apply`
   is `YourName@nztcs`.

Set `NZTCS_BOT_USERNAME=YourName@nztcs`. `apply` asks for the password with a
hidden prompt each time. To stop the tool using your account, delete the bot
password on the same page.

Optionally, create the page `User:YourName/nztcs-wiki-bot` explaining the tool
(there's a draft in [docs/assisted-editing.md](docs/assisted-editing.md#a-page-explaining-the-tool)).
Edit summaries link to it once it exists, so other editors can see what made
the edit and who to ask.

### Each session

Re-run the review first, so the proposed edits match the live articles, then
start `apply`:

```bash
rm -rf cache
nztcs-wiki-bot --csv lepidoptera.csv
nztcs-wiki-bot apply --limit 10
```

For each article, you see the whole infobox as it will be after the edit,
with added lines marked `+` and removed lines `-`:

```
[3/212] Aenetus virescens → Pūriri moth
https://en.wikipedia.org/wiki/P%C5%ABriri_moth
NZTCS status: NT (Not Threatened) · insert

Infobox after this edit (+ added, - removed):

    {{Speciesbox
    | name = Pūriri moth
    | image = Puriri moth-05.jpg
  + | status = NT
  + | status_system = NZTCS
  + | status_ref = <ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>
    | genus = Aenetus
    | species = virescens
    | authority = ([[Edward Doubleday|Doubleday]], 1843)
    }}

Save this edit? [y]es [n]o [d]iff [o]pen [q]uit:
```

| Key | Does |
|---|---|
| `y` | Save the edit. |
| `n` | Skip it. Skips are remembered, so it won't be shown again (see `--show-skipped`). |
| `d` | Show the full diff, then ask again. |
| `o` | Open the article in your browser, then ask again. |
| `q` | Stop. Saved edits stay saved; the next session carries on. |

If the article's text also describes a conservation status ("In 2017 the
Department of Conservation classified it as…"), `apply` shows that sentence
first and says whether it matches. The tool only changes the infobox, so fix
the text yourself if it doesn't.

### What it skips without asking

| Outcome | Why |
|---|---|
| `changed` | The article was edited after your review run. Re-run the review to refresh it. |
| `already-applied` | The change is already there. |
| `nobots` | The article opts out with `{{nobots}}` or `{{bots}}`. |
| `needs-citation` | The citation still has a TODO (a report the tool doesn't know yet). |
| `missing` | The article no longer exists. |

These don't count towards `--limit`. Neither do entries you skipped in an
earlier session.

### It stops by itself when

- you get a new message on your talk page (someone may be asking you to pause);
- it has asked about `--limit` entries;
- it reaches the end of the list.

Every outcome is logged to `review/applied.tsv`, with the revision ID for each
save (`https://en.wikipedia.org/w/index.php?diff=<revid>` shows the edit).

### Pace

Keep a human pace and read each change. Many fast, near-identical edits can
draw the same scrutiny as an unapproved bot, even when you approve each one
([WP:MEATBOT](https://en.wikipedia.org/wiki/Wikipedia:Bot_policy#Bot-like_editing)).
A few dozen edits a session, spread over days, is safer than hundreds in an
afternoon. If anyone raises a concern on your talk page, stop and reply first.

More detail: [docs/assisted-editing.md](docs/assisted-editing.md).

## Understanding the output

The review run writes everything to `review/` (change it with `--out`). Every
row of the report ends up in exactly one bucket:

| File | What's in it |
|---|---|
| `matched.md` / `.jsonl` | **The edits.** Confident matches, each with the lines to paste and where, plus the full diff. `apply` reads `matched.jsonl`. |
| `ambiguous.md` / `.jsonl` | An article was found but needs your eyes: no infobox, an infobox for a different taxon, or the status is already current. |
| `unmapped.tsv` | No Wikipedia code for this status: not assessed, a category Wikipedia can't display (e.g. Vagrant), or a title the tool has never seen. |
| `no_match.tsv` | No Wikipedia article for that name. |
| `skipped.tsv` | Names skipped before lookup: undescribed (`sp. A`), quoted genus, `cf.`/`aff.`, subspecies, and `s.l.`/`s.s.` concepts. A subspecies' status never goes on the species article. |
| `stats.txt` | Tallies, including `filtered` rows left out by `--species`/`--limit`. `balanced True` means every row was accounted for. |
| `applied.tsv` | Written by `apply`: what you saved and skipped. The review run never touches it. |

Citations use `{{CiteQ}}`, which builds the full reference from the report's
Wikidata item, under the ref name most articles already use (`NZTCS2025` for
Lepidoptera 2025). If an article already cites the report, its existing
citation is reused. For a report the tool doesn't know yet, the citation is a
scaffold with a TODO to fill in, and `apply` won't save it.

### Applying by hand

Each entry in `matched.md` gives plain wikitext to copy, and where it goes:

````markdown
## Aenetus virescens → Pūriri moth

- **Common name:** pūriri moth
- **NZTCS status:** `NT`
- **Patch action:** insert

**Add** these lines directly above `| genus = Aenetus`:

```wikitext
| status = NT
| status_system = NZTCS
| status_ref = <ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>
```
````

Open the article, click **Edit source**, paste the block where the entry says,
preview, and save. The walkthrough is in
[docs/reviewing-output.md](docs/reviewing-output.md).

## Command-line options

```
nztcs-wiki-bot --csv PATH [--contact TEXT] [--out DIR] [--cache DIR] [--limit N] [--species TEXT]
nztcs-wiki-bot apply [--review DIR] [--username NAME] [--limit N] [--species TEXT]
                     [--interval SECONDS] [--show-skipped] [--tool-page PAGE] [--contact TEXT]
nztcs-wiki-bot fetch [REPORT_ID] [--out PATH]
```

**Review run:**

| Option | Default | Meaning |
|---|---|---|
| `--csv PATH` | *(required)* | The NZTCS report CSV to process. |
| `--contact TEXT` | `$NZTCS_BOT_CONTACT` | Your email or contact URL for the User-Agent. Required. |
| `--out DIR` | `review` | Where to write the review files. |
| `--cache DIR` | `cache` | Where to cache Wikipedia responses. Delete it to force fresh fetches. |
| `--limit N` | *(none)* | Process at most `N` species (after skips). |
| `--species TEXT` | *(none)* | Only species whose name contains `TEXT`, e.g. `Aenetus`. |

**`apply`:**

| Option | Default | Meaning |
|---|---|---|
| `--review DIR` | `review` | The review folder to read `matched.jsonl` from and log to. |
| `--username NAME` | `$NZTCS_BOT_USERNAME`, or asks | Your bot password username, e.g. `YourName@nztcs`. The password comes from a hidden prompt (or `$NZTCS_BOT_PASSWORD`). |
| `--limit N` | *(none)* | Stop after asking about `N` entries. Entries skipped without asking don't count. |
| `--species TEXT` | *(none)* | Only entries whose name contains `TEXT`. |
| `--interval SECONDS` | `10` | Minimum gap between saves (at least 5). |
| `--show-skipped` | off | Also show entries you skipped in earlier sessions. |
| `--tool-page PAGE` | `User:<you>/nztcs-wiki-bot` | Page that edit summaries link to, once it exists. |
| `--contact TEXT` | `$NZTCS_BOT_CONTACT` | As for the review run. |

**`fetch`:** downloads report `REPORT_ID` (default `1176`) from nztcs.org.nz
to `--out` (default `nztcs_report_<id>_<date>.csv`).

## Documentation

- [docs/assisted-editing.md](docs/assisted-editing.md): saving edits with `apply`, in full.
- [docs/reviewing-output.md](docs/reviewing-output.md): checking and applying edits by hand.
- [docs/adding-a-report.md](docs/adding-a-report.md): finding and running other NZTCS reports, and adding their citations.
- [docs/nztcs-status-codes.md](docs/nztcs-status-codes.md): how statuses map to Speciesbox codes, and why some don't.
- [docs/wikipedia-policy.md](docs/wikipedia-policy.md): how the tool follows Wikimedia's rules.
- [docs/design.md](docs/design.md): architecture and design decisions.

## FAQ

**A species I expected isn't in `matched.md`.** Check the other buckets. Each
row lands in exactly one, with a reason.

**`apply` says an article "changed since your run".** Someone edited it after
your review run, so the prepared edit might overwrite theirs. Run
`rm -rf cache` and the review again, then `apply`.

**I saved an edit I shouldn't have.** Open the edit
(`https://en.wikipedia.org/w/index.php?diff=<revid>`, with the revid from
`review/applied.tsv`) and click **undo**. If it's still the latest edit, the
undo applies cleanly.

**I want to see the entries I skipped.** `nztcs-wiki-bot apply --show-skipped`.
To forget all skips, delete `review/applied.tsv` (which also clears the log).

**Login failed.** Check the username is `YourName@botname`, exactly as shown on
Special:BotPasswords, and that the bot password has the **Edit existing pages**
grant. Bot passwords can be reset on the same page.

**It said `MaxLagExhausted`.** Wikipedia's servers were busy. Run it again
later. Cached results mean it picks up where it left off.

**I pasted an edit by hand but the species is still in `matched.md`.** The run
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
