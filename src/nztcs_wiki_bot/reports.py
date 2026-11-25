"""NZTCS reports the bot can cite in full.

The reports are listed in ``reports.yaml``, next to this module. Each entry
links a report, as it appears in the CSV's ``reportName`` column, to its
Wikidata item. The citation is then ``{{CiteQ|<item>}}``, which builds the full
reference (authors, title, series, number, URL) from Wikidata, and is how
existing Wikipedia articles already cite these reports.

``ref_name`` is the ``<ref name=...>`` that articles already use for the
report, so new citations join existing ones instead of duplicating them. ``url``
is the report's full-text link, used with the Wikidata ID to spot a citation of
the same report under some other ref name.

A report missing from the file still works: the bot falls back to a
``{{cite report}}`` scaffold with a TODO marker for the reviewer to complete.
To add a report, see docs/adding-a-report.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, fields
from functools import cache
from pathlib import Path

import yaml

REPORTS_FILE = Path(__file__).with_name("reports.yaml")


@dataclass(frozen=True)
class Report:
    wikidata: str
    ref_name: str
    url: str


class ReportsFileError(ValueError):
    """Raised when ``reports.yaml`` can't be read as a table of reports."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """``SafeLoader`` that rejects repeated keys instead of keeping the last."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"{key!r} appears twice", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def load(path: Path = REPORTS_FILE) -> dict[str, Report]:
    """Read and check a reports file.

    Raises :class:`ReportsFileError`, naming the file and the problem.
    """
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except yaml.YAMLError as e:
        raise ReportsFileError(f"{path}: not valid YAML:\n{e}") from e
    if not isinstance(data, dict):
        raise ReportsFileError(f"{path}: expected a list of report names, each with its fields")

    wanted = {f.name for f in fields(Report)}
    reports: dict[str, Report] = {}
    for name, entry in data.items():
        where = f"{path}: {name!r}"
        if not isinstance(entry, dict) or set(entry) != wanted:
            raise ReportsFileError(
                f"{where} needs exactly these indented fields: wikidata, ref_name, url"
            )
        if not all(isinstance(v, str) for v in entry.values()):
            raise ReportsFileError(f"{where}: every field must be filled in with text")
        report = Report(**entry)
        if not re.fullmatch(r"Q\d+", report.wikidata):
            raise ReportsFileError(f"{where}: wikidata must look like Q139379012")
        if not re.fullmatch(r"[^\s\"'<>/]+", report.ref_name):
            raise ReportsFileError(f"{where}: ref_name can't contain spaces, quotes, <, > or /")
        if not report.url.startswith("https://"):
            raise ReportsFileError(f"{where}: url must start with https://")
        reports[str(name).strip()] = report
    return reports


@cache
def known_reports() -> dict[str, Report]:
    """The reports in :data:`REPORTS_FILE`, read once."""
    return load()


def lookup(report_name: str) -> Report | None:
    """The known report for a CSV ``reportName``, or ``None``.

    >>> lookup("Lepidoptera 2025 (Hoare et al. 2026)").wikidata
    'Q139379012'
    >>> lookup("Birds 2021") is None
    True
    """
    return known_reports().get((report_name or "").strip())


def missing(report_names: Iterable[str]) -> list[str]:
    """The names with no entry, once each and sorted. Blank names are ignored.

    >>> missing(["Birds 2021", "Lepidoptera 2025 (Hoare et al. 2026)", "Birds 2021", ""])
    ['Birds 2021']
    """
    names = {(n or "").strip() for n in report_names}
    return sorted(n for n in names if n and lookup(n) is None)


def entry_template(report_name: str) -> str:
    """A block to paste into ``reports.yaml`` for a missing report.

    The suggested ``ref_name`` uses the assessment year in the report's name.

    >>> print(entry_template("Hymenoptera 2014 (Ward et al. 2017)"))
    "Hymenoptera 2014 (Ward et al. 2017)":
      wikidata: Q...
      ref_name: NZTCS2014
      url: https://...
    """
    year = re.search(r"\b(?:19|20)\d{2}\b", report_name)
    quoted = report_name.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'"{quoted}":\n'
        f"  wikidata: Q...\n"
        f"  ref_name: NZTCS{year.group(0) if year else ''}\n"
        f"  url: https://..."
    )
