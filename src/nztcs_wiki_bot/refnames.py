"""``nztcs-wiki-bot refnames``: which ref name do articles use for a report?

Searches English Wikipedia articles for a report's Wikidata ID and PDF
filename, then counts the ``<ref name=...>`` that each one cites it under. Use
it to choose the report's ``ref_name`` in ``reports.yaml``.

Read-only. Responses aren't cached, so the counts are current.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from . import citation, reports
from .wiki_client import CONTACT_ENV_VAR, MissingContactError, WikiClient

# VisualEditor names refs ":0", ":1"…, which says nothing about the source.
_AUTO_NAME = re.compile(r":\d+")


@dataclass
class Usage:
    found: int  # articles the searches returned
    names: Counter[str]  # ref name -> number of articles using it


def search_queries(report: reports.Report) -> list[str]:
    """CirrusSearch queries for articles that may cite ``report``.

    >>> search_queries(reports.Report("Q1", "x", "https://example.org/a/nztcs9.pdf"))
    ['insource:"Q1"', 'insource:"nztcs9.pdf"']
    """
    # The filename, not the whole URL, so other hosts for the same PDF are found.
    filename = report.url.rstrip("/").rsplit("/", 1)[-1]
    return [f'insource:"{report.wikidata}"', f'insource:"{filename}"']


def count_names(wikitexts: Iterable[str], report: reports.Report) -> Counter[str]:
    names = (citation.existing_ref_name(text, report) for text in wikitexts)
    return Counter(n for n in names if n is not None)


def find_usage(client: WikiClient, report: reports.Report) -> Usage:
    titles = sorted({t for q in search_queries(report) for t in client.search_titles(q)})
    texts = client.fetch_wikitexts(titles)
    return Usage(found=len(titles), names=count_names(texts.values(), report))


def suggest(names: Counter[str], current: str) -> str:
    """The most used descriptive name, keeping ``current`` on a tie or no data.

    >>> suggest(Counter({":0": 9, "Hoare2026": 2}), "NZTCS2025")
    'Hoare2026'
    >>> suggest(Counter({"a": 2, "NZTCS2025": 2}), "NZTCS2025")
    'NZTCS2025'
    >>> suggest(Counter({":0": 1}), "NZTCS2025")
    'NZTCS2025'
    """
    usable = {n: c for n, c in names.items() if not _AUTO_NAME.fullmatch(n)}
    if not usable:
        return current
    best = max(usable.values())
    if usable.get(current) == best:
        return current
    return min(n for n, c in usable.items() if c == best)


def format_usage(name: str, report: reports.Report, usage: Usage) -> str:
    lines = [
        f"Report: {name}",
        f"Articles found by searching for {report.wikidata} or its PDF filename: {usage.found}",
    ]
    if usage.names:
        lines.append("Ref names they cite it under (articles):")
        ranked = sorted(usage.names.items(), key=lambda item: (-item[1], item[0]))
        lines += [f"  {count:>5}  {ref}" for ref, count in ranked]
    unnamed = usage.found - sum(usage.names.values())
    if unnamed:
        lines.append(f"Found, but with no named ref matching this report: {unnamed}")
    best = suggest(usage.names, report.ref_name)
    if best != report.ref_name:
        lines.append(f"Suggestion: change ref_name from {report.ref_name} to {best}")
    elif best in usage.names:
        lines.append(f"Suggestion: keep ref_name {best}")
    else:
        lines.append(f"No descriptive name in use, so keep ref_name {best}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nztcs-wiki-bot refnames",
        description="Count the ref names Wikipedia articles use for a report in reports.yaml.",
    )
    p.add_argument("report_name", help="The report's name, exactly as in reports.yaml (quote it)")
    p.add_argument(
        "--contact",
        default=None,
        help="Your email or contact URL, sent in the User-Agent as Wikimedia requires "
        f"(default: ${CONTACT_ENV_VAR})",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    name = args.report_name.strip()
    try:
        report = reports.lookup(name)
    except reports.ReportsFileError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if report is None:
        listed = "\n".join(f"  {n}" for n in reports.known_reports())
        print(
            f"error: no entry for {name!r} in {reports.REPORTS_FILE}\n"
            f"Add one first (see docs/adding-a-report.md). Reports listed now:\n{listed}",
            file=sys.stderr,
        )
        return 2
    try:
        client = WikiClient(contact=args.contact)
    except MissingContactError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(format_usage(name, report, find_usage(client, report)))
    return 0
