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
    filtered: int = 0  # rows left out by --species / --limit


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


@dataclass
class PlainEdit:
    """One change, as plain lines a reviewer can copy without diff markers.

    ``op`` is ``insert``, ``replace`` or ``delete``. For an insert, ``above``
    is the existing line the new lines go directly above (or ``below`` the
    line they follow, when there's nothing after them).
    """

    op: str
    remove: list[str]
    add: list[str]
    above: str | None = None
    below: str | None = None


def plain_edits(before: str, after: str) -> list[PlainEdit]:
    """Turn a before/after pair into copy-ready edits, one per changed run.

    >>> e = plain_edits("{{Box\\n| genus = A\\n}}", "{{Box\\n| status = NT\\n| genus = A\\n}}")
    >>> e[0].op, e[0].add, e[0].above
    ('insert', ['| status = NT'], '| genus = A')
    >>> e = plain_edits("| status = NC\\n| x = 1", "| status = NE\\n| x = 1")
    >>> e[0].op, e[0].remove, e[0].add
    ('replace', ['| status = NC'], ['| status = NE'])
    """
    a, b = before.splitlines(), after.splitlines()
    edits = []
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            above = a[i1] if i1 < len(a) else None
            # "Above }}" or "above a blank line" doesn't say where; an article has
            # many of those. Point at the line before instead.
            if above is not None and _is_vague(above) and i1 > 0:
                above = None
            below = a[i1 - 1] if above is None and i1 > 0 else None
            edits.append(PlainEdit("insert", [], b[j1:j2], above=above, below=below))
        else:
            edits.append(PlainEdit(tag, a[i1:i2], b[j1:j2]))
    return edits


def _is_vague(line: str) -> bool:
    """Whether a line is too generic to say where an insertion goes."""
    text = line.strip()
    return text == "" or text.startswith("}}")


def _code(line: str, limit: int = 80) -> str:
    """An existing line, shortened, as inline code for 'directly above …'."""
    text = line.strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return "`` " + text + " ``" if "`" in text else f"`{text}`"


def _block(lines: list[str]) -> list[str]:
    return ["```wikitext", *lines, "```"]


def _render_edit(edit: PlainEdit) -> list[str]:
    n = "this line" if max(len(edit.remove), len(edit.add)) == 1 else "these lines"
    if edit.op == "insert":
        if edit.above is not None:
            where = f"directly above {_code(edit.above)}"
        elif edit.below is not None:
            where = f"directly below {_code(edit.below)}"
        else:
            where = "into the article"
        return [f"**Add** {n} {where}:", "", *_block(edit.add)]
    if edit.op == "delete":
        return [f"**Remove** {n}:", "", *_block(edit.remove)]
    return [f"**Replace** {n}:", "", *_block(edit.remove), "", "**with:**", "", *_block(edit.add)]


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
            record = asdict(e)
            record["edits"] = [asdict(x) for x in plain_edits(e.before, e.after)]
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    lines = ["# Matched — proposed NZTCS patches", ""]
    lines.append(
        f"_{len(entries)} confident matches. Each entry gives the lines to copy into "
        "the article as they are, with the full diff underneath for checking._"
    )
    lines.append("")
    for e in entries:
        lines.append(f'<a id="{_anchor(e.species_id)}"></a>')
        url = f"https://en.wikipedia.org/wiki/{e.title.replace(' ', '_')}"
        lines.append(f"## {e.binomial} → [{e.title}]({url})")
        lines.append("")
        lines.append(f"- **Common name:** {e.common_name or '—'}")
        lines.append(f"- **NZTCS status:** `{e.status_code}`")
        lines.append(f"- **Patch action:** {e.action}")
        lines.append("")
        for edit in plain_edits(e.before, e.after):
            lines.extend(_render_edit(edit))
            lines.append("")
        lines.append("<details>")
        lines.append("<summary>Full diff</summary>")
        lines.append("")
        lines.append("```diff")
        lines.append(e.diff.rstrip("\n"))
        lines.append("```")
        lines.append("")
        lines.append("</details>")
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
        len(b.matched)
        + len(b.ambiguous)
        + len(b.unmapped)
        + len(b.no_match)
        + len(b.skipped)
        + b.filtered
    )
    lines = [
        f"rows_in    {b.rows_in}",
        f"matched    {len(b.matched)}",
        f"ambiguous  {len(b.ambiguous)}",
        f"unmapped   {len(b.unmapped)}",
        f"no_match   {len(b.no_match)}",
        f"skipped    {len(b.skipped)}",
        f"filtered   {b.filtered}",
        f"accounted  {accounted}",
        f"balanced   {accounted == b.rows_in}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
