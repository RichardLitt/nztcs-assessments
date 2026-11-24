"""Orchestrate the bot: load → filter → resolve → verify → patch → emit.

This is the glue that wires the modules together. It is deliberately free of
I/O details (CSV parsing, HTTP, file writing live in their own modules) so it can
be unit-tested against a fake :class:`~nztcs_wiki_bot.wiki_client.WikiClient`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from . import citation, name_cleaner, speciesbox, status_map
from .csv_loader import Row, load_rows
from .output import Buckets, MatchEntry, unified_diff
from .wiki_client import ResolvedTitle


class WikiReader(Protocol):
    """The read-only slice of :class:`~nztcs_wiki_bot.wiki_client.WikiClient` used here."""

    def resolve_titles(self, titles: list[str]) -> dict[str, ResolvedTitle]: ...

    def fetch_wikitext(self, title: str) -> str | None: ...


@dataclass
class PipelineConfig:
    limit: int | None = None
    species: str | None = None  # filter to a single binomial substring


def run(rows: list[Row], client: WikiReader, config: PipelineConfig | None = None) -> Buckets:
    """Run the full pipeline over ``rows`` and return populated :class:`Buckets`."""
    config = config or PipelineConfig()
    buckets = Buckets(rows_in=len(rows))

    # 1. Clean names + apply skip rules; collect resolvable binomials.
    pending: list[tuple[Row, name_cleaner.CleanName]] = []
    for row in rows:
        clean = name_cleaner.clean_name(row.nztcs_species_name)
        if clean.skipped:
            buckets.skipped.append(
                {"name": row.nztcs_species_name, "reason": clean.skip_reason}
            )
            continue
        if config.species and config.species.lower() not in (clean.binomial or "").lower():
            buckets.filtered += 1
            continue
        pending.append((row, clean))

    if config.limit is not None and len(pending) > config.limit:
        buckets.filtered += len(pending) - config.limit
        pending = pending[: config.limit]

    # 2. Resolve all binomials in batches (one network phase).
    binomials = [c.binomial for _, c in pending if c.binomial]
    resolved = client.resolve_titles(binomials)

    # 3. Per row: verify status mapping, fetch wikitext, verify taxon, patch.
    for row, clean in pending:
        binomial = clean.binomial or ""

        # Status mapping — fail loud per design, route to unmapped bucket.
        title_status = row.conservation_status_title
        code = status_map.code_for(title_status, row.criteria_title)
        if code is None:
            buckets.unmapped.append(
                {
                    "binomial": binomial,
                    "status_title": title_status,
                    "reason": status_map.unmapped_reason(title_status),
                }
            )
            continue

        res = resolved.get(binomial)
        if res is None or res.missing or not res.canonical:
            buckets.no_match.append({"binomial": binomial, "reason": "missing"})
            continue

        wikitext = client.fetch_wikitext(res.canonical)
        if not wikitext:
            buckets.no_match.append({"binomial": binomial, "reason": "no-wikitext"})
            continue

        infobox = speciesbox.find_infobox(wikitext)
        if infobox is None:
            buckets.ambiguous.append(
                {
                    "species_id": row.species_id,
                    "binomial": binomial,
                    "title": res.canonical,
                    "reason": "no-speciesbox",
                }
            )
            continue
        if not speciesbox.verify_taxon(infobox, clean.genus or "", clean.species or ""):
            buckets.ambiguous.append(
                {
                    "species_id": row.species_id,
                    "binomial": binomial,
                    "title": res.canonical,
                    "reason": "taxon-mismatch",
                }
            )
            continue

        ref_name, ref_wikitext = citation.build_ref(row, wikitext)
        patch = speciesbox.patch_status(
            wikitext, clean.genus or "", clean.species or "", code, ref_name, ref_wikitext
        )
        if not patch.changed:
            buckets.ambiguous.append(
                {
                    "species_id": row.species_id,
                    "binomial": binomial,
                    "title": res.canonical,
                    "reason": "already-current",
                }
            )
            continue

        buckets.matched.append(
            MatchEntry(
                species_id=row.species_id,
                binomial=binomial,
                common_name=row.common_name,
                title=res.canonical,
                status_code=code,
                action=patch.action,
                before=patch.before,
                after=patch.after,
                diff=unified_diff(patch.before, patch.after, res.canonical),
            )
        )

    return buckets


def run_from_csv(
    csv_path: str, client: WikiReader, config: PipelineConfig | None = None
) -> Buckets:
    """Convenience: load the CSV then :func:`run`."""
    return run(load_rows(csv_path), client, config)
