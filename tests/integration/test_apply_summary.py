"""Edit summaries link to a page explaining the tool, once that page exists."""

from __future__ import annotations

import responses

from nztcs_wiki_bot import apply
from nztcs_wiki_bot.editor import WikiEditor
from tests.integration.test_apply import ENTRIES, PASSWORD, _review, _scripted, _wiki


def _run(tmp_path, wiki, extra=()):
    review = _review(tmp_path, ENTRIES[:1])
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        rc = apply.main(
            ["--review", str(review), "--username", "Richlitt@nztcs",
             "--contact", "you@example.org", *extra],
            editor_factory=lambda c: WikiEditor(c, sleep=lambda s: None),
            ask=_scripted("y"),
            get_password=lambda prompt: PASSWORD,
        )
    assert rc == 0
    (edit,) = wiki.edits
    return edit["summary"]


def test_summary_links_to_tool_page_when_it_exists(tmp_path, capsys):
    wiki = _wiki(ENTRIES[:1])
    wiki.pages["User:Richlitt/nztcs-wiki-bot"] = {"text": "About", "revid": 1, "ts": "x"}
    summary = _run(tmp_path, wiki)
    assert summary == (
        "Add NZTCS conservation status: Nationally Vulnerable (NV); "
        "assisted edit with [[User:Richlitt/nztcs-wiki-bot|nztcs-wiki-bot]]"
    )
    assert "Tip: create the page" not in capsys.readouterr().out


def test_summary_is_plain_and_tip_shown_when_page_missing(tmp_path, capsys):
    summary = _run(tmp_path, _wiki(ENTRIES[:1]))
    assert summary.endswith("; assisted edit with nztcs-wiki-bot")
    assert "[[" not in summary
    assert "Tip: create the page [[User:Richlitt/nztcs-wiki-bot]]" in capsys.readouterr().out


def test_tool_page_can_be_overridden(tmp_path):
    wiki = _wiki(ENTRIES[:1])
    wiki.pages["User:Richlitt/Tools"] = {"text": "About", "revid": 1, "ts": "x"}
    summary = _run(tmp_path, wiki, extra=["--tool-page", "User:Richlitt/Tools"])
    assert summary.endswith("assisted edit with [[User:Richlitt/Tools|nztcs-wiki-bot]]")
