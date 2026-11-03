"""Command-line entrypoint: ``nztcs-wiki-bot`` / ``python -m nztcs_wiki_bot``.

``nztcs-wiki-bot fetch ...`` downloads a report (see :mod:`.fetch`); any other
invocation runs the review-queue pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .output import write_review
from .pipeline import PipelineConfig, run_from_csv
from .wiki_client import CONTACT_ENV_VAR, MissingContactError, WikiClient


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nztcs-wiki-bot",
        description="Generate a Wikipedia review queue of NZTCS status patches. "
        "Read-only: never edits Wikipedia. "
        "Use 'nztcs-wiki-bot fetch REPORT_ID' to download a report CSV first.",
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


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "fetch":
        from . import fetch

        return fetch.main(argv[1:])

    args = build_parser().parse_args(argv)

    if not Path(args.csv).exists():
        print(f"error: CSV not found: {args.csv}", file=sys.stderr)
        return 2

    try:
        client = WikiClient(contact=args.contact, cache_dir=Path(args.cache))
    except MissingContactError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    config = PipelineConfig(limit=args.limit, species=args.species)

    print(f"Loading {args.csv} ...", flush=True)
    buckets = run_from_csv(args.csv, client, config)
    write_review(args.out, buckets)

    print(
        f"Done. rows_in={buckets.rows_in} "
        f"matched={len(buckets.matched)} ambiguous={len(buckets.ambiguous)} "
        f"unmapped={len(buckets.unmapped)} no_match={len(buckets.no_match)} "
        f"skipped={len(buckets.skipped)}",
        flush=True,
    )
    print(f"Review queue written to {args.out}/", flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
