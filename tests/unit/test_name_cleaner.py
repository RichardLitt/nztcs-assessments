import pytest

from nztcs_wiki_bot import name_cleaner as nc


@pytest.mark.parametrize(
    "raw, binomial, skip",
    [
        ("Aenetus virescens (Doubleday, 1843)", "Aenetus virescens", None),
        ("Agrotis admirationis Guenée, 1868", "Agrotis admirationis", None),
        ("Pseudocoremia cineracia (Howes, 1942)", "Pseudocoremia cineracia", None),
        ("Aoraia oreobolae Dugdale, 1994", "Aoraia oreobolae", None),
        ("Archyala sp. A (NZAC04239001; Mataroa)", None, nc.SKIP_UNDESCRIBED),
        ("Archyala sp. B (Mount Greenland)", None, nc.SKIP_UNDESCRIBED),
        ("Asaphodes sp. (near aphelias)", None, nc.SKIP_UNDESCRIBED),
        ('"Acroclita" discariana Philpott, 1930', None, nc.SKIP_QUOTED_GENUS),
        ("“Tinea” texta Meyrick, 1931", None, nc.SKIP_QUOTED_GENUS),
    ],
)
def test_clean_name_table(raw, binomial, skip):
    result = nc.clean_name(raw)
    assert result.binomial == binomial
    assert result.skip_reason == skip


def test_nbsp_between_genus_and_species():
    result = nc.clean_name("Aenetus virescens (Doubleday, 1843)")
    assert result.binomial == "Aenetus virescens"


def test_trailing_whitespace():
    assert nc.clean_name("  Aenetus virescens  ").binomial == "Aenetus virescens"


def test_endash_in_author_year_does_not_break_binomial():
    result = nc.clean_name("Aenetus virescens (Smith, 1900–1901)")
    assert result.binomial == "Aenetus virescens"


def test_skipped_property():
    assert nc.clean_name("Archyala sp. A").skipped is True
    assert nc.clean_name("Aenetus virescens").skipped is False
