"""Entries you answer n to stay hidden in later apply sessions."""

from __future__ import annotations

import responses

from nztcs_wiki_bot import apply
from nztcs_wiki_bot.editor import WikiEditor
from nztcs_wiki_bot.output import Buckets, write_review
from tests.integration.test_apply import ENTRIES, PASSWORD, _scripted, _wiki


def _session(review, wiki, answers, extra=()):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        return apply.main(
            ["--review", str(review), "--username", "Richlitt@nztcs",
             "--contact", "you@example.org", "--interval", "5", *extra],
            editor_factory=lambda c: WikiEditor(c, sleep=lambda s: None),
            ask=_scripted(*answers),
            get_password=lambda prompt: PASSWORD,
        )


def _review(tmp_path):
    review = tmp_path / "review"
    write_review(review, Buckets(rows_in=2, matched=list(ENTRIES[:2])))
    return review


def test_skipped_entry_is_not_shown_again(tmp_path, capsys):
    review, wiki = _review(tmp_path), _wiki(ENTRIES[:2])
    _session(review, wiki, ["n", "n"])
    capsys.readouterr()
    # Second session: no prompts at all (the scripted ask would fail on any).
    _session(review, wiki, [])
    out = capsys.readouterr().out
    assert "Not showing 2 entries you skipped before. Use --show-skipped" in out
    assert "Nothing to apply." in out
    assert wiki.fetched == ["Pūriri moth", "Taxon shorthand"]  # only from session 1


def test_only_skipped_entries_are_hidden(tmp_path, capsys):
    review, wiki = _review(tmp_path), _wiki(ENTRIES[:2])
    _session(review, wiki, ["n", "q"])  # skip the first, quit at the second
    capsys.readouterr()
    _session(review, wiki, ["n"])  # only the second is asked about
    out = capsys.readouterr().out
    assert "Not showing 1 entry you skipped before." in out
    assert "Taxon shorthand" in out and "[1/1]" in out


def test_show_skipped_brings_them_back_and_a_save_sticks(tmp_path, capsys):
    review, wiki = _review(tmp_path), _wiki(ENTRIES[:1])
    write_review(review, Buckets(rows_in=1, matched=list(ENTRIES[:1])))
    _session(review, wiki, ["n"])
    _session(review, wiki, ["y"], extra=["--show-skipped"])
    assert len(wiki.edits) == 1
    assert apply.previously_skipped(review / "applied.tsv") == set()
    capsys.readouterr()
    _session(review, wiki, [])  # now already applied, not hidden as skipped
    out = capsys.readouterr().out
    assert "Not showing" not in out and "this change is already there" in out


def test_skips_survive_a_fresh_review_run(tmp_path):
    review, wiki = _review(tmp_path), _wiki(ENTRIES[:2])
    _session(review, wiki, ["n", "n"])
    write_review(review, Buckets(rows_in=2, matched=list(ENTRIES[:2])))  # re-run the tool
    assert apply.previously_skipped(review / "applied.tsv") == {
        ("1", "Pūriri moth"), ("2", "Taxon shorthand"),
    }
