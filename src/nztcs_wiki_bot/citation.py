"""Build a ``{{cite report}}`` scaffold ref for an NZTCS patch.

The CSV does not carry the full author list, so the generated citation is a
*scaffold*: it pre-fills what we know (title, year, publisher, series) and marks
the author field with an HTML comment so the human reviewer completes it before
saving. The scaffold marker is intentionally visible in every diff.
"""

from __future__ import annotations

import re

from .csv_loader import Row

TODO_AUTHORS = "<!-- TODO: complete author list and series number before saving -->"


def ref_name(report_name: str) -> str:
    """Derive a deterministic, slug-safe ``<ref name="...">`` from a report name.

    >>> ref_name("Lepidoptera 2025 (Hoare et al. 2026)")
    'NZTCS-Lepidoptera-2025'
    """
    # Keep the leading "<taxon> <year>" portion before any parenthetical.
    head = report_name.split("(", 1)[0].strip()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", head).strip("-")
    return f"NZTCS-{slug}" if slug else "NZTCS"


def build_ref(row: Row) -> tuple[str, str]:
    """Return ``(ref_name, full_ref_wikitext)`` for a CSV row.

    The full ref is a complete ``<ref name="...">...</ref>`` element ready to drop
    into a Speciesbox ``status_ref`` parameter.

    >>> from nztcs_wiki_bot.csv_loader import Row
    >>> r = Row.from_dict(
    ...     {"reportName": "Lepidoptera 2025 (Hoare et al. 2026)", "reportYear": "2026"}
    ... )
    >>> name, ref = build_ref(r)
    >>> name
    'NZTCS-Lepidoptera-2025'
    >>> "cite report" in ref and TODO_AUTHORS in ref
    True
    """
    name = ref_name(row.report_name)
    title = _report_title(row.report_name)
    year = row.report_year or _year_from_name(row.report_name)
    ref = (
        f'<ref name="{name}">{{{{cite report '
        f"| author = {TODO_AUTHORS} "
        f"| date = {year} "
        f"| title = {title} "
        f"| publisher = New Zealand Department of Conservation "
        f"| series = New Zealand Threat Classification Series "
        f"}}}}</ref>"
    )
    return name, ref


def _report_title(report_name: str) -> str:
    """Human title for the cite. Falls back to the raw report name."""
    head = report_name.split("(", 1)[0].strip()
    if not head:
        return report_name
    # "Lepidoptera 2025" -> a descriptive conservation-status title.
    m = re.match(r"^(.*?)\s+(\d{4})$", head)
    if m:
        taxon, year = m.group(1), m.group(2)
        return f"Conservation status of New Zealand {taxon}, {year}"
    return head


def _year_from_name(report_name: str) -> str:
    m = re.search(r"\b(20\d{2})\b", report_name)
    return m.group(1) if m else ""
