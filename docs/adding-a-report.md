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

The bot gives a complete citation, `{{CiteQ|<item>}}`, only for reports listed
in `KNOWN_REPORTS` in
[`src/nztcs_wiki_bot/reports.py`](../src/nztcs_wiki_bot/reports.py). For
anything else it falls back to a `{{cite report}}` scaffold with a TODO marker
that every reviewer has to fill in by hand. Adding the report takes a few
minutes and saves that work on every article:

1. **Find the report's Wikidata item.** Search [Wikidata](https://www.wikidata.org)
   for the report's title or its PDF link. Check that the item has the authors,
   date, series and full-text URL. If there's no item, you can create one on
   Wikidata ([WikiProject Source Metadata](https://www.wikidata.org/wiki/Wikidata:WikiProject_Source_Metadata)
   lists the usual properties), or skip this section and use the scaffold.
2. **Find the ref name articles already use.** Search Wikipedia for
   `insource:"Q<item>"`. If articles already cite it, use the name most of them
   use. For Lepidoptera 2025 that's `NZTCS2025` (81 articles in November 2026,
   against 16 for `Hoare2026` and 5 for `Hoare2025`). Otherwise, use
   `NZTCS<assessment year>`. The bot reuses whatever name an individual article
   already has, so this name only matters for articles that don't cite the
   report yet.
3. **Add an entry** to `KNOWN_REPORTS`, keyed by the report's `reportName`
   exactly as it appears in the CSV:

   ```python
   "Lepidoptera 2025 (Hoare et al. 2026)": Report(
       wikidata="Q139379012",
       ref_name="NZTCS2025",
       url="https://www.doc.govt.nz/globalassets/documents/science-and-technical/nztcs51.pdf",
   ),
   ```

4. Run `pytest` and open a pull request.

Without an entry, the scaffold is built from the `reportName` and `reportYear`
columns, for example ref name `NZTCS-Birds-2021` and title *Conservation status
of New Zealand Birds, 2021*. That title is generated, so it may not match the
published report's title word for word. See
[reviewing-output.md](reviewing-output.md#other-reports-complete-the-scaffold).
