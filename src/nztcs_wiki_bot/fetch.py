"""Download an NZTCS report's assessments from nztcs.org.nz into a CSV.

Usage: ``nztcs-wiki-bot fetch [REPORT_ID] [--out PATH]`` or
``python -m nztcs_wiki_bot.fetch [REPORT_ID]``.

The CSV columns are :data:`~nztcs_wiki_bot.csv_loader.EXPECTED_FIELDS`, so the
output feeds straight into the main bot via ``--csv``.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

import requests

from . import __version__
from .csv_loader import EXPECTED_FIELDS, strip_html
from .wiki_client import PROJECT_URL, REQUESTS_VERSION

API_URL = "https://nztcs.org.nz/rest/assessmentSearch"
DEFAULT_REPORT_ID = 1176  # Lepidoptera 2025 (Hoare et al. 2026)
PAGE_SIZE = 1000
USER_AGENT = (
    f"nztcs-wiki-bot/{__version__} (+{PROJECT_URL}) python-requests/{REQUESTS_VERSION}"
)

# Cells that may carry HTML markup (mainly <i> italics) in the API response.
_HTML_FIELDS = ("nztcsSpeciesName", "commonName")


def fetch_assessments(
    report_id: int,
    session: requests.Session | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict]:
    """Fetch every assessment for ``report_id``, following pagination."""
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    results: list[dict] = []
    page = 1
    while True:
        resp = session.post(
            API_URL,
            json={
                "reportId": report_id,
                "pageNumber": page,
                "pageSize": page_size,
                "showArchived": True,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("searchResults", [])
        total = data.get("total", 0)
        results.extend(batch)
        if not batch or len(results) >= total:
            break
        page += 1
    return results


def save_csv(assessments: list[dict], path: str | Path) -> int:
    """Write ``assessments`` to ``path`` as an NZTCS report CSV; return row count."""
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer: csv.DictWriter[str] = csv.DictWriter(f, fieldnames=EXPECTED_FIELDS)
        writer.writeheader()
        for a in assessments:
            row = {k: a.get(k, "") for k in EXPECTED_FIELDS}
            for k in _HTML_FIELDS:
                row[k] = strip_html(row[k])
            writer.writerow(row)
    return len(assessments)


def default_filename(report_id: int, today: date | None = None) -> str:
    """``nztcs_report_<id>_<YYYYMMDD>.csv``.

    >>> default_filename(1176, date(2026, 5, 5))
    'nztcs_report_1176_20260505.csv'
    """
    return f"nztcs_report_{report_id}_{(today or date.today()):%Y%m%d}.csv"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nztcs-wiki-bot fetch",
        description="Download an NZTCS report from nztcs.org.nz as a CSV.",
    )
    p.add_argument(
        "report_id",
        nargs="?",
        type=int,
        default=DEFAULT_REPORT_ID,
        help=f"NZTCS report ID (default: {DEFAULT_REPORT_ID}, Lepidoptera 2025)",
    )
    p.add_argument(
        "--out", default=None, help="Output path (default: nztcs_report_<id>_<date>.csv)"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = args.out or default_filename(args.report_id)
    print(f"Fetching assessments for report {args.report_id} ...", flush=True)
    assessments = fetch_assessments(args.report_id)
    if not assessments:
        print(f"No assessments found for report {args.report_id}")
        return 1
    n = save_csv(assessments, out)
    print(f"Saved {n} assessments to {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
