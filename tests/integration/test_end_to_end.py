"""Full CLI run against the fake wiki, compared byte-for-byte to a golden copy.

The input (``fixtures/csv/end_to_end.csv``) has one row per outcome: insert,
update, taxon mismatch, disambiguation, no infobox, empty page, missing page,
two skip rules, a non-status title and a never-seen status title.

To regenerate the golden files after an intentional output change::

    UPDATE_GOLDEN=1 pytest tests/integration/test_end_to_end.py

then review the diff under ``tests/fixtures/expected_review/`` before committing.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import responses

from nztcs_wiki_bot.cli import main
from tests.conftest import FIXTURES
from tests.integration import wiki_site

CSV = FIXTURES / "csv" / "end_to_end.csv"
GOLDEN = FIXTURES / "expected_review"


def run_cli(tmp_path: Path, name: str = "review") -> Path:
    out = tmp_path / name
    cache = tmp_path / f"{name}-cache"
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki_site.install(rsps)
        rc = main(["--csv", str(CSV), "--out", str(out), "--cache", str(cache)])
    assert rc == 0
    return out


def _files(d: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir())}


def test_output_matches_golden(tmp_path):
    out = run_cli(tmp_path)
    if os.environ.get("UPDATE_GOLDEN"):
        shutil.rmtree(GOLDEN, ignore_errors=True)
        shutil.copytree(out, GOLDEN)
    assert _files(out) == _files(GOLDEN)


def test_every_row_lands_in_exactly_one_bucket(tmp_path):
    stats = (run_cli(tmp_path) / "stats.txt").read_text(encoding="utf-8")
    assert "rows_in    11" in stats
    assert "balanced   True" in stats
