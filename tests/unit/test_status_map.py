import csv
from pathlib import Path

import pytest

from nztcs_wiki_bot import status_map as sm

# One real row per distinct conservationStatusTitle in report 1176 (Lepidoptera 2025).
STATUS_CSV = Path(__file__).parents[1] / "fixtures" / "csv" / "all_status_titles.csv"


@pytest.mark.parametrize(
    "title, code",
    [
        ("Nationally Critical", "NC"),
        ("Nationally Endangered", "NE"),
        ("Nationally Vulnerable", "NV"),
        ("Declining", "D"),
        ("Naturally Uncommon", "NU"),
        ("Uncommon", "NU"),  # 2025 rename
        ("Not Threatened", "NT"),
        ("Data Deficient", "DD"),
        ("Nationally Increasing", "NI"),
        ("Recovering", "R"),
        ("Relict", "Rel"),
        ("Extinct", "EX"),
    ],
)
def test_known_titles_map(title, code):
    assert sm.status_code(title) == code


# Every code Module:Conservation status renders for NZTCS (p.NZTCS, checked
# 2026-11-03), excluding the 2002-era SD/GD/SP/RR that NZTCS no longer issues.
WIKIPEDIA_NZTCS_CODES = {"EX", "NC", "NE", "NV", "NI", "D", "Rel", "NU", "R", "NT", "DD"}


def test_every_mapped_code_renders_on_wikipedia():
    assert set(sm.STATUS_CODES.values()) <= WIKIPEDIA_NZTCS_CODES


@pytest.mark.parametrize("title", sorted(sm.NO_WIKIPEDIA_CODE_TITLES))
def test_titles_without_wikipedia_badge_are_unmapped(title):
    assert not sm.is_known(title)
    assert sm.unmapped_reason(title) == "no-wikipedia-code"


def test_unknown_title_raises():
    with pytest.raises(sm.UnknownStatusError) as exc:
        sm.status_code("Totally Made Up Status")
    assert "Totally Made Up Status" in str(exc.value)


def test_is_known():
    assert sm.is_known("Nationally Critical")
    assert not sm.is_known("Not assessed")
    assert not sm.is_known("")


def test_whitespace_tolerant():
    assert sm.status_code("  Declining  ") == "D"


def test_non_status_titles_are_recognised_but_unmapped():
    for title in sm.NON_STATUS_TITLES:
        assert not sm.is_known(title)


def test_every_real_status_is_known_or_explicitly_non_status():
    with STATUS_CSV.open(encoding="utf-8") as f:
        titles = {r["conservationStatusTitle"] for r in csv.DictReader(f)}
    unaccounted = {
        t for t in titles if not sm.is_known(t) and sm.unmapped_reason(t) == "unknown-status-title"
    }
    assert not unaccounted, f"status titles need a mapping decision: {unaccounted}"
