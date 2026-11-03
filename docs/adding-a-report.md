# Running a different NZTCS report

NZTCS assessments are published as separate reports, one per taxon group per
assessment round (for example "Lepidoptera 2025" or "Birds 2021"). The bot works on
one report CSV at a time.

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
follows pagination for reports over 1000 species). It strips HTML italics from
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

## Citations for other reports

The generated `status_ref` is built from the report's `reportName` and
`reportYear` columns. For `Lepidoptera 2025 (Hoare et al. 2026)` that gives:

- ref name `NZTCS-Lepidoptera-2025`
- title *Conservation status of New Zealand Lepidoptera, 2025*
- date `2026`

This title is generated, so it may not match the published report's official
title word for word. Check it against the report while you fill in the authors. See
[reviewing-output.md](reviewing-output.md#3-complete-the-citation).
