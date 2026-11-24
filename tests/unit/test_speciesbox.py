
from nztcs_wiki_bot import speciesbox as sb
from tests.conftest import wikitext

# -- find_infobox -----------------------------------------------------------

def test_find_speciesbox():
    ib = sb.find_infobox(wikitext("puriri_moth"))
    assert ib is not None
    assert ib.name == "speciesbox"


def test_find_taxobox_legacy():
    ib = sb.find_infobox(wikitext("taxobox_legacy"))
    assert ib is not None
    assert ib.name == "taxobox"


def test_no_infobox_returns_none():
    assert sb.find_infobox(wikitext("disambig")) is None
    assert sb.find_infobox("plain article, no template") is None
    # An article with other templates ({{Reflist}}) but no taxon infobox.
    assert sb.find_infobox(wikitext("no_infobox")) is None


# -- verify_taxon -----------------------------------------------------------

def _infobox(name: str) -> sb.Infobox:
    ib = sb.find_infobox(wikitext(name))
    assert ib is not None
    return ib


def test_verify_taxon_genus_species():
    assert sb.verify_taxon(_infobox("puriri_moth"), "Aenetus", "virescens")


def test_verify_taxon_rejects_wrong_genus():
    assert not sb.verify_taxon(_infobox("wrong_taxon"), "Aenetus", "virescens")


def test_verify_taxon_combined_taxon_param():
    assert sb.verify_taxon(_infobox("taxon_shorthand"), "Aenetus", "virescens")


def test_verify_taxon_case_insensitive():
    assert sb.verify_taxon(_infobox("puriri_moth"), "aenetus", "VIRESCENS")


# -- patch_status -----------------------------------------------------------

def _patch(name, code="NV"):
    return sb.patch_status(
        wikitext(name),
        "Aenetus",
        "virescens",
        code,
        "NZTCS-Lepidoptera-2025",
        '<ref name="NZTCS-Lepidoptera-2025">{{cite report}}</ref>',
    )


def test_insert_new_status():
    result = _patch("puriri_moth", "NV")
    assert result.action == "insert"
    assert result.changed
    assert result.after.count("status_system") == 1
    assert "status = NV" in result.after or "status=NV" in result.after.replace(" ", "")
    assert "NZTCS" in result.after


def test_update_existing_nztcs():
    result = sb.patch_status(
        wikitext("powelliphanta_augusta"),
        "Powelliphanta",
        "augusta",
        "NE",
        "NZTCS-Lepidoptera-2025",
        '<ref name="NZTCS-Lepidoptera-2025">{{cite report}}</ref>',
    )
    assert result.action == "update"
    assert "NE" in result.after
    # exactly one NZTCS status_system remains
    assert result.after.count("status_system") == 1


def test_add_secondary_for_iucn_article():
    result = _patch("iucn_only", "NU")
    assert result.action == "add_secondary"
    assert "status = LC" in result.after.replace("  ", " ") or "status =LC" in result.after
    assert "IUCN3.1" in result.after
    assert "status2" in result.after
    assert "status2_system" in result.after


def test_idempotent_insert():
    first = _patch("puriri_moth", "NV")
    second = sb.patch_status(
        first.after,
        "Aenetus",
        "virescens",
        "NV",
        "NZTCS-Lepidoptera-2025",
        '<ref name="NZTCS-Lepidoptera-2025">{{cite report}}</ref>',
    )
    assert second.after == first.after
    assert not second.changed
    assert second.action == "noop"


def test_patch_noop_when_no_infobox():
    result = sb.patch_status(
        "no infobox here", "Aenetus", "virescens", "NV", "r", "<ref>x</ref>"
    )
    assert result.action == "noop"
    assert not result.changed


# -- patch_status with real citations (citation.build_ref) -------------------

from nztcs_wiki_bot import citation  # noqa: E402
from nztcs_wiki_bot.csv_loader import Row  # noqa: E402

_LEP = Row.from_dict({"reportName": "Lepidoptera 2025 (Hoare et al. 2026)", "reportYear": "2026"})


def _article(params: str, body: str) -> str:
    return (
        "{{Speciesbox\n| genus = Arctesthes\n| species = avatar\n| authority = Patrick, 2023\n"
        f"{params}}}}}\n{body}\n==References==\n{{{{Reflist}}}}\n"
    )


def _patch_with_citation(wt: str, code: str = "NC") -> sb.PatchResult:
    name, ref = citation.build_ref(_LEP, wt)
    return sb.patch_status(wt, "Arctesthes", "avatar", code, name, ref)


def test_insert_uses_citeq_for_known_report():
    result = _patch_with_citation(_article("", "A moth."))
    assert result.action == "insert"
    assert '| status_ref = <ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>' in result.after


def test_already_cited_status_is_noop():
    # The shape 16 existing articles use: short ref in the infobox, CiteQ in the body.
    wt = _article(
        '| status = NC\n| status_system = NZTCS\n| status_ref = <ref name="Hoare2026" />\n',
        'A moth.<ref name="Hoare2026">{{CiteQ|Q139379012}}</ref>',
    )
    result = _patch_with_citation(wt, "NC")
    assert result.action == "noop"
    assert not result.changed


def test_insert_reuses_existing_ref_under_another_name():
    wt = _article("", "A moth.<ref name=Patrick2023>{{CiteQ|Q139379012|pages=32}}</ref>")
    result = _patch_with_citation(wt)
    assert result.action == "insert"
    assert '| status_ref = <ref name="Patrick2023" />' in result.after
    assert result.after.count("Q139379012") == 1


def test_bare_ref_name_counts_as_defined():
    wt = _article("", "A moth.<ref name=Hoare2026>{{CiteQ|Q139379012}}</ref>")
    result = _patch_with_citation(wt)
    assert '| status_ref = <ref name="Hoare2026" />' in result.after


def test_ref_names_are_case_sensitive():
    assert not sb._ref_defined('<ref name="hoare2026">x</ref>', "Hoare2026")
    assert not sb._ref_name_in('<ref name="hoare2026" />', "Hoare2026")
