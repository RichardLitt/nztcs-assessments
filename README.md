# nztcs-wiki-bot

Add **New Zealand Threat Classification System (NZTCS)** conservation statuses
to Wikipedia species articles, from the Department of Conservation's published
assessments.

Most New Zealand species articles on Wikipedia have an infobox (a
"Speciesbox") but no NZTCS status, the official New Zealand government
assessment. Even the flagship
[Pūriri moth](https://en.wikipedia.org/wiki/P%C5%ABriri_moth) is missing one.
This tool takes an NZTCS report and, for each species, finds the Wikipedia
article, checks it's the right one, and prepares the exact change.

## Two ways to use it

| | Option 1: the bot | Option 2: manual files |
|---|---|---|
| **What it does** | Shows you each change and saves it to Wikipedia from your account when you press `y`. | Writes every change to files on your computer. You paste each one into Wikipedia yourself. |
| **You need** | A Wikipedia account and a [bot password](#one-time-setup-a-bot-password) | A Wikipedia account |
| **Commands** | `nztcs-wiki-bot --csv …`, then `nztcs-wiki-bot apply` | `nztcs-wiki-bot --csv …` |
| **Per article** | Seconds: read the change, press a key | A few minutes: open, edit, paste, preview, save |
| **Guide** | [Option 1](#option-1-save-edits-with-the-bot) · [docs/assisted-editing.md](docs/assisted-editing.md) | [Option 2](#option-2-make-files-and-edit-by-hand) · [docs/reviewing-output.md](docs/reviewing-output.md) |

Both start the same way: the review run reads the report and Wikipedia and
writes the proposed changes to `review/`. Option 2 stops there. Option 1 then
reads those files and saves the changes for you.

Either way, every edit is reviewed by you and made from your account, so you're
responsible for it, just as if you'd typed it. The bot asks before every save,
which makes it *assisted editing*: it doesn't need Wikipedia's bot approval.

## Is this safe?

Yes, by design:

- **The review run is read-only.** Every request is a `GET` with
  `action=query`. The client refuses anything else, and a test checks every
  request a full run makes. It doesn't log in.
- **Only the bot (`apply`) edits, one confirmed edit at a time.** Writing lives
  in a separate module the review run never uses. It logs in with a limited
  bot password that you create and can revoke, re-checks each article before
  asking, and skips any that changed since your review run, so it can't
  overwrite someone else's edit.
- **Polite.** It follows Wikimedia's API etiquette: an identifying User-Agent,
  at most one request per second, `maxlag` backoff, batches of 50 titles, and an
  on-disk cache. The bot also waits at least 10 seconds between saves. Details
  are in [docs/wikipedia-policy.md](docs/wikipedia-policy.md).

## Install (both options)

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

## Get a report (both options)

```bash
nztcs-wiki-bot fetch 1176 --out lepidoptera.csv
```

`1176` is Lepidoptera 2025 (507 moths and butterflies), and the default if you
give no ID. To find other reports, see
[docs/adding-a-report.md](docs/adding-a-report.md).

## Option 1: Save edits with the bot

### One-time setup: a bot password

The bot logs in with a *bot password*: a separate, limited password for your
own account, not your main one.

1. Logged in to Wikipedia, open
   [Special:BotPasswords](https://en.wikipedia.org/wiki/Special:BotPasswords).
2. Enter a bot name, such as `nztcs`, and click **Create**.
3. Tick only the **Edit existing pages** grant, then click **Create**.
4. Copy the password it shows (it isn't shown again). Your username for the bot
   is `YourName@nztcs`.

```bash
export NZTCS_BOT_USERNAME=YourName@nztcs
```

The bot asks for the password with a hidden prompt each time. To stop it using
your account, delete the bot password on the same page.

Optionally, create the page `User:YourName/nztcs-wiki-bot` explaining the tool
(there's a draft in [docs/assisted-editing.md](docs/assisted-editing.md#a-page-explaining-the-tool)).
Edit summaries link to it once it exists, so other editors can see what made
the edit and who to ask.

### Each session

```bash
rm -rf cache                                  # so the changes match the live articles
nztcs-wiki-bot --csv lepidoptera.csv          # the review run: a few minutes
nztcs-wiki-bot apply --limit 10               # save edits, confirming each one
```

On your first session, use `--limit 1` and check the saved edit on Wikipedia
before doing more.

### What you see

For each article, the whole infobox as it will be after the edit, with added
lines marked `+` and removed lines `-`:

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
| `n` | Skip it. Skips are remembered, so it won't be shown in later sessions (see `--show-skipped`). |
| `d` | Show the full diff, then ask again. |
| `o` | Open the article in your browser, then ask again. |
| `q` | Stop. Saved edits stay saved; the next session carries on. |

If the article's text also describes a conservation status ("In 2017 the
Department of Conservation classified it as…"), the bot shows that sentence
first and says whether it matches. It only changes the infobox, so fix the text
yourself if it doesn't.

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

It stops by itself when you get a new message on your talk page (someone may
be asking you to pause), when it has asked about `--limit` entries, or at the
end of the list. Every outcome is logged to `review/applied.tsv`, with the
revision ID for each save.

### Pace

Keep a human pace and read each change. Many fast, near-identical edits can
draw the same scrutiny as an unapproved bot, even when you approve each one
([WP:MEATBOT](https://en.wikipedia.org/wiki/Wikipedia:Bot_policy#Bot-like_editing)).
A few dozen edits a session, spread over days, is safer than hundreds in an
afternoon. If anyone raises a concern on your talk page, stop and reply first.

### Bot options

```
nztcs-wiki-bot apply [--review DIR] [--username NAME] [--limit N] [--species TEXT]
                     [--interval SECONDS] [--show-skipped] [--tool-page PAGE] [--contact TEXT]
```

| Option | Default | Meaning |
|---|---|---|
| `--review DIR` | `review` | The review folder to read `matched.jsonl` from and log to. |
| `--username NAME` | `$NZTCS_BOT_USERNAME`, or asks | Your bot password username, e.g. `YourName@nztcs`. The password comes from a hidden prompt (or `$NZTCS_BOT_PASSWORD`). |
| `--limit N` | *(none)* | Stop after asking about `N` entries. Entries skipped without asking don't count. |
| `--species TEXT` | *(none)* | Only entries whose name contains `TEXT`. |
| `--interval SECONDS` | `10` | Minimum gap between saves (at least 5). |
| `--show-skipped` | off | Also show entries you skipped in earlier sessions. |
| `--tool-page PAGE` | `User:<you>/nztcs-wiki-bot` | Page that edit summaries link to, once it exists. |
| `--contact TEXT` | `$NZTCS_BOT_CONTACT` | Your email or contact URL for the User-Agent. |

The full guide is [docs/assisted-editing.md](docs/assisted-editing.md).

## Option 2: Make files and edit by hand

### Make the files

```bash
rm -rf cache                                  # so the changes match the live articles
nztcs-wiki-bot --csv lepidoptera.csv
```

This takes a few minutes, because it's deliberately rate-limited. To try it on
a few species first, add `--limit 5`, or `--species Aenetus` for one genus.

### What you get

Everything goes into `review/` (change it with `--out`). Every row of the
report ends up in exactly one place:

| File | What's in it |
|---|---|
| `matched.md` | **The edits to make.** Confident matches, each with the lines to paste and where. Open this one. |
| `matched.jsonl` | The same, as data. The bot (Option 1) reads this. |
| `ambiguous.md` / `.jsonl` | An article was found but needs your eyes: no infobox, an infobox for a different taxon, or the status is already current. |
| `unmapped.tsv` | No Wikipedia code for this status: not assessed, a category Wikipedia can't display (e.g. Vagrant), or a title the tool has never seen. |
| `no_match.tsv` | No Wikipedia article for that name. |
| `skipped.tsv` | Names skipped before lookup: undescribed (`sp. A`), quoted genus, `cf.`/`aff.`, subspecies, and `s.l.`/`s.s.` concepts. A subspecies' status never goes on the species article. |
| `stats.txt` | Tallies, including `filtered` rows left out by `--species`/`--limit`. `balanced True` means every row was accounted for. |

### What an entry looks like

Each entry in `matched.md` gives plain wikitext to copy, with no diff markers,
and says where it goes:

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

<details>
<summary>Full diff</summary>
…
</details>
````

For an article that already has an NZTCS status, the entry says **Replace this
line: … with: …** instead. The patch action tells you which kind it is:

| Patch action | Meaning |
|---|---|
| `insert` | The infobox has no status. Three lines are added. |
| `update` | The infobox already has an NZTCS status. The code and/or reference change. |
| `add_secondary` | The infobox already shows another system (usually IUCN). NZTCS is added alongside as `status2`, `status2_system`, `status2_ref`. |

### Making an edit

1. **Check the match.** Click the article link in the heading and confirm it's
   about this species. For `update` entries, skip it if the article already
   cites a newer NZTCS report.
2. **Edit the source.** Click **Edit source** (not the visual editor). Find the
   line the entry names (for example `| genus = Aenetus`), put your cursor at
   the start of it, and paste the block. For a replace, swap the whole line.
3. **Check the citation.** For known reports it's complete and needs nothing.
   If it contains a `TODO` marker, fill in the authors and series number first,
   and never save with the marker in place.
4. **Preview.** The infobox should show an NZTCS status with *(NZ TCS)* beside
   it, and the reference should render without red error text. If you see
   ***Invalid status***, don't save.
5. **Save** with a clear edit summary, such as
   `Add NZTCS conservation status (Lepidoptera 2025, Hoare et al. 2026)`.
   Don't tick **This is a minor edit**.

The step-by-step guide, including the other files, is
[docs/reviewing-output.md](docs/reviewing-output.md).

### Keeping the files fresh

The files reflect the articles at the time of the run. Before an editing
session on a later day, run `rm -rf cache` and the review again. Articles
you've already edited then move to `ambiguous` as `already-current`.

### Review run options

```
nztcs-wiki-bot --csv PATH [--contact TEXT] [--out DIR] [--cache DIR] [--limit N] [--species TEXT]
nztcs-wiki-bot fetch [REPORT_ID] [--out PATH]
```

| Option | Default | Meaning |
|---|---|---|
| `--csv PATH` | *(required)* | The NZTCS report CSV to process. |
| `--contact TEXT` | `$NZTCS_BOT_CONTACT` | Your email or contact URL for the User-Agent. Required. |
| `--out DIR` | `review` | Where to write the files. |
| `--cache DIR` | `cache` | Where to cache Wikipedia responses. Delete it to force fresh fetches. |
| `--limit N` | *(none)* | Process at most `N` species (after skips). |
| `--species TEXT` | *(none)* | Only species whose name contains `TEXT`, e.g. `Aenetus`. |

`fetch` downloads report `REPORT_ID` (default `1176`) from nztcs.org.nz to
`--out` (default `nztcs_report_<id>_<date>.csv`).

## Citations

Both options use the same citation. It's `{{CiteQ}}`, which builds the full
reference (authors, title, series, link) from the report's Wikidata item,
under the ref name most articles already use (`NZTCS2025` for Lepidoptera
2025). If an article already cites the report, its existing citation is reused.
For a report the tool doesn't know yet, the citation is a scaffold with a TODO
to fill in by hand, and the bot won't save it. See
[docs/adding-a-report.md](docs/adding-a-report.md#adding-a-reports-citation)
to add one.

## Documentation

- [docs/assisted-editing.md](docs/assisted-editing.md): Option 1, saving edits with the bot.
- [docs/reviewing-output.md](docs/reviewing-output.md): Option 2, applying the files by hand.
- [docs/adding-a-report.md](docs/adding-a-report.md): finding and running other NZTCS reports, and adding their citations.
- [docs/nztcs-status-codes.md](docs/nztcs-status-codes.md): how statuses map to Speciesbox codes, and why some don't.
- [docs/wikipedia-policy.md](docs/wikipedia-policy.md): how the tool follows Wikimedia's rules.
- [docs/design.md](docs/design.md): architecture and design decisions.

## FAQ

**A species I expected isn't in `matched.md`.** Check the other files. Each
row lands in exactly one, with a reason.

**The bot says an article "changed since your run".** Someone edited it after
your review run, so the prepared change might overwrite theirs. Run
`rm -rf cache` and the review again, then `apply`.

**I saved an edit I shouldn't have.** Open it from the article's history (the
bot's log, `review/applied.tsv`, has the revision ID:
`https://en.wikipedia.org/w/index.php?diff=<revid>`) and click **undo**. If
it's still the latest edit, the undo applies cleanly.

**I want the bot to show entries I skipped.** `nztcs-wiki-bot apply
--show-skipped`. To forget all skips, delete `review/applied.tsv` (which also
clears the log).

**The bot's login failed.** Check the username is `YourName@botname`, exactly
as shown on Special:BotPasswords, and that the bot password has the **Edit
existing pages** grant. Bot passwords can be reset on the same page.

**I pasted an edit by hand but the species is still in `matched.md`.** The run
used cached wikitext from before your edit. Delete `cache/` and run again: an
up-to-date article moves to `ambiguous` as `already-current`.

**It said `MaxLagExhausted`.** Wikipedia's servers were busy. Run it again
later. Cached results mean it picks up where it left off.

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
