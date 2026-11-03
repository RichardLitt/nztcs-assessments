
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
