"""CLI integration: run main() against mocked HTTP and check review/ output."""

import responses

from nztcs_wiki_bot.cli import main
from nztcs_wiki_bot.wiki_client import API_URL

SPECIESBOX = "{{Speciesbox\n| genus = Aenetus\n| species = virescens\n}}"


@responses.activate
def test_cli_writes_review(tmp_path, monkeypatch):
    # Resolve call (batch) then a wikitext fetch.
    responses.add(
        responses.GET, API_URL,
        json={"query": {
            "redirects": [{"from": "Aenetus virescens", "to": "Pūriri moth"}],
            "pages": [{"title": "Pūriri moth"}],
        }},
        status=200,
    )
    responses.add(
        responses.GET, API_URL,
        json={"query": {"pages": [{"title": "Pūriri moth", "revisions": [
            {"slots": {"main": {"content": SPECIESBOX}}}]}]}},
        status=200,
    )

    csv_path = tmp_path / "one.csv"
    csv_path.write_text(
        "speciesId,assessmentId,nztcsSpeciesName,commonName,conservationStatusTitle,"
        "categoryTitle,criteriaTitle,qualifiers,reportName,reportYear,popSizeTitle,popTrendTitle\n"
        '1,2,"Aenetus virescens (Doubleday, 1843)",pūriri moth,Nationally Vulnerable,'
        "Threatened,,,Lepidoptera 2025 (Hoare et al. 2026),2026,,\n",
        encoding="utf-8",
    )
    out = tmp_path / "review"
    rc = main(["--csv", str(csv_path), "--out", str(out), "--cache", str(tmp_path / "cache")])
    assert rc == 0
    assert (out / "matched.jsonl").read_text(encoding="utf-8").strip()
    assert (out / "stats.txt").exists()
    assert "balanced   True" in (out / "stats.txt").read_text(encoding="utf-8")


def test_cli_missing_contact_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("NZTCS_BOT_CONTACT")
    csv_path = tmp_path / "one.csv"
    csv_path.write_text("speciesId\n", encoding="utf-8")
    rc = main(["--csv", str(csv_path), "--cache", str(tmp_path / "cache")])
    assert rc == 2
    assert "--contact" in capsys.readouterr().err


def test_cli_missing_csv_returns_2(tmp_path):
    rc = main(["--csv", str(tmp_path / "nope.csv")])
    assert rc == 2
