# Contributing

Thanks for helping. Bug reports, new test cases and fixes are all welcome.

## Setup

```bash
git clone https://github.com/RichardLitt/nztcs-assessments.git
cd nztcs-assessments
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks

CI runs these on every pull request, and they should pass locally first:

```bash
ruff check         # lint (ruff check --fix for the auto-fixable ones)
pyright            # type-check src/ and tests/
pytest             # offline tests + doctests, fails under 90% coverage
```

The suite is fully offline. Wikipedia and NZTCS are mocked. One opt-in test
does a real read-only Wikipedia lookup. Run it before processing a new NZTCS
report, to catch Wikipedia API changes the mocks can't:

```bash
NZTCS_BOT_CONTACT=you@example.org pytest -m live --no-cov tests/live
```

## Where things go

- New behaviour needs a test. Unit tests live in `tests/unit/test_<module>.py`.
  Anything that crosses modules goes in `tests/integration/`.
- **Wikitext cases** (a real infobox layout the bot gets wrong): save a minimal
  copy of the article's wikitext as `tests/fixtures/wikitext/<name>.txt`, keeping
  only what's needed to reproduce the problem, and add a test in
  `tests/unit/test_speciesbox.py`.
- **End-to-end cases**: add a page to `tests/fixtures/api_responses/site.json`
  and a row to `tests/fixtures/csv/end_to_end.csv`, then regenerate the golden
  output and **read the diff** before committing:

  ```bash
  UPDATE_GOLDEN=1 pytest tests/integration/test_end_to_end.py
  git diff tests/fixtures/expected_review/
  ```

- **New NZTCS status titles**: see
  [docs/adding-a-report.md](docs/adding-a-report.md#4-check-unmappedtsv) and
  [docs/nztcs-status-codes.md](docs/nztcs-status-codes.md).
- Don't commit report CSVs (`nztcs_report_*.csv` is gitignored). Fixtures should
  be a few rows, copied from a real report.

## Ground rules

- **Read-only stays read-only.** No change may add a write, login or token
  request to `wiki_client.py`. `test_no_write_endpoints.py` must keep passing
  unchanged. A PR that weakens it won't be merged.
- **Fail loudly, never guess.** When the bot isn't sure (a name, a taxon, a
  status), it should put the row in a bucket with a reason, not produce a
  patch.
- Keep output deterministic. If you add a field to `review/` files, make sure
  its ordering is stable.

## Pull requests

- Branch from `main` and open the PR against `main`. Keep one change per PR.
- Describe what changed and why, and include before/after output if
  `review/` files change.
- Add a line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md).

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By taking
part, you agree to abide by it.
