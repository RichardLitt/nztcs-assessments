# Adding or running a different NZTCS report

NZTCS assessments are published as separate reports, one per taxon group per
assessment round (for example "Lepidoptera 2025" or "Birds 2021"). The bot works on
one report CSV at a time.

There are two separate things you might want to do:

- **Run the bot on another report.** You don't need to edit any files: follow
  steps 1 to 4.
- **Give that report a complete citation.** Add a few lines to a YAML file:
  see [Adding a report's citation](#adding-a-reports-citation). Without this,
  `apply` won't save the report's edits.

## 1. Find the report ID

1. Go to [nztcs.org.nz](https://nztcs.org.nz) and browse or search the reports.
2. Open the report you want and note its numeric ID. It appears in the page's
   URL. You can also see it in your browser's developer tools, as `reportId` in the
   request to `/rest/assessmentSearch`.

`1176` is Lepidoptera 2025 (Hoare et al. 2026), which is also the default if you
give no ID.

## 2. Download it

```bash
nztcs-wiki-bot fetch <report_id>                    # → nztcs_report_<id>_<YYYYMMDD>.csv
nztcs-wiki-bot fetch <report_id> --out birds.csv    # or choose the filename
```

This makes one or more read-only `POST` requests to the NZTCS search API (it
follows pagination for reports over 1000 species). It prints the name of the report it
downloaded. **Check that it's the one you meant**: the filename you choose has
no effect on what's downloaded. It also strips HTML italics from
names and writes the 12 columns the bot expects. Report CSVs are gitignored, so
fetch your own copy rather than committing it.

## 3. Run the bot

```bash
nztcs-wiki-bot --csv birds.csv --limit 10     # look at a few first
nztcs-wiki-bot --csv birds.csv                # then the whole report
```

Use a separate `--out` per report if you want to keep their review folders
apart, e.g. `--out review-birds`.

## 4. Check `unmapped.tsv`

A new taxon group can bring status titles the Lepidoptera report didn't have.
The bot never guesses. Any title it doesn't recognise goes to `unmapped.tsv`
with the reason `unknown-status-title`, and produces no patch.

If you see one:

1. Check whether Wikipedia can display it. The list of codes Wikipedia renders
   is in [nztcs-status-codes.md](nztcs-status-codes.md#codes-wikipedia-can-render).
2. If it can, add a line to `STATUS_CODES` in
   [`src/nztcs_wiki_bot/status_map.py`](../src/nztcs_wiki_bot/status_map.py).
   If it's a real category Wikipedia can't display, add it to
   `NO_WIKIPEDIA_CODE_TITLES`. If it isn't a status at all, add it to
   `NON_STATUS_TITLES`.
3. Add the title to `tests/fixtures/csv/all_status_titles.csv` (copy a real
   row from the report), run `pytest`, and open a pull request.

## Adding a report's citation

Reports with a complete citation, `{{CiteQ|<item>}}`, are listed in
[`src/nztcs_wiki_bot/reports.yaml`](../src/nztcs_wiki_bot/reports.yaml). For any
other report, the bot writes a `{{cite report}}` scaffold with a TODO marker
that you'd have to fill in by hand on every article, and `apply` won't save it.

### 1. Get a block to paste

Run the bot on the report's CSV. For each report with no entry, it prints a
warning with a block like this (you can stop the run with Ctrl+C once you've
copied it):

```yaml
"Hymenoptera 2014 (Ward et al. 2017)":
  wikidata: Q...
  ref_name: NZTCS2014
  url: https://...
```

Paste it at the end of `reports.yaml`. Keep the first line exactly as printed:
it's matched character for character against the CSV's `reportName` column.
Keep the two-space indent on the other lines.

### 2. Fill in `wikidata`

Search [Wikidata](https://www.wikidata.org) for the report's title or its PDF
link, and copy the item ID (`Q` followed by digits). Check that the item has the
authors, date, series and full-text URL, because `{{CiteQ}}` builds the citation
from them. If there's no item, you can create one
([WikiProject Source Metadata](https://www.wikidata.org/wiki/Wikidata:WikiProject_Source_Metadata)
lists the usual properties), or leave the report out and complete the scaffold
by hand.

### 3. Fill in `url`

The full-text link to the report, usually a PDF on `www.doc.govt.nz`. Use the
address listed on the Wikidata item (*full work available at URL*). The bot uses
it to recognise an article that already cites the report.

### 4. Check `ref_name`

Search Wikipedia for `insource:"Q<item>"`. If articles already cite the report,
use the name most of them use. For Lepidoptera 2025 that's `NZTCS2025` (81
articles in November 2026, against 16 for `Hoare2026` and 5 for `Hoare2025`).
Otherwise, keep the suggested `NZTCS<assessment year>`. The bot reuses whatever
name an individual article already has, so this name only matters for articles
that don't cite the report yet.

### 5. Run the bot again

```bash
nztcs-wiki-bot --csv birds.csv --limit 10
```

The warning should be gone, and the citations in `review/matched.md` should use
`{{CiteQ}}`. If the file has a mistake (a missing field, bad indentation, a
report listed twice), the run stops and says what's wrong. To share the new
entry, run `pytest` and open a pull request.

If you installed with `pip install -e` as in the
[README](../README.md#install-both-options), your changes to the file take
effect straight away.

### Without an entry

The scaffold is built from the `reportName` and `reportYear` columns, for
example ref name `NZTCS-Birds-2021` and title *Conservation status of New
Zealand Birds, 2021*. That title is generated, so it may not match the published
report's title word for word. See
[reviewing-output.md](reviewing-output.md#other-reports-complete-the-scaffold).
