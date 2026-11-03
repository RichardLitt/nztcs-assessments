from pathlib import Path

import pytest

from nztcs_wiki_bot import csv_loader

CSV_DIR = Path(__file__).parents[1] / "fixtures" / "csv"


def test_load_one_row_has_all_fields():
    rows = csv_loader.load_rows(CSV_DIR / "one_row.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row.species_id == "100"
    assert row.nztcs_species_name == "Aenetus virescens (Doubleday, 1843)"
    assert row.common_name == "pūriri moth"
    assert row.conservation_status_title == "Not Threatened"
    assert row.report_year == "2026"


def test_empty_cells_are_empty_strings_not_none():
    row = csv_loader.load_rows(CSV_DIR / "undescribed.csv")[0]
    assert row.common_name == ""
    assert row.pop_size_title == ""
    assert row.common_name is not None


def test_strip_html_helper():
    assert csv_loader.strip_html("<i>Aenetus</i> &amp; co") == "Aenetus & co"
    assert csv_loader.strip_html(None) == ""
    assert csv_loader.strip_html("") == ""


def test_missing_columns_raise(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing expected NZTCS columns"):
        csv_loader.load_rows(bad)
