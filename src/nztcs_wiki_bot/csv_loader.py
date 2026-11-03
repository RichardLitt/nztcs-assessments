"""Load and clean NZTCS assessment rows from the report CSV.

The CSV is produced by ``fetch_nztcs_assessments.py`` (the fetch script).
Column names here must stay in sync with the ``fields`` list in that script.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

# The columns the fetch script writes, in order. Kept here so the loader can
# assert the CSV it is handed is actually an NZTCS report.
EXPECTED_FIELDS = (
    "speciesId",
    "assessmentId",
    "nztcsSpeciesName",
    "commonName",
    "conservationStatusTitle",
    "categoryTitle",
    "criteriaTitle",
    "qualifiers",
    "reportName",
    "reportYear",
    "popSizeTitle",
    "popTrendTitle",
)


class _HTMLStripper(HTMLParser):
    """Collect text content, discarding tags (mainly ``<i>`` italics)."""

    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_data(self) -> str:
        return "".join(self._chunks)


def strip_html(text: str | None) -> str:
    """Strip HTML tags and unescape entities from a CSV cell.

    Returns ``""`` for empty/None input so callers never see ``None``.

    >>> strip_html("<i>Aenetus</i> &amp; co")
    'Aenetus & co'
    >>> strip_html(None)
    ''
    """
    if not text:
        return ""
    stripper = _HTMLStripper()
    stripper.feed(text)
    return stripper.get_data()


@dataclass(frozen=True)
class Row:
    """One NZTCS assessment row, cleaned of HTML.

    All fields are strings; absent cells are empty strings, never ``None``.
    """

    species_id: str
    assessment_id: str
    nztcs_species_name: str
    common_name: str
    conservation_status_title: str
    category_title: str
    criteria_title: str
    qualifiers: str
    report_name: str
    report_year: str
    pop_size_title: str
    pop_trend_title: str
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> Row:
        def clean(key: str) -> str:
            return strip_html(d.get(key, ""))

        known = set(EXPECTED_FIELDS)
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(
            species_id=d.get("speciesId", "") or "",
            assessment_id=d.get("assessmentId", "") or "",
            nztcs_species_name=clean("nztcsSpeciesName"),
            common_name=clean("commonName"),
            conservation_status_title=d.get("conservationStatusTitle", "") or "",
            category_title=d.get("categoryTitle", "") or "",
            criteria_title=d.get("criteriaTitle", "") or "",
            qualifiers=d.get("qualifiers", "") or "",
            report_name=d.get("reportName", "") or "",
            report_year=d.get("reportYear", "") or "",
            pop_size_title=d.get("popSizeTitle", "") or "",
            pop_trend_title=d.get("popTrendTitle", "") or "",
            extra=extra,
        )


def load_rows(csv_path: str | Path) -> list[Row]:
    """Parse the report CSV into a list of :class:`Row`.

    Raises ``ValueError`` if the CSV is missing required columns.
    """
    return list(iter_rows(csv_path))


def iter_rows(csv_path: str | Path) -> Iterator[Row]:
    """Stream :class:`Row` objects from the report CSV."""
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing = [c for c in EXPECTED_FIELDS if c not in header]
        if missing:
            raise ValueError(
                f"{path} is missing expected NZTCS columns: {', '.join(missing)}"
            )
        for raw in reader:
            yield Row.from_dict(raw)
