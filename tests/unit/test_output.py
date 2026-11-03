import json

from nztcs_wiki_bot.output import Buckets, MatchEntry, unified_diff, write_review


def _entry(species_id="100", code="NV"):
    before = "{{Speciesbox\n| genus = Aenetus\n| species = virescens\n}}\n"
    after = before.replace("}}", "| status = NV\n}}")
    return MatchEntry(
        species_id=species_id,
        binomial="Aenetus virescens",
        common_name="pūriri moth",
        title="Pūriri moth",
        status_code=code,
        action="insert",
        before=before,
        after=after,
        diff=unified_diff(before, after, "Pūriri moth"),
    )


def test_matched_jsonl_is_valid_json(tmp_path):
    b = Buckets(rows_in=1, matched=[_entry()])
    write_review(tmp_path, b)
    lines = (tmp_path / "matched.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    for key in ("species_id", "binomial", "title", "status_code", "before", "after", "diff"):
        assert key in obj


def test_matched_md_has_anchor(tmp_path):
    write_review(tmp_path, Buckets(rows_in=1, matched=[_entry("12345")]))
    md = (tmp_path / "matched.md").read_text(encoding="utf-8")
    assert 'id="speciesId-12345"' in md
    assert "```diff" in md
    assert "- **Common name:** pūriri moth\n" in md


def test_stats_balanced(tmp_path):
    b = Buckets(
        rows_in=4,
        matched=[_entry("1")],
        ambiguous=[{"species_id": "2", "binomial": "X y"}],
        no_match=[{"binomial": "A b"}],
        skipped=[{"name": "Z sp. A", "reason": "undescribed"}],
    )
    write_review(tmp_path, b)
    stats = (tmp_path / "stats.txt").read_text(encoding="utf-8")
    assert "balanced   True" in stats
    assert "rows_in    4" in stats


def test_tsv_files_written(tmp_path):
    b = Buckets(
        rows_in=2,
        unmapped=[{"binomial": "A b", "status_title": "Not assessed", "reason": "non-status"}],
        skipped=[{"name": 'X "y"', "reason": "quoted_genus"}],
    )
    write_review(tmp_path, b)
    unmapped = (tmp_path / "unmapped.tsv").read_text(encoding="utf-8")
    assert "Not assessed" in unmapped
    assert unmapped.splitlines()[0] == "binomial\tstatus_title\treason"


def test_output_is_deterministic(tmp_path):
    b1 = Buckets(rows_in=2, matched=[_entry("2"), _entry("1")])
    out1 = tmp_path / "a"
    out2 = tmp_path / "b"
    write_review(out1, b1)
    write_review(out2, Buckets(rows_in=2, matched=[_entry("1"), _entry("2")]))
    assert (out1 / "matched.jsonl").read_bytes() == (out2 / "matched.jsonl").read_bytes()
