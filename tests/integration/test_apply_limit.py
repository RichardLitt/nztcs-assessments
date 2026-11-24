"""--limit counts entries you're asked about, not ones skipped without asking."""

from __future__ import annotations

import responses

from nztcs_wiki_bot import apply
from nztcs_wiki_bot.editor import WikiEditor
from nztcs_wiki_bot.output import Buckets, write_review
from tests.integration.test_apply import ENTRIES, PASSWORD, _scripted, _wiki


def _session(tmp_path, wiki, answers, limit, entries=ENTRIES):
    review = tmp_path / "review"
    if not (review / "matched.jsonl").exists():
        write_review(review, Buckets(rows_in=len(entries), matched=list(entries)))
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        rc = apply.main(
            ["--review", str(review), "--username", "Richlitt@nztcs",
             "--contact", "you@example.org", "--interval", "5", "--limit", str(limit)],
            editor_factory=lambda c: WikiEditor(c, sleep=lambda s: None),
            ask=_scripted(*answers),
            get_password=lambda prompt: PASSWORD,
        )
    assert rc == 0
    return review


def test_already_applied_entries_dont_use_up_the_limit(tmp_path, capsys):
    wiki = _wiki()
    wiki.pages["Pūriri moth"]["text"] = ENTRIES[0].after  # already applied
    _session(tmp_path, wiki, ["y"], limit=1)
    out = capsys.readouterr().out
    assert [e["title"] for e in wiki.edits] == ["Taxon shorthand"]
    assert "Reached --limit 1." in out
    assert "Legacy" not in wiki.fetched  # stopped before the third entry


def test_changed_entries_dont_use_up_the_limit(tmp_path):
    wiki = _wiki()
    wiki.pages["Pūriri moth"]["text"] += "\nSomeone else's edit."
    wiki.pages["Taxon shorthand"]["text"] += "\nAnother edit."
    _session(tmp_path, wiki, ["n"], limit=1)
    assert wiki.fetched == ["Pūriri moth", "Taxon shorthand", "Legacy"]


def test_both_yes_and_no_count(tmp_path, capsys):
    wiki = _wiki()
    _session(tmp_path, wiki, ["n", "y"], limit=2)
    assert [e["title"] for e in wiki.edits] == ["Taxon shorthand"]
    assert "Legacy" not in wiki.fetched
    assert "asking about at most 2" in capsys.readouterr().out


def test_previous_skips_dont_use_up_the_limit(tmp_path):
    wiki = _wiki()
    _session(tmp_path, wiki, ["n"], limit=1)  # skip Pūriri moth
    wiki.fetched.clear()
    _session(tmp_path, wiki, ["y"], limit=1)  # hidden, so Taxon shorthand is asked
    assert [e["title"] for e in wiki.edits] == ["Taxon shorthand"]
    assert wiki.fetched == ["Taxon shorthand"]


def test_limit_not_reached_goes_through_everything(tmp_path, capsys):
    wiki = _wiki()
    for e in ENTRIES:
        wiki.pages[e.title]["text"] = e.after
    _session(tmp_path, wiki, [], limit=5)
    out = capsys.readouterr().out
    assert "Reached --limit" not in out
    assert wiki.fetched == ["Pūriri moth", "Taxon shorthand", "Legacy"]
