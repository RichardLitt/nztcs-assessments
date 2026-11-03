import csv
import json

import responses

from nztcs_wiki_bot import fetch
from nztcs_wiki_bot.cli import main as cli_main
from nztcs_wiki_bot.csv_loader import EXPECTED_FIELDS, load_rows


def _assessment(i: int, **over) -> dict:
    a = {
        "speciesId": i,
        "assessmentId": 1000 + i,
        "nztcsSpeciesName": f"<i>Genus species{i}</i> Author, 1900",
        "commonName": "moth",
        "conservationStatusTitle": "Not Threatened",
        "categoryTitle": "Not Threatened",
        "reportName": "Lepidoptera 2025 (Hoare et al. 2026)",
        "reportYear": 2026,
        "notACsvColumn": "dropped",
    }
    a.update(over)
    return a


def _page_callback(all_items: list[dict], requests_seen: list[dict]):
    def cb(request):
        body = json.loads(request.body)
        requests_seen.append(body)
        size, page = body["pageSize"], body["pageNumber"]
        chunk = all_items[(page - 1) * size : page * size]
        return (200, {}, json.dumps({"total": len(all_items), "searchResults": chunk}))

    return cb


@responses.activate
def test_fetch_single_page_sends_user_agent():
    seen: list[dict] = []
    items = [_assessment(i) for i in range(3)]
    responses.add_callback(responses.POST, fetch.API_URL, callback=_page_callback(items, seen))

    got = fetch.fetch_assessments(1176)

    assert len(got) == 3
    assert len(seen) == 1
    assert seen[0]["reportId"] == 1176
    ua = str(responses.calls[0].request.headers["User-Agent"])
    assert ua.startswith("nztcs-wiki-bot/") and fetch.PROJECT_URL in ua


@responses.activate
def test_fetch_follows_pagination():
    seen: list[dict] = []
    items = [_assessment(i) for i in range(25)]
    responses.add_callback(responses.POST, fetch.API_URL, callback=_page_callback(items, seen))

    got = fetch.fetch_assessments(1, page_size=10)

    assert [a["speciesId"] for a in got] == list(range(25))
    assert [b["pageNumber"] for b in seen] == [1, 2, 3]


@responses.activate
def test_fetch_stops_on_empty_page_even_if_total_lies():
    responses.add(
        responses.POST, fetch.API_URL, json={"total": 99, "searchResults": [_assessment(1)]}
    )
    responses.add(responses.POST, fetch.API_URL, json={"total": 99, "searchResults": []})

    assert len(fetch.fetch_assessments(1)) == 1
    assert len(responses.calls) == 2


def test_save_csv_roundtrips_through_loader(tmp_path):
    out = tmp_path / "r.csv"
    n = fetch.save_csv([_assessment(1, commonName="<i>p&#363;riri</i> moth")], out)

    assert n == 1
    with out.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert tuple(reader.fieldnames or ()) == EXPECTED_FIELDS
        raw = next(reader)
    assert raw["nztcsSpeciesName"] == "Genus species1 Author, 1900"
    assert raw["commonName"] == "pūriri moth"
    assert "notACsvColumn" not in raw

    (row,) = load_rows(out)
    assert row.species_id == "1"
    assert row.report_year == "2026"


@responses.activate
def test_cli_fetch_subcommand_writes_csv(tmp_path, capsys):
    seen: list[dict] = []
    responses.add_callback(
        responses.POST, fetch.API_URL, callback=_page_callback([_assessment(7)], seen)
    )
    out = tmp_path / "out.csv"

    rc = cli_main(["fetch", "42", "--out", str(out)])

    assert rc == 0
    assert seen[0]["reportId"] == 42
    assert len(load_rows(out)) == 1
    assert "Saved 1 assessments" in capsys.readouterr().out


@responses.activate
def test_fetch_main_empty_report_returns_1(tmp_path):
    responses.add(responses.POST, fetch.API_URL, json={"total": 0, "searchResults": []})
    out = tmp_path / "none.csv"

    assert fetch.main(["5", "--out", str(out)]) == 1
    assert not out.exists()
