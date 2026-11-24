# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Citations for known reports are now complete: `status_ref` is
  `{{CiteQ|<Wikidata item>}}` under the ref name most existing articles use
  (`NZTCS2025` for Lepidoptera 2025), instead of a `{{cite report}}` scaffold
  with a TODO marker. Known reports are listed in `reports.py`; other reports
  still get the scaffold.
- If an article already cites the report under any ref name (matched by
  Wikidata ID or full-text URL), the patch reuses it as `<ref name="..." />`
  instead of adding a second citation. Articles that already show the current
  status with that citation are now `already-current` rather than rewritten.

### Fixed

- Existing ref names written bare or in single quotes (`<ref name=X>`) were not
  recognised, so a patch could define the same name twice.

## [0.1.0] - 2026-11-24

First version.

### Added

- `nztcs-wiki-bot` command. It reads an NZTCS report CSV and writes a review
  queue (`review/matched.md`, `ambiguous.md`, `unmapped.tsv`, `no_match.tsv`,
  `skipped.tsv`, `stats.txt`) of Speciesbox patches. `stats.txt` accounts for
  every input row, counting rows left out by `--species` or `--limit` as
  `filtered`, and reports whether the totals balance.
- `nztcs-wiki-bot fetch REPORT_ID` downloads a report from nztcs.org.nz,
  following pagination.
- Three patch modes: insert a new status, update an existing NZTCS status, or
  add NZTCS as `status2` alongside another system.
- Taxon verification: an article must have an infobox whose genus and species
  match the CSV row.
- A read-only, Wikimedia-compliant client: identifying User-Agent with a
  required operator contact (`--contact` / `NZTCS_BOT_CONTACT`), `maxlag`
  backoff, 50-title batching, a 1 request/sec floor, and an on-disk cache.
- Offline test suite (unit, integration with golden output, doctests), an
  opt-in live test to run by hand before processing a new report, and CI on
  Python 3.10–3.13.
- User guides for adding a report, reviewing the output, NZTCS status codes,
  and Wikipedia API policy, plus CONTRIBUTING and a code of conduct.

### Notes

- NZTCS statuses Wikipedia can't display go to `unmapped.tsv` with the reason
  `no-wikipedia-code`, rather than producing patches that would render as
  "Invalid status". These are Coloniser, Migrant, Vagrant, Introduced and
  Naturalised, and Uncommon where the population state isn't natural
  (Uncommon with a natural state is patched as `NU`). Adding them to
  Wikipedia's Module:Conservation status has been requested; see
  [docs/proposals/module-conservation-status-nztcs.md](docs/proposals/module-conservation-status-nztcs.md).
- NZTCS qualifiers are read but not yet used
  ([#8](https://github.com/RichardLitt/nztcs-assessments/issues/8)).

[Unreleased]: https://github.com/RichardLitt/nztcs-assessments/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RichardLitt/nztcs-assessments/releases/tag/v0.1.0
