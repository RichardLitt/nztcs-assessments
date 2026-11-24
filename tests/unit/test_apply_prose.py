"""apply warns when the article text describes a status the infobox patch won't change."""

from __future__ import annotations

import responses

from nztcs_wiki_bot import apply
from nztcs_wiki_bot.editor import WikiEditor

BOX = "{{Speciesbox\n| genus = Tinea\n| species = texta\n}}\n"
# Modelled on the real Tinea texta article.
DOC_SENTENCE = (
    "In 2025 this species was classified as having the conservation threat classification of "
    '"At Risk, Uncommon" by the [[Department of Conservation (New Zealand)|Department of '
    'Conservation]].<ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>'
)


def _entry(body: str, code: str = "DD", box: str = BOX) -> apply.Entry:
    before = box + body
    return apply.Entry("1", "Tinea texta", "Tinea texta", code, "insert", before, before, "")


def test_finds_status_sentence_and_cleans_markup():
    (sentence,) = apply.status_sentences(_entry(f"A moth. {DOC_SENTENCE} It is small."))
    assert sentence == (
        "In 2025 this species was classified as having the conservation threat classification "
        'of "At Risk, Uncommon" by the Department of Conservation.'
    )


def test_ignores_status_words_without_an_nztcs_mention():
    assert apply.status_sentences(_entry("Its numbers are declining in the north.")) == []


def test_ignores_the_infobox_itself():
    box = (
        "{{Speciesbox\n| genus = Tinea\n| species = texta\n"
        "| status = NT\n| status_system = NZTCS\n}}\n"
    )
    assert apply.status_sentences(_entry("A moth.", box=box)) == []


def test_ignores_text_inside_refs_and_comments():
    body = (
        "A moth.<ref>{{cite report |title=Conservation status (NZTCS) Declining}}</ref> "
        "<!-- NZTCS: Nationally Critical -->"
    )
    assert apply.status_sentences(_entry(body)) == []


def test_limit_and_truncation():
    long = "The NZTCS lists it as Declining " + "because " * 60 + "."
    body = " ".join([long] * 5)
    found = apply.status_sentences(_entry(body))
    assert len(found) == 3 and all(len(s) <= 300 for s in found) and found[0].endswith("…")


def test_mentions_status_uses_the_label():
    assert apply.mentions_status("listed as Not Threatened under the NZTCS", "NT")
    assert not apply.mentions_status('classified as "At Risk, Uncommon" by DOC', "DD")


class _Editor:
    username = "Richlitt"


def _said(entry: apply.Entry) -> str:
    out: list[str] = []
    applier = apply.Applier(_Editor(), log_path=None, say=out.append, color=False)  # type: ignore[arg-type]
    applier._warn_about_prose(entry)
    return "\n".join(out)


def test_warning_when_text_may_disagree():
    text = _said(_entry(DOC_SENTENCE, code="DD"))
    assert "The article text also describes a conservation status:" in text
    assert '"At Risk, Uncommon"' in text
    assert "Note: the text may not match the new status (Data Deficient)." in text


def test_reassurance_when_text_matches():
    body = "The [[New Zealand Threat Classification System]] lists it as Data Deficient."
    text = _said(_entry(body, code="DD"))
    assert "It mentions Data Deficient, which matches." in text
    assert "Note:" not in text


def test_silent_when_no_status_sentence():
    assert _said(_entry("A small moth found in Otago.")) == ""


def test_warning_shown_before_the_prompt(tmp_path, capsys):
    from tests.integration.test_apply import ENTRIES, PASSWORD, _review, _wiki

    entry = ENTRIES[0]
    sentence = "\nIn 2017 the Department of Conservation listed it as Nationally Vulnerable.\n"
    entry = type(entry)(**{**entry.__dict__, "before": entry.before + sentence,
                           "after": entry.after + sentence})
    review = _review(tmp_path, [entry])
    wiki = _wiki([entry])
    shown_before_prompt: list[str] = []

    def ask(prompt):
        shown_before_prompt.append(capsys.readouterr().out)
        return "n"

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        wiki.install(rsps)
        apply.main(
            ["--review", str(review), "--username", "Richlitt@nztcs",
             "--contact", "you@example.org"],
            editor_factory=lambda c: WikiEditor(c, sleep=lambda s: None),
            ask=ask,
            get_password=lambda prompt: PASSWORD,
        )
    (out,) = shown_before_prompt
    assert '"In 2017 the Department of Conservation listed it as Nationally Vulnerable."' in out
    assert "It mentions Nationally Vulnerable, which matches." in out
