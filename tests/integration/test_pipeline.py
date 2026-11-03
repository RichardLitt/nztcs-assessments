"""End-to-end pipeline tests against a fake (no-network) WikiClient."""

from nztcs_wiki_bot.csv_loader import Row
from nztcs_wiki_bot.pipeline import PipelineConfig, run
from nztcs_wiki_bot.wiki_client import ResolvedTitle
from tests.conftest import FakeWikiClient, wikitext


def _row(species_id, name, status="Not Threatened", common=""):
    return Row.from_dict(
        {
            "speciesId": species_id,
            "nztcsSpeciesName": name,
            "commonName": common,
            "conservationStatusTitle": status,
            "reportName": "Lepidoptera 2025 (Hoare et al. 2026)",
            "reportYear": "2026",
        }
    )


def test_full_pipeline_buckets():
    rows = [
        _row("1", "Aenetus virescens (Doubleday, 1843)", "Nationally Vulnerable", "pūriri moth"),
        _row("2", "Archyala sp. A (NZAC04239001)", "Data Deficient"),  # skipped
        _row("3", '"Acroclita" discariana Philpott, 1930', "Nationally Vulnerable"),  # skipped
        _row("4", "Powelliphanta augusta Walker, 2003", "Nationally Endangered"),  # update
        _row("5", "Nonexistent species Author, 1900", "Declining"),  # no_match
        _row("6", "Bogus taxon Author, 1900", "Not assessed"),  # unmapped (non-status)
        # resolves to a page whose Speciesbox is a *different* taxon -> ambiguous
        _row("7", "Examplus mismatchus Author, 1900", "Declining"),
    ]
    client = FakeWikiClient(
        resolutions={
            "Aenetus virescens": ResolvedTitle("Aenetus virescens", "Pūriri moth", False),
            "Powelliphanta augusta": ResolvedTitle(
                "Powelliphanta augusta", "Powelliphanta augusta", False
            ),
            "Examplus mismatchus": ResolvedTitle("Examplus mismatchus", "Some Other Page", False),
            "Nonexistent species": ResolvedTitle("Nonexistent species", None, True),
            "Bogus taxon": ResolvedTitle("Bogus taxon", None, True),
        },
        pages={
            "Pūriri moth": wikitext("puriri_moth"),
            "Powelliphanta augusta": wikitext("powelliphanta_augusta"),
            "Some Other Page": wikitext("wrong_taxon"),
        },
    )

    buckets = run(rows, client)

    assert {e.species_id for e in buckets.matched} == {"1", "4"}
    assert len(buckets.skipped) == 2
    assert len(buckets.unmapped) == 1
    assert buckets.unmapped[0]["reason"] == "non-status"
    assert any(a["reason"] == "taxon-mismatch" for a in buckets.ambiguous)
    assert any(n["binomial"] == "Nonexistent species" for n in buckets.no_match)

    # everything is accounted for
    total = (
        len(buckets.matched)
        + len(buckets.ambiguous)
        + len(buckets.unmapped)
        + len(buckets.no_match)
        + len(buckets.skipped)
    )
    assert total == buckets.rows_in


def test_pipeline_is_idempotent_on_buckets():
    rows = [_row("1", "Aenetus virescens (Doubleday, 1843)", "Nationally Vulnerable")]
    client = FakeWikiClient(
        resolutions={"Aenetus virescens": ResolvedTitle("Aenetus virescens", "Pūriri moth", False)},
        pages={"Pūriri moth": wikitext("puriri_moth")},
    )
    a = run(rows, client)
    b = run(rows, client)
    assert [e.diff for e in a.matched] == [e.diff for e in b.matched]


def test_limit_and_species_filter():
    rows = [
        _row("1", "Aenetus virescens (Doubleday, 1843)", "Declining"),
        _row("2", "Agrotis admirationis Guenée, 1868", "Declining"),
    ]
    client = FakeWikiClient(
        resolutions={"Aenetus virescens": ResolvedTitle("Aenetus virescens", "Pūriri moth", False)},
        pages={"Pūriri moth": wikitext("puriri_moth")},
    )
    buckets = run(rows, client, PipelineConfig(species="Aenetus"))
    # only the Aenetus row should have been resolved
    assert client.resolve_calls[0] == ["Aenetus virescens"]
    assert [e.binomial for e in buckets.matched] == ["Aenetus virescens"]


def test_no_write_endpoints_ever_called():
    """Safety boundary: the fake client only exposes read methods, and the real
    WikiClient guards action!=query. This asserts the pipeline never reaches for
    a write."""
    rows = [_row("1", "Aenetus virescens (Doubleday, 1843)", "Declining")]
    client = FakeWikiClient(
        resolutions={"Aenetus virescens": ResolvedTitle("Aenetus virescens", "Pūriri moth", False)},
        pages={"Pūriri moth": wikitext("puriri_moth")},
    )
    run(rows, client)
    # FakeWikiClient records only resolve/fetch; assert no other interaction.
    assert hasattr(client, "resolve_calls") and hasattr(client, "fetch_calls")
    assert client.fetch_calls == ["Pūriri moth"]
