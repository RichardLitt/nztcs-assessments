import pytest

from nztcs_wiki_bot import reports

NAME = "Birds 2021 (Someone et al. 2022)"
GOOD = f"""\
"{NAME}":
  wikidata: Q1
  ref_name: NZTCS2021
  url: https://example.org/birds.pdf
"""


def _load(tmp_path, text):
    path = tmp_path / "reports.yaml"
    path.write_text(text, encoding="utf-8")
    return reports.load(path)


def test_shipped_file_loads():
    assert reports.load()


def test_load_good_file(tmp_path):
    assert _load(tmp_path, GOOD) == {
        NAME: reports.Report("Q1", "NZTCS2021", "https://example.org/birds.pdf")
    }


def test_filled_in_template_loads(tmp_path):
    text = reports.entry_template(NAME).replace("Q...", "Q1")
    assert list(_load(tmp_path, text)) == [NAME]


def test_unfilled_template_is_rejected(tmp_path):
    with pytest.raises(reports.ReportsFileError, match="wikidata"):
        _load(tmp_path, reports.entry_template(NAME))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('"a": [', "not valid YAML"),
        ("", "expected a list"),
        (GOOD + GOOD, "appears twice"),
        (GOOD.replace("  url", "  link"), "exactly these"),
        (f'"{NAME}":\nwikidata: Q1\n', "exactly these"),
        (GOOD.replace("Q1", ""), "filled in"),
        (GOOD.replace("Q1", "139"), "filled in"),
        (GOOD.replace("Q1", "P1"), "wikidata"),
        (GOOD.replace("NZTCS2021", "NZTCS 2021"), "ref_name"),
        (GOOD.replace("https://", "http://"), "url"),
    ],
)
def test_bad_files_are_rejected_with_a_reason(tmp_path, text, message):
    with pytest.raises(reports.ReportsFileError, match=message):
        _load(tmp_path, text)
