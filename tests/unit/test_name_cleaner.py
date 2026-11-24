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


# -- subspecies, taxon concepts and uncertain identifications -------------------


@pytest.mark.parametrize(
    "raw, skip",
    [
        ("Vanessa gonerilla gonerilla (Fabricius, 1775)", nc.SKIP_SUBSPECIES),
        ("Vanessa gonerilla ida (Alfken, 1899)", nc.SKIP_SUBSPECIES),
        ("Zizina otis labradus (Godart, 1824)", nc.SKIP_SUBSPECIES),
        ("Melanitis leda bankia (Fabricius, 1775)", nc.SKIP_SUBSPECIES),
        ("Pyrgotis pyramidias s.l. Meyrick, 1901", nc.SKIP_TAXON_CONCEPT),
        ("Pyrgotis pyramidias s.s. Meyrick, 1901", nc.SKIP_TAXON_CONCEPT),
        ("Pyrgotis pyramidias sensu stricto", nc.SKIP_TAXON_CONCEPT),
        ("Chalastra cf. pellurgata (NZAC04193100)", nc.SKIP_UNCERTAIN),
        ("Meterana cf. tetrachroa (NZAC04285469)", nc.SKIP_UNCERTAIN),
        ("Ichneutica aff. virescens", nc.SKIP_UNCERTAIN),
    ],
)
def test_names_that_must_not_patch_the_species_article(raw, skip):
    result = nc.clean_name(raw)
    assert result.skip_reason == skip
    assert result.binomial is None


@pytest.mark.parametrize(
    "raw, binomial",
    [
        ("Hierodoris s.l. insignis Philpott, 1926", "Hierodoris insignis"),
        ("Hierodoris s.l. stellata Philpott, 1918", "Hierodoris stellata"),
        ("Hierodoris s. l. insignis", "Hierodoris insignis"),
        ("Exampla nova de Joannis, 1915", "Exampla nova"),
        ("Exampla nova von Heinemann, 1870", "Exampla nova"),
    ],
)
def test_genus_qualifiers_and_authority_particles_are_not_subspecies(raw, binomial):
    result = nc.clean_name(raw)
    assert result.skip_reason is None
    assert result.binomial == binomial


def test_report_1176_skips_exactly_the_expected_names():
    """Regression guard on the real shapes from the Lepidoptera 2025 report."""
    names = [
        "Vanessa gonerilla gonerilla (Fabricius, 1775)", "Vanessa gonerilla ida (Alfken, 1899)",
        "Zizina otis labradus (Godart, 1824)", "Melanitis leda bankia (Fabricius, 1775)",
        "Zizina oxleyi (Felder & Felder, 1865)", "Vanessa itea (Fabricius, 1775)",
    ]
    assert [nc.clean_name(n).skip_reason for n in names] == [
        "subspecies", "subspecies", "subspecies", "subspecies", None, None,
    ]
