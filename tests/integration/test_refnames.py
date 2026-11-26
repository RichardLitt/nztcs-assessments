"""``refnames`` end to end against a mocked Wikipedia."""

from urllib.parse import parse_qs, urlparse

import pytest
import responses

from nztcs_wiki_bot import reports, wiki_client
from nztcs_wiki_bot.cli import main
from nztcs_wiki_bot.wiki_client import API_URL, WikiClient

LEPIDOPTERA = "Lepidoptera 2025 (Hoare et al. 2026)"
CITE = "{{CiteQ|Q139379012}}"


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    monkeypatch.setattr(wiki_client, "MIN_INTERVAL", 0.0)


def _params(call) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(str(call.request.url)).query).items()}


def _page(title: str, text: str) -> dict:
    return {"title": title, "revisions": [{"slots": {"main": {"content": text}}}]}


def _search(*titles: str, **extra) -> dict:
    return {"query": {"search": [{"title": t} for t in titles]}, **extra}


@responses.activate
def test_counts_names_across_continued_responses(capsys):
    # First search is continued, the second repeats an article.
    responses.add(
        responses.GET, API_URL, json=_search("A", "B", **{"continue": {"sroffset": 2}})
    )
    responses.add(responses.GET, API_URL, json=_search("C"))
    responses.add(responses.GET, API_URL, json=_search("A", "D"))
    # The text batch is split too: each page's text arrives in one response.
    responses.add(
        responses.GET,
        API_URL,
        json={
            "continue": {"rvcontinue": "x"},
            "query": {
                "pages": [
                    _page("A", f'<ref name="Hoare2026">{CITE}</ref>'),
                    _page("B", f'<ref name=":0">{CITE}</ref>'),
                    {"title": "C"},
                    {"title": "D"},
                ]
            },
        },
    )
    responses.add(
        responses.GET,
        API_URL,
        json={
            "query": {
                "pages": [
                    {"title": "A"},
                    _page("C", f"<ref name=Hoare2026>{CITE}</ref>"),
                    _page("D", f"<ref>{CITE}</ref>"),
                ]
            }
        },
    )

    assert main(["refnames", LEPIDOPTERA]) == 0

    out = capsys.readouterr().out
    assert "PDF filename: 4" in out
    assert "    2  Hoare2026\n      1  :0" in out
    assert "no named ref matching this report: 1" in out
    assert "change ref_name from NZTCS2025 to Hoare2026" in out
    calls = list(responses.calls)
    assert _params(calls[1])["sroffset"] == "2"
    assert _params(calls[2])["srsearch"] == 'insource:"nztcs51.pdf"'
    assert _params(calls[3])["titles"] == "A|B|C|D"
    assert _params(calls[4])["rvcontinue"] == "x"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (f'<ref name="NZTCS2025">{CITE}</ref>', "Suggestion: keep ref_name NZTCS2025"),
        (f"<ref>{CITE}</ref>", "No descriptive name in use, so keep ref_name NZTCS2025"),
    ],
)
@responses.activate
def test_keeps_current_name(capsys, text, message):
    responses.add(responses.GET, API_URL, json=_search("A"))
    responses.add(responses.GET, API_URL, json={"query": {"pages": [_page("A", text)]}})

    assert main(["refnames", LEPIDOPTERA]) == 0
    assert message in capsys.readouterr().out


@responses.activate
def test_api_error_is_not_reported_as_no_results():
    responses.add(responses.GET, API_URL, json={"error": {"code": "badquery"}})

    with pytest.raises(RuntimeError, match="badquery"):
        WikiClient().search_titles("x")


def test_unknown_report_lists_known_ones(capsys):
    assert main(["refnames", "Birds 2021"]) == 2
    err = capsys.readouterr().err
    assert "no entry for 'Birds 2021'" in err and LEPIDOPTERA in err


def test_missing_contact(monkeypatch, capsys):
    monkeypatch.delenv("NZTCS_BOT_CONTACT")
    assert main(["refnames", LEPIDOPTERA]) == 2
    assert "--contact" in capsys.readouterr().err


def test_bad_reports_file(monkeypatch, capsys):
    def broken():
        raise reports.ReportsFileError("reports.yaml: not valid YAML")

    monkeypatch.setattr(reports, "known_reports", broken)
    assert main(["refnames", LEPIDOPTERA]) == 2
    assert "not valid YAML" in capsys.readouterr().err
