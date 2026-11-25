"""Command-line entrypoint: ``nztcs-wiki-bot`` / ``python -m nztcs_wiki_bot``.

``nztcs-wiki-bot fetch ...`` downloads a report (see :mod:`.fetch`),
``nztcs-wiki-bot refnames ...`` counts the ref names
articles use for a report (see :mod:`.refnames`),
``nztcs-wiki-bot apply ...`` saves reviewed patches (see :mod:`.apply`), and any
other invocation runs the read-only review-queue pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import reports
from .csv_loader import load_rows
from .output import write_review
from .pipeline import PipelineConfig, run_from_csv
from .wiki_client import CONTACT_ENV_VAR, MissingContactError, WikiClient


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nztcs-wiki-bot",
        description="Generate a Wikipedia review queue of NZTCS status patches. "
        "This run is read-only: it never edits Wikipedia. "
        "Use 'nztcs-wiki-bot fetch REPORT_ID' to download a report CSV first, "
        "'nztcs-wiki-bot refnames NAME' to check a report's ref name, and "
        "'nztcs-wiki-bot apply' to save reviewed patches, confirming each one.",
    )
    p.add_argument("--csv", required=True, help="Path to an NZTCS report CSV")
    p.add_argument("--out", default="review", help="Output directory (default: review/)")
    p.add_argument(
        "--cache",
        default="cache",
        help="HTTP cache directory (default: cache/). Delete it to force re-fetch.",
    )
    p.add_argument("--limit", type=int, default=None, help="Process at most N resolvable rows")
    p.add_argument("--species", default=None, help="Only rows whose binomial contains this string")
    p.add_argument(
        "--contact",
        default=None,
        help="Your email or contact URL, sent in the User-Agent as Wikimedia requires "
        f"(default: ${CONTACT_ENV_VAR})",
    )
    return p


def _warn_missing_reports(csv_path: str) -> None:
    """Say which reports have no citation entry, and how to add one."""
    for name in reports.missing(row.report_name for row in load_rows(csv_path)):
        print(
            f"\nWARNING: no citation entry for report {name!r}.\n"
            "Its patches will have a TODO citation to complete by hand, and 'apply' "
            "won't save them.\n"
            f"To fix this, add the following to {reports.REPORTS_FILE}\n"
            "(see docs/adding-a-report.md), then run this again:\n\n"
            f"{reports.entry_template(name)}\n",
            flush=True,
        )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "fetch":
        from . import fetch

        return fetch.main(argv[1:])
    if argv and argv[0] == "refnames":
        from . import refnames

        return refnames.main(argv[1:])
    if argv and argv[0] == "apply":
        from . import apply

        return apply.main(argv[1:])

    args = build_parser().parse_args(argv)

    if not Path(args.csv).exists():
        print(f"error: CSV not found: {args.csv}", file=sys.stderr)
        return 2

    try:
        reports.known_reports()
    except reports.ReportsFileError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        client = WikiClient(contact=args.contact, cache_dir=Path(args.cache))
    except MissingContactError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    config = PipelineConfig(limit=args.limit, species=args.species)

    print(f"Loading {args.csv} ...", flush=True)
    _warn_missing_reports(args.csv)
    buckets = run_from_csv(args.csv, client, config)
    write_review(args.out, buckets)

    print(
        f"Done. rows_in={buckets.rows_in} "
        f"matched={len(buckets.matched)} ambiguous={len(buckets.ambiguous)} "
        f"unmapped={len(buckets.unmapped)} no_match={len(buckets.no_match)} "
        f"skipped={len(buckets.skipped)} filtered={buckets.filtered}",
        flush=True,
    )
    print(f"Review queue written to {args.out}/", flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
