# Reviewing output and applying patches

The bot never edits Wikipedia. You do, one article at a time. This guide covers
turning an entry in `review/matched.md` into a saved Wikipedia edit.

## Before you start

- You need a Wikipedia account. Anonymous edits work, but an account gives you a
  history and a talk page where other editors can reach you.
- Work from a **fresh run**. Wikipedia articles change. If `cache/` is more than
  a day or two old, delete it and re-run so the diffs match the live articles.

## For each entry in `matched.md`

Each entry has a heading (`binomial → article`), the NZTCS status code, the
patch action, and a unified diff:

| Patch action | Meaning |
|---|---|
| `insert` | The infobox had no status. Three lines are added: `status`, `status_system`, `status_ref`. |
| `update` | The infobox already had an NZTCS status. The code and/or reference change. |
| `add_secondary` | The infobox already shows another system (usually IUCN). NZTCS is added alongside as `status2`, `status2_system`, `status2_ref`, leaving the IUCN status untouched. |

### 1. Sanity-check the match

Click the article link in the heading. Confirm the article really is about this
species. The bot has already checked that the infobox's genus and species match,
but you're the last line of defence against a mislabelled infobox.

For `update` entries, look at the existing reference first. If the article
already cites a **newer** NZTCS report than yours, skip the entry.

### 2. Edit the source

Click **Edit source** (not the visual editor). The infobox is near the top:
`{{Speciesbox`, or occasionally `{{Taxobox}}`, `{{Subspeciesbox}}` or
`{{Automatic taxobox}}`.

Make the change shown in the diff: add the `+` lines and remove the `-` lines.
Lines starting with a space are context, so leave them as they are. Where you put the new
lines inside the template doesn't affect rendering. The bot places them after
`authority` to match the template documentation's order.

### 3. Check the citation

For reports the bot knows (listed in
[`src/nztcs_wiki_bot/reports.py`](../src/nztcs_wiki_bot/reports.py)), the
citation is already complete:

```
<ref name="Hoare2026">{{CiteQ|Q139379012}}</ref>
```

`{{CiteQ}}` builds the full reference (authors, title, series, number, link)
from the report's Wikidata item, the same way other articles cite it. There's
nothing to fill in. In the preview, check that the reference renders with
authors and a title.

If the article already cites the report, the bot reuses that citation's name
and emits only `<ref name="..." />`. Again, there's nothing to complete.

#### Other reports: complete the scaffold

For a report not in that list, the generated `status_ref` is a **scaffold**. The
NZTCS CSV doesn't include the author list or series number, so the reference
contains a visible marker:

```
| author = <!-- TODO: complete author list and series number before saving -->
```

Look up the report on [nztcs.org.nz](https://nztcs.org.nz) or the Department of
Conservation's publications page. Replace the marker with the authors, and add
the series number to `series`. The result has this shape:

```
| author = Hoare, R. J. B.; <other authors as listed on the report>
| series = New Zealand Threat Classification Series <number>
```

Never save with the TODO marker still in place. Better still, add the report to
`reports.py` (see [adding-a-report.md](adding-a-report.md#citations-for-other-reports))
and re-run, so every article gets a complete citation.

### 4. Preview

Click **Show preview**. The infobox should now show an NZTCS badge (such as
"Not Threatened" or "Nationally Vulnerable") with *(NZ TCS)* beside it. If you
see ***Invalid status***, don't save. Please
[open an issue](https://github.com/RichardLitt/nztcs-assessments/issues).

Check the References section too. The new citation should appear there and
render without red error text.

### 5. Save

Use a clear edit summary, for example:

> Add NZTCS conservation status (Lepidoptera 2025, Hoare et al. 2026)

Don't tick **This is a minor edit**: adding or changing a sourced status is a
content change.

## The other buckets

- **`ambiguous.md`**: worth a look. An article whose `reason` is `no-speciesbox`
  may still be the right article, just without an infobox. You can add one by
  hand following [Template:Speciesbox](https://en.wikipedia.org/wiki/Template:Speciesbox).
  `taxon-mismatch` usually means the name redirects to a genus or a different
  species. `already-current` needs nothing.
- **`no_match.tsv`**: no article exists. That's a candidate for a new article,
  but not this tool's job.
- **`unmapped.tsv`**: there's no Wikipedia code to add. See
  [nztcs-status-codes.md](nztcs-status-codes.md).
- **`skipped.tsv`**: names that can't be matched as written.

## Doing a lot of these

Pasting many near-identical edits by hand is exactly what Wikipedia's bot
policy is designed around. If you find yourself doing dozens a day, read
[WP:MEATBOT](https://en.wikipedia.org/wiki/Wikipedia:Bot_policy#Bot-like_editing).
Bot-like editing at high speed can draw the same scrutiny as an unapproved bot,
even if every edit is manual. Take your time, and review each diff properly.
