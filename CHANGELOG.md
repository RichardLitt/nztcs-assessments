# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - unreleased

First version.

### Added

- `nztcs-wiki-bot` command. It reads an NZTCS report CSV and writes a review
  queue (`review/matched.md`, `ambiguous.md`, `unmapped.tsv`, `no_match.tsv`,
  `skipped.tsv`, `stats.txt`) of Speciesbox patches.
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
  opt-in live test, and CI on Python 3.10–3.13.

### Notes

- NZTCS categories Wikipedia can't display (Migrant, Vagrant, Coloniser,
  Introduced and Naturalised) go to `unmapped.tsv` rather than producing
  patches that would render as "Invalid status".
