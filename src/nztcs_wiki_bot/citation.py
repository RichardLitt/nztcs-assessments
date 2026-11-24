"""Build the ``status_ref`` citation for an NZTCS patch.

For a report listed in :mod:`nztcs_wiki_bot.reports`, the citation is
``{{CiteQ|<Wikidata item>}}`` under the ref name articles already use for that
report. If the article already cites the report under some other name (found
by its Wikidata ID or full-text URL), that name is reused instead, so the
article ends up with one citation, not two.

For any other report, the CSV doesn't carry enough to cite it (no authors or
series number), so the citation is a ``{{cite report}}`` *scaffold*: it fills
in what's known and marks the author field with a visible HTML comment that the
reviewer must complete before saving.
"""

from __future__ import annotations

import re

from . import reports
from .csv_loader import Row

TODO_AUTHORS = "<!-- TODO: complete author list and series number before saving -->"

# A named ref with a body. The name may be double-quoted, single-quoted or bare.
_NAMED_REF = re.compile(
    r"<ref\s+name\s*=\s*"
    r"(?:\"(?P<dq>[^\"]+)\"|'(?P<sq>[^']+)'|(?P<bare>[^\s\"'/>]+))"
    r"\s*>(?P<body>.*?)</ref>",
    re.DOTALL | re.IGNORECASE,
)


def ref_name(report_name: str) -> str:
    """Derive a deterministic, slug-safe ``<ref name="...">`` for a scaffold.

    >>> ref_name("Lepidoptera 2025 (Hoare et al. 2026)")
    'NZTCS-Lepidoptera-2025'
    """
    # Keep the leading "<taxon> <year>" portion before any parenthetical.
    head = report_name.split("(", 1)[0].strip()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", head).strip("-")
    return f"NZTCS-{slug}" if slug else "NZTCS"


def build_ref(row: Row, wikitext: str = "") -> tuple[str, str]:
    """Return ``(ref_name, full_ref_wikitext)`` for a CSV row.

    ``wikitext`` is the article's current source, used to reuse an existing
    citation of the same report. The full ref is a complete
    ``<ref name="...">...</ref>`` element ready to drop into a Speciesbox
    ``status_ref`` parameter.

    >>> from nztcs_wiki_bot.csv_loader import Row
    >>> r = Row.from_dict(
    ...     {"reportName": "Lepidoptera 2025 (Hoare et al. 2026)", "reportYear": "2026"}
    ... )
    >>> build_ref(r)
    ('Hoare2026', '<ref name="Hoare2026">{{CiteQ|Q139379012}}</ref>')
    >>> build_ref(r, '<ref name=moths>{{CiteQ|Q139379012|pages=32}}</ref>')[0]
    'moths'
    """
    report = reports.lookup(row.report_name)
    if report is None:
        return _scaffold(row)
    name = existing_ref_name(wikitext, report) or report.ref_name
    return name, f'<ref name="{name}">{{{{CiteQ|{report.wikidata}}}}}</ref>'


def existing_ref_name(wikitext: str, report: reports.Report) -> str | None:
    """Name of a ref in ``wikitext`` that already cites ``report``, if any.

    Matches on the report's Wikidata ID or full-text URL. Unnamed refs can't be
    reused, so they're ignored.

    >>> rep = reports.lookup("Lepidoptera 2025 (Hoare et al. 2026)")
    >>> existing_ref_name('<ref name="H26">{{CiteQ|Q139379012}}</ref>', rep)
    'H26'
    >>> existing_ref_name('<ref name="other">{{CiteQ|Q1393790123}}</ref>', rep) is None
    True
    """
    qid = re.compile(r"\b" + re.escape(report.wikidata) + r"\b")
    for m in _NAMED_REF.finditer(wikitext):
        body = m.group("body")
        if qid.search(body) or report.url in body:
            return m.group("dq") or m.group("sq") or m.group("bare")
    return None


def _scaffold(row: Row) -> tuple[str, str]:
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
