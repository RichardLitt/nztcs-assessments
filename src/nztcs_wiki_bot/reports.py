"""NZTCS reports the bot can cite in full.

Each entry links a report, as it appears in the CSV's ``reportName`` column, to
its Wikidata item. The citation is then ``{{CiteQ|<item>}}``, which builds the
full reference (authors, title, series, number, URL) from Wikidata, and is how
existing Wikipedia articles already cite these reports.

``ref_name`` is the ``<ref name=...>`` that articles already use for the
report, so new citations join existing ones instead of duplicating them. ``url``
is the report's full-text link, used with the Wikidata ID to spot a citation of
the same report under some other ref name.

A report missing from this table still works: the bot falls back to a
``{{cite report}}`` scaffold with a TODO marker for the reviewer to complete.
To add a report, see docs/adding-a-report.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Report:
    wikidata: str
    ref_name: str
    url: str


KNOWN_REPORTS: dict[str, Report] = {
    # Hoare, Edwards, Knox, Frost & Michel 2026. NZ Threat Classification Series 51.
    "Lepidoptera 2025 (Hoare et al. 2026)": Report(
        wikidata="Q139379012",
        ref_name="Hoare2026",
        url="https://www.doc.govt.nz/globalassets/documents/science-and-technical/nztcs51.pdf",
    ),
}


def lookup(report_name: str) -> Report | None:
    """Return the known report for a CSV ``reportName``, or ``None``.

    >>> lookup("Lepidoptera 2025 (Hoare et al. 2026)").wikidata
    'Q139379012'
    >>> lookup("Something else 2030") is None
    True
    """
    return KNOWN_REPORTS.get((report_name or "").strip())
