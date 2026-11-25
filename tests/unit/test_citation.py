import pytest

from nztcs_wiki_bot import citation, reports
from nztcs_wiki_bot.csv_loader import Row

LEPIDOPTERA = "Lepidoptera 2025 (Hoare et al. 2026)"
UNKNOWN = "Coleoptera 2031 (Someone et al. 2032)"
REPORT = reports.known_reports()[LEPIDOPTERA]


def _row(report_name=LEPIDOPTERA, **kw):
    base = {"reportName": report_name, "reportYear": "2026"}
    base.update(kw)
    return Row.from_dict(base)


# Known report: {{CiteQ}} under the shared ref name.


def test_known_report_uses_citeq():
    name, ref = citation.build_ref(_row())
    assert name == "NZTCS2025"
    assert ref == '<ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>'
    assert citation.TODO_AUTHORS not in ref


def test_known_report_lookup_ignores_surrounding_whitespace():
    name, _ = citation.build_ref(_row(f"  {LEPIDOPTERA} "))
    assert name == "NZTCS2025"


@pytest.mark.parametrize(
    "existing",
    [
        '<ref name="moths">{{CiteQ|Q139379012|pages=32}}</ref>',
        "<ref name='moths'>{{CiteQ|Q139379012}}</ref>",
        "<ref name=moths>{{CiteQ|Q139379012}}</ref>",
        '<ref name="moths">{{cite report |url=' + REPORT.url + " |title=x}}</ref>",
    ],
    ids=["double-quoted", "single-quoted", "bare", "by-url"],
)
def test_reuses_existing_citation_of_same_report(existing):
    wikitext = f"Some text.{existing}\n{{{{Speciesbox | genus = A | species = b}}}}"
    name, ref = citation.build_ref(_row(), wikitext)
    assert name == "moths"
    assert ref.startswith('<ref name="moths">')


def test_ignores_citations_of_other_reports():
    wikitext = '<ref name="other">{{CiteQ|Q1393790123}}</ref><ref name="x">{{CiteQ|Q42}}</ref>'
    name, _ = citation.build_ref(_row(), wikitext)
    assert name == "NZTCS2025"


def test_ignores_unnamed_citation_of_same_report():
    name, _ = citation.build_ref(_row(), "<ref>{{CiteQ|Q139379012}}</ref>")
    assert name == "NZTCS2025"


# Unknown report: {{cite report}} scaffold with a TODO marker.


def test_ref_name_is_slug_safe():
    name = citation.ref_name(LEPIDOPTERA)
    assert name == "NZTCS-Lepidoptera-2025"
    assert " " not in name and "(" not in name


def test_unknown_report_falls_back_to_scaffold():
    name, ref = citation.build_ref(_row(UNKNOWN, reportYear="2032"))
    assert name == "NZTCS-Coleoptera-2031"
    assert "cite report" in ref
    assert "2032" in ref
    assert citation.TODO_AUTHORS in ref
    assert ref.startswith(f'<ref name="{name}">')
    assert ref.endswith("</ref>")


def test_scaffold_title_derivation():
    _, ref = citation.build_ref(_row(UNKNOWN))
    assert "Conservation status of New Zealand Coleoptera, 2031" in ref


def test_build_ref_is_deterministic():
    for report_name in (LEPIDOPTERA, UNKNOWN):
        assert citation.build_ref(_row(report_name)) == citation.build_ref(_row(report_name))
