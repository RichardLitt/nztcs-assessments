"""``nztcs-wiki-bot apply`` against a fake MediaWiki that records every write.

The fake tracks page text and revision IDs, checks login, tokens and
``baserevid`` like the real API, and keeps a list of the edits it accepted, so
each test can say exactly what was (or wasn't) saved.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from nztcs_wiki_bot import apply, speciesbox
from nztcs_wiki_bot.citation import TODO_AUTHORS
from nztcs_wiki_bot.editor import WikiEditor
from nztcs_wiki_bot.output import Buckets, MatchEntry, unified_diff, write_review
from nztcs_wiki_bot.wiki_client import API_URL
from tests.conftest import wikitext

PASSWORD = "s3cret-bot-password"
REF = '<ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>'


class FakeWiki:
    def __init__(self, pages: dict[str, str]):
        self.pages = {
            t: {"text": text, "revid": 1000 + i, "ts": "2026-11-24T00:00:00Z"}
            for i, (t, text) in enumerate(pages.items())
        }
        self.edits: list[dict] = []
        self.fetched: list[str] = []
        self.logged_in = False
        self.messages_after_saves: int | None = None
        self.fail_next_edit: str | None = None
        self.maxlag_next_get = False
        self._next_rev = 5000

    def install(self, rsps: responses.RequestsMock) -> None:
        rsps.add_callback(responses.GET, API_URL, callback=self._get)
        rsps.add_callback(responses.POST, API_URL, callback=self._post)

    @staticmethod
    def _ok(body: dict, headers: dict | None = None):
        return (200, headers or {}, json.dumps(body))

    def _get(self, request):
        p = {k: v[0] for k, v in parse_qs(urlparse(request.url).query).items()}
        if self.maxlag_next_get:
            self.maxlag_next_get = False
            return self._ok({"error": {"code": "maxlag", "info": "lagged"}}, {"Retry-After": "2"})
        if p.get("meta") == "tokens" and p.get("type") == "login":
            return self._ok({"query": {"tokens": {"logintoken": "LOGIN+\\"}}})
        if p.get("meta") == "tokens":
            assert self.logged_in, "csrf token requested before login"
            return self._ok({"query": {"tokens": {"csrftoken": "CSRF+\\"}}})
        if p.get("meta") == "userinfo":
            limit = self.messages_after_saves
            has = limit is not None and len(self.edits) >= limit
            return self._ok({"query": {"userinfo": {"name": "Richlitt", "messages": has}}})
        if p.get("prop") == "revisions":
            title = p["titles"]
            if not title.startswith("User:"):  # articles only, not the tool page
                self.fetched.append(title)
            page = self.pages.get(title)
            if page is None:
                return self._ok({"curtimestamp": "2026-11-24T01:00:00Z",
                                 "query": {"pages": [{"title": title, "missing": True}]}})
            rev = {"revid": page["revid"], "timestamp": page["ts"],
                   "slots": {"main": {"content": page["text"]}}}
            return self._ok({"curtimestamp": "2026-11-24T01:00:00Z",
                             "query": {"pages": [{"title": title, "revisions": [rev]}]}})
        raise AssertionError(f"unexpected GET {p}")

    def _post(self, request):
        p = {k: v[0] for k, v in parse_qs(request.body).items()}
        if p["action"] == "login":
            assert p["lgtoken"] == "LOGIN+\\"
            if p["lgpassword"] != PASSWORD:
                return self._ok({"login": {"result": "Failed", "reason": "Incorrect password"}})
            self.logged_in = True
            return self._ok({"login": {"result": "Success", "lgusername": "Richlitt"}})
        if p["action"] == "edit":
            assert self.logged_in and p["token"] == "CSRF+\\"
            if self.fail_next_edit:
                code, self.fail_next_edit = self.fail_next_edit, None
                return self._ok({"error": {"code": code, "info": "refused"}})
            page = self.pages[p["title"]]
            if int(p["baserevid"]) != page["revid"]:
                return self._ok({"error": {"code": "editconflict", "info": "conflict"}})
            self._next_rev += 1
            page.update(text=p["text"], revid=self._next_rev)
            self.edits.append(p)
            return self._ok({"edit": {"result": "Success", "newrevid": self._next_rev}})
        raise AssertionError(f"unexpected POST {p}")


def _entry(species_id: str, title: str, fixture: str, genus: str, species: str, code="NV"):
    before = wikitext(fixture)
    patch = speciesbox.patch_status(before, genus, species, code, "NZTCS2025", REF)
    return MatchEntry(
        species_id=species_id, binomial=f"{genus} {species}", common_name="", title=title,
        status_code=code, action=patch.action, before=patch.before, after=patch.after,
        diff=unified_diff(patch.before, patch.after, title),
    )


ENTRIES = [
    _entry("1", "Pūriri moth", "puriri_moth", "Aenetus", "virescens"),
    _entry("2", "Taxon shorthand", "taxon_shorthand", "Aenetus", "virescens", "NT"),
    _entry("3", "Legacy", "taxobox_legacy", "Aoraia", "oreobolae", "DD"),
]


def _review(tmp_path: Path, entries=ENTRIES) -> Path:
    review = tmp_path / "review"
    write_review(review, Buckets(rows_in=len(entries), matched=list(entries)))
    return review


def _wiki(entries=ENTRIES) -> FakeWiki:
    return FakeWiki({e.title: e.before for e in entries})


def _scripted(*answers):
    it = iter(answers)

    def ask(prompt):
        try:
            return next(it)
        except StopIteration:
            raise AssertionError(f"unexpected prompt: {prompt!r}") from None

    return ask


def _run(tmp_path, wiki, answers, entries=ENTRIES, extra=()):
    review = _review(tmp_path, entries)
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        rc = apply.main(
            ["--review", str(review), "--username", "Richlitt@nztcs",
             "--contact", "you@example.org", "--interval", "5", *extra],
            editor_factory=lambda c: WikiEditor(c, sleep=lambda s: None),
            ask=_scripted(*answers),
            get_password=lambda prompt: PASSWORD,
        )
    log_path = review / "applied.tsv"
    log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    return rc, log


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(apply.time, "sleep", lambda s: None)


def test_yes_saves_exactly_the_patch(tmp_path):
    wiki = _wiki()
    rc, log = _run(tmp_path, wiki, ["y"], extra=["--limit", "1"])
    assert rc == 0
    (edit,) = wiki.edits
    assert edit["title"] == "Pūriri moth"
    assert edit["text"] == ENTRIES[0].after
    assert edit["summary"] == (
        "Add NZTCS conservation status: Nationally Vulnerable (NV); "
        "assisted edit with nztcs-wiki-bot"
    )
    assert edit["nocreate"] == "1" and edit["assert"] == "user"
    assert edit["baserevid"] == "1000" and edit["basetimestamp"] == "2026-11-24T00:00:00Z"
    assert edit["starttimestamp"] == "2026-11-24T01:00:00Z"
    assert "\tPūriri moth\tsaved\t5001\n" in log


def test_no_skips_and_quit_stops_before_later_entries(tmp_path):
    wiki = _wiki()
    rc, log = _run(tmp_path, wiki, ["n", "q"])
    assert rc == 0
    assert wiki.edits == []
    assert wiki.fetched == ["Pūriri moth", "Taxon shorthand"]  # third never fetched
    assert "\tPūriri moth\tskipped\t" in log
    assert "Taxon shorthand" not in log


def test_changed_article_is_skipped_without_asking(tmp_path):
    wiki = _wiki(ENTRIES[:1])
    wiki.pages["Pūriri moth"]["text"] += "\nSomeone else's new sentence."
    rc, log = _run(tmp_path, wiki, [], entries=ENTRIES[:1])
    assert wiki.edits == [] and "\tchanged\t" in log


def test_already_applied_is_skipped_without_asking(tmp_path):
    wiki = _wiki(ENTRIES[:1])
    wiki.pages["Pūriri moth"]["text"] = ENTRIES[0].after
    rc, log = _run(tmp_path, wiki, [], entries=ENTRIES[:1])
    assert wiki.edits == [] and "\talready-applied\t" in log


def test_rerun_after_saving_skips_saved_entries(tmp_path):
    wiki = _wiki(ENTRIES[:1])
    _run(tmp_path, wiki, ["y"], entries=ENTRIES[:1])
    _, log = _run(tmp_path, wiki, [], entries=ENTRIES[:1])
    assert len(wiki.edits) == 1 and "\talready-applied\t" in log


def test_nobots_is_skipped(tmp_path):
    entry = _entry("9", "Opted out", "puriri_moth", "Aenetus", "virescens")
    entry.before = "{{bots|deny=Richlitt}}\n" + entry.before
    entry.after = "{{bots|deny=Richlitt}}\n" + entry.after
    wiki = _wiki([entry])
    _, log = _run(tmp_path, wiki, [], entries=[entry])
    assert wiki.edits == [] and "\tnobots\t" in log


def test_todo_citation_is_never_saved(tmp_path):
    entry = _entry("8", "Scaffold", "puriri_moth", "Aenetus", "virescens")
    scaffold = f"<ref>{{{{cite report | author = {TODO_AUTHORS} }}}}</ref>"
    entry.after = entry.after.replace(REF, scaffold)
    wiki = _wiki([entry])
    _, log = _run(tmp_path, wiki, [], entries=[entry])
    assert wiki.edits == [] and wiki.fetched == [] and "\tneeds-citation\t" in log


def test_missing_article_is_skipped(tmp_path):
    wiki = FakeWiki({})
    _, log = _run(tmp_path, wiki, [], entries=ENTRIES[:1])
    assert "\tmissing\t" in log


def test_stops_when_a_talk_page_message_arrives(tmp_path, capsys):
    wiki = _wiki()
    wiki.messages_after_saves = 1
    rc, log = _run(tmp_path, wiki, ["y"])
    assert rc == 0
    assert len(wiki.edits) == 1
    assert wiki.fetched == ["Pūriri moth"]
    assert "Special:MyTalk" in capsys.readouterr().out


def test_refused_edit_is_logged_and_run_continues(tmp_path):
    wiki = _wiki(ENTRIES[:2])
    wiki.fail_next_edit = "abusefilter-disallowed"
    _, log = _run(tmp_path, wiki, ["y", "y"], entries=ENTRIES[:2])
    assert [e["title"] for e in wiki.edits] == ["Taxon shorthand"]
    assert "\terror:abusefilter-disallowed\t" in log


def test_edit_conflict_is_refused_by_baserevid(tmp_path):
    # The page changes between fetch and save: MediaWiki's conflict check wins.
    wiki = _wiki(ENTRIES[:1])
    original_get = wiki._get

    def get_then_bump(request):
        resp = original_get(request)
        if "prop=revisions" in request.url:
            wiki.pages["Pūriri moth"]["revid"] += 1
        return resp

    wiki._get = get_then_bump
    _, log = _run(tmp_path, wiki, ["y"], entries=ENTRIES[:1])
    assert wiki.edits == [] and "\terror:editconflict\t" in log


def test_login_failure_saves_nothing(tmp_path, capsys):
    review = _review(tmp_path)
    wiki = _wiki()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        rc = apply.main(
            ["--review", str(review), "--username", "Richlitt@nztcs",
             "--contact", "you@example.org"],
            editor_factory=WikiEditor, ask=_scripted(), get_password=lambda p: "wrong",
        )
    assert rc == 2 and wiki.edits == []
    assert "login failed: Incorrect password" in capsys.readouterr().err


def test_password_is_never_printed_or_logged(tmp_path, capsys):
    wiki = _wiki()
    _, log = _run(tmp_path, wiki, ["y", "n", "y"])
    out = capsys.readouterr()
    assert PASSWORD not in out.out + out.err + log
    assert all("lgpassword" not in e and PASSWORD not in json.dumps(e) for e in wiki.edits)


def test_interval_is_enforced_between_saves(tmp_path):
    wiki = _wiki(ENTRIES[:2])
    now = [100.0]
    slept: list[float] = []
    review = _review(tmp_path, ENTRIES[:2])
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        editor = WikiEditor("you@example.org", sleep=lambda s: None)
        editor.login("Richlitt@nztcs", PASSWORD)
        applier = apply.Applier(
            editor, review / "applied.tsv", ask=_scripted("y", "y"), say=lambda s: None,
            interval=10, clock=lambda: now[0], sleep=slept.append,
        )
        now[0] = 100.0
        applier.run(apply.load_entries(review / "matched.jsonl"))
    assert len(wiki.edits) == 2
    assert slept == [10.0]  # the clock didn't move, so the full interval is waited


def test_diff_and_open_keep_asking(tmp_path):
    wiki = _wiki(ENTRIES[:1])
    opened: list[str] = []
    said: list[str] = []
    review = _review(tmp_path, ENTRIES[:1])
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        editor = WikiEditor("you@example.org", sleep=lambda s: None)
        editor.login("Richlitt@nztcs", PASSWORD)
        applier = apply.Applier(
            editor, review / "applied.tsv", ask=_scripted("d", "o", "?", "y"),
            say=said.append, open_url=opened.append, sleep=lambda s: None,
        )
        applier.run(apply.load_entries(review / "matched.jsonl"))
    assert opened == ["https://en.wikipedia.org/wiki/P%C5%ABriri_moth"]
    assert any(s.startswith("--- Pūriri moth (current)") for s in said)
    assert len(wiki.edits) == 1


def test_shows_the_whole_infobox_before_asking(tmp_path, capsys):
    wiki = _wiki(ENTRIES[:1])
    _run(tmp_path, wiki, ["n"], entries=ENTRIES[:1])
    out = capsys.readouterr().out
    expected = "\n".join([
        "    {{Speciesbox",
        "    | image = Aenetus virescens.jpg",
        "  + | status = NV",
        "  + | status_system = NZTCS",
        "  + | status_ref = " + REF,
        "    | genus = Aenetus",
        "    | species = virescens",
        "    | authority = ([[Edward Doubleday|Doubleday]], 1843)",
        "    }}",
    ])
    assert expected in out
    assert "\033[" not in out  # no colour codes when not a terminal


def test_whole_infobox_shows_existing_status_for_secondary(tmp_path):
    entry = _entry("7", "IUCN article", "iucn_only", "Aenetus", "virescens")
    view = apply.infobox_view(apply.Entry(
        entry.species_id, entry.binomial, entry.title, entry.status_code,
        entry.action, entry.before, entry.after, entry.diff,
    ))
    assert "    | status = LC" in view and "    | status_system = IUCN3.1" in view
    assert "  + | status2 = NV" in view


def test_whole_infobox_marks_replaced_lines_and_colours_them(tmp_path):
    entry = _entry("6", "Snail", "powelliphanta_augusta", "Powelliphanta", "augusta", "NE")
    e = apply.Entry(entry.species_id, entry.binomial, entry.title, entry.status_code,
                    entry.action, entry.before, entry.after, entry.diff)
    plain = apply.infobox_view(e)
    assert "  - | status = NC\n  + | status = NE" in plain
    coloured = apply.infobox_view(e, color=True)
    assert "\033[31m  - | status = NC\033[0m" in coloured
    assert "\033[32m  + | status = NE\033[0m" in coloured


def test_falls_back_to_diff_without_an_infobox():
    e = apply.Entry("5", "A b", "A b", "NT", "insert", "plain", "plain text", "THE DIFF")
    assert apply.infobox_view(e) == "THE DIFF"


def test_maxlag_is_retried(tmp_path):
    wiki = _wiki(ENTRIES[:1])
    wiki.maxlag_next_get = True
    slept: list[float] = []
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        editor = WikiEditor("you@example.org", sleep=slept.append)
        editor.login("Richlitt@nztcs", PASSWORD)
    assert slept == [2.0] and editor.username == "Richlitt"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--interval", "1"], "--interval must be at least 5 seconds"),
        (["--review", "nowhere"], "matched.jsonl not found"),
    ],
)
def test_bad_arguments(tmp_path, capsys, argv, message):
    review = _review(tmp_path)
    args = ["--review", str(review), "--contact", "you@example.org", *argv]
    rc = apply.main(
        args, editor_factory=WikiEditor, ask=_scripted(), get_password=lambda p: PASSWORD
    )
    assert rc == 2 and message in capsys.readouterr().err


def test_cli_dispatches_apply(tmp_path, capsys):
    from nztcs_wiki_bot.cli import main

    rc = main(["apply", "--review", str(tmp_path / "none"), "--contact", "you@example.org"])
    assert rc == 2 and "matched.jsonl not found" in capsys.readouterr().err
