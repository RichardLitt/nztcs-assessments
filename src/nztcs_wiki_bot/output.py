"""Emit the review queue: JSONL + Markdown per bucket, plus TSVs and stats.

Output layout (under the ``--out`` directory)::

    review/
    ├── matched.jsonl / matched.md
    ├── ambiguous.jsonl / ambiguous.md
    ├── unmapped.tsv      # status title had no code
    ├── no_match.tsv      # no Wikipedia article
    ├── skipped.tsv       # undescribed / quoted-genus
    └── stats.txt
"""

from __future__ import annotations

import difflib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class MatchEntry:
    species_id: str
    binomial: str
    common_name: str
    title: str
    status_code: str
    action: str
    before: str
    after: str
    diff: str


@dataclass
class Buckets:
    matched: list[MatchEntry] = field(default_factory=list)
    ambiguous: list[dict] = field(default_factory=list)
    unmapped: list[dict] = field(default_factory=list)
    no_match: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    rows_in: int = 0


def unified_diff(before: str, after: str, title: str) -> str:
    """Return a unified diff between two wikitext blobs."""
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{title} (current)",
        tofile=f"{title} (proposed)",
        n=3,
    )
    return "".join(diff)


def _anchor(species_id: str) -> str:
    return f"speciesId-{species_id}"


def write_review(out_dir: str | Path, buckets: Buckets) -> None:
    """Write all review-queue files under ``out_dir`` deterministically."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    _write_matched(out, buckets.matched)
    _write_ambiguous(out, buckets.ambiguous)
    _write_tsv(out / "unmapped.tsv", ["binomial", "status_title", "reason"], buckets.unmapped)
    _write_tsv(out / "no_match.tsv", ["binomial", "reason"], buckets.no_match)
    _write_tsv(out / "skipped.tsv", ["name", "reason"], buckets.skipped)
    _write_stats(out / "stats.txt", buckets)


def _write_matched(out: Path, entries: list[MatchEntry]) -> None:
    entries = sorted(entries, key=lambda e: e.species_id)
    with (out / "matched.jsonl").open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(asdict(e), ensure_ascii=False, sort_keys=True) + "\n")

    lines = ["# Matched — proposed NZTCS patches", ""]
    lines.append(
        f"_{len(entries)} confident matches. "
        "Review each diff against the live article before pasting._"
    )
    lines.append("")
    for e in entries:
        lines.append(f'<a id="{_anchor(e.species_id)}"></a>')
        url = f"https://en.wikipedia.org/wiki/{e.title.replace(' ', '_')}"
        lines.append(f"## {e.binomial} → [{e.title}]({url})")
        lines.append("")
        common = f" ({e.common_name})" if e.common_name else ""
        lines.append(f"- **Common name:**{common or ' —'}")
        lines.append(f"- **NZTCS status:** `{e.status_code}`")
        lines.append(f"- **Patch action:** {e.action}")
        lines.append("")
        lines.append("```diff")
        lines.append(e.diff.rstrip("\n"))
        lines.append("```")
        lines.append("")
    (out / "matched.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ambiguous(out: Path, entries: list[dict]) -> None:
    entries = sorted(entries, key=lambda e: e.get("species_id", ""))
    with (out / "ambiguous.jsonl").open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")

    lines = ["# Ambiguous — needs human eyes", ""]
    lines.append(f"_{len(entries)} titles resolved but the Speciesbox check failed._")
    lines.append("")
    for e in entries:
        title = e.get("title") or "(no article)"
        lines.append(f"## {e.get('binomial', '?')} — {e.get('reason', 'unknown')}")
        if e.get("title"):
            url = title.replace(" ", "_")
            lines.append(f"- Article: [{title}](https://en.wikipedia.org/wiki/{url})")
        lines.append("")
    (out / "ambiguous.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_tsv(path: Path, header: list[str], rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: tuple(str(r.get(h, "")) for h in header))
    lines = ["\t".join(header)]
    for r in rows:
        lines.append("\t".join(str(r.get(h, "")).replace("\t", " ") for h in header))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stats(path: Path, b: Buckets) -> None:
    accounted = (
        len(b.matched) + len(b.ambiguous) + len(b.unmapped) + len(b.no_match) + len(b.skipped)
    )
    lines = [
        f"rows_in    {b.rows_in}",
        f"matched    {len(b.matched)}",
        f"ambiguous  {len(b.ambiguous)}",
        f"unmapped   {len(b.unmapped)}",
        f"no_match   {len(b.no_match)}",
        f"skipped    {len(b.skipped)}",
        f"accounted  {accounted}",
        f"balanced   {accounted == b.rows_in}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
