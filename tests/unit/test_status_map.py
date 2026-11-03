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
        ("Coloniser", "C"),
        ("Vagrant", "V"),
        ("Introduced and Naturalised", "IN"),
    ],
)
def test_known_titles_map(title, code):
    assert sm.status_code(title) == code


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
        t for t in titles if not sm.is_known(t) and t not in sm.NON_STATUS_TITLES
    }
    assert not unaccounted, f"status titles need a mapping decision: {unaccounted}"
