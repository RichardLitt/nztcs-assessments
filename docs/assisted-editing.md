# Saving edits with `apply` (assisted editing)

`nztcs-wiki-bot apply` saves the patches from a review run to Wikipedia, from
**your own account**, one at a time. For each entry it shows you the change and
waits. Nothing is saved unless you press `y`.

This is *assisted editing*, not a bot: you review and approve every edit, so it
doesn't need [bot approval](https://en.wikipedia.org/wiki/Wikipedia:Bots/Requests_for_approval).
You're still responsible for each edit, exactly as if you'd made it by hand.
Fully automatic editing, with no confirmation, would need a separate bot
account and approval first.

## One-time setup: a bot password

`apply` logs in with a *bot password*: a separate, limited password for your
account that you can revoke at any time. It's not your main password.

1. While logged in to Wikipedia, open
   [Special:BotPasswords](https://en.wikipedia.org/wiki/Special:BotPasswords).
2. Enter a bot name, for example `nztcs`, and click **Create**.
3. Under grants, tick only **Edit existing pages**. Leave the rest unticked.
4. Click **Create**. Wikipedia shows a username like `Richlitt@nztcs` and a
   long password. Copy the password now; it isn't shown again.

To stop the tool using your account, come back to the same page and delete or
reset the bot password.

## Running it

Do a fresh review run first, so the patches match the live articles:

```bash
rm -rf cache
nztcs-wiki-bot --csv nztcs_report_1176_20260505.csv
```

Then:

```bash
export NZTCS_BOT_USERNAME=Richlitt@nztcs
nztcs-wiki-bot apply
```

It asks for the password with a hidden prompt. You can also set
`NZTCS_BOT_PASSWORD`, but then it sits in your shell history and environment,
so the prompt is safer. `NZTCS_BOT_CONTACT` (or `--contact`) is still needed,
as for every run.

Useful options:

| Option | What it does |
|---|---|
| `--species TEXT` | Only entries whose name contains `TEXT`, e.g. `--species Ichneutica`. |
| `--limit N` | Look at the first `N` entries only. Good for a first try. |
| `--interval SECONDS` | Minimum gap between saves (default 10, minimum 5). |
| `--review DIR` | A review folder other than `review/`. |

## What you see for each entry

The whole infobox, as it will be after the edit. Added lines start with `+`
(green in a terminal), removed lines with `-` (red), and every other line is
shown unchanged. So you can see at a glance whether the infobox already has a
status, and what else is in it.

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

For an article that already has a status from another system, such as IUCN,
you'll see it unmarked, with the NZTCS lines added as `status2`. For an
update, the old line is shown with `-` and the new one with `+`. Set
`NO_COLOR=1` to turn the colours off.

| Key | Does |
|---|---|
| `y` | Save the edit. |
| `n` | Skip this one. |
| `d` | Show the full diff, then ask again. |
| `o` | Open the article in your browser, then ask again. |
| `q` | Stop. You can start again later; finished entries are skipped. |

The edit summary says what changed and that it was an assisted edit, for
example `Add NZTCS conservation status: Not Threatened (NT); assisted edit with
nztcs-wiki-bot`. Edits aren't marked minor.

## What it checks before asking

The live article is fetched again for every entry. It skips the entry, without
asking, if:

| Outcome | Why |
|---|---|
| `changed` | The article has been edited since your review run, so the patch could overwrite someone else's change. Re-run the tool to refresh. |
| `already-applied` | The change is already there, for example from an earlier `apply` session. |
| `nobots` | The article has `{{nobots}}`, or `{{bots}}` excludes you or the tool. |
| `needs-citation` | The citation still has the TODO marker (a report not in `reports.py`). |
| `missing` | The article no longer exists. |

When you press `y`, the save itself is also protected. It's sent with the
revision it was based on, so if someone edits the page in the seconds between
fetching and saving, Wikipedia refuses it as an edit conflict instead of
overwriting their change. It never creates pages, and it fails rather than edit
logged out.

## When it stops on its own

- **A talk-page message.** After each save, it checks whether you have a new
  message. If you do, it stops and gives you the link. Someone may be asking
  you to pause.
- **`q` or Ctrl-C.** Anything already saved stays saved and logged.

## The log

Every outcome is appended to `review/applied.tsv`: time, species ID, article,
outcome (`saved`, `skipped`, `changed`, `error:<code>`, …) and the new revision
ID for saves. To see a saved edit, open
`https://en.wikipedia.org/w/index.php?diff=<revid>`.

## When the article text also gives a status

The patch only changes the infobox. Many articles also say something like
"In 2017 the Department of Conservation classified it as Nationally
Vulnerable" in the text, which would then contradict a new infobox status.

When the article text has a sentence that mentions the NZTCS (or the
Department of Conservation) and a status name, `apply` shows it under the
infobox:

```
The article text also describes a conservation status:
  "In 2025 this species was classified as having the conservation threat
  classification of "At Risk, Uncommon" by the Department of Conservation."
Note: the text may not match the new status (Data Deficient). This tool only
changes the infobox, so open the article (o) and update the text yourself if
needed.
```

If every sentence it found names the new status, it says so instead. It shows
up to three sentences. Refs, comments and templates are ignored when looking.

## Pace

You can work faster with `apply` than by hand, but keep a human pace and
actually read each change. Many fast, near-identical edits can attract the same
scrutiny as an unapproved bot, even when you approve each one; see
[WP:MEATBOT](https://en.wikipedia.org/wiki/Wikipedia:Bot_policy#Bot-like_editing).
A few dozen edits in a session, spread over days, is safer than hundreds in an
afternoon. If anyone raises concerns on your talk page, stop and talk to them
first.
