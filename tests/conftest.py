"""Shared fixtures: paths, sample rows, and a fake (no-network) WikiClient."""

from __future__ import annotations

from pathlib import Path

import pytest

from nztcs_wiki_bot.csv_loader import Row
from nztcs_wiki_bot.wiki_client import CONTACT_ENV_VAR, ResolvedTitle

FIXTURES = Path(__file__).parent / "fixtures"
TEST_CONTACT = "test@example.org"


@pytest.fixture(autouse=True)
def _operator_contact(request, monkeypatch):
    """Give every offline test a contact. Live tests must use a real one."""
    if request.node.get_closest_marker("live") is None:
        monkeypatch.setenv(CONTACT_ENV_VAR, TEST_CONTACT)


def wikitext(name: str) -> str:
    return (FIXTURES / "wikitext" / f"{name}.txt").read_text(encoding="utf-8")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_row() -> Row:
    return Row.from_dict(
        {
            "speciesId": "100",
            "assessmentId": "200",
            "nztcsSpeciesName": "Aenetus virescens (Doubleday, 1843)",
            "commonName": "pūriri moth",
            "conservationStatusTitle": "Not Threatened",
            "categoryTitle": "Not Threatened",
            "reportName": "Lepidoptera 2025 (Hoare et al. 2026)",
            "reportYear": "2026",
        }
    )


class FakeWikiClient:
    """A WikiClient stand-in driven by in-memory dicts (no network)."""

    def __init__(
        self,
        resolutions: dict[str, ResolvedTitle] | None = None,
        pages: dict[str, str] | None = None,
    ) -> None:
        self.resolutions = resolutions or {}
        self.pages = pages or {}
        self.resolve_calls: list[list[str]] = []
        self.fetch_calls: list[str] = []

    def resolve_titles(self, titles: list[str]) -> dict[str, ResolvedTitle]:
        self.resolve_calls.append(list(titles))
        out = {}
        for t in titles:
            out[t] = self.resolutions.get(
                t, ResolvedTitle(requested=t, canonical=None, missing=True)
            )
        return out

    def fetch_wikitext(self, title: str) -> str | None:
        self.fetch_calls.append(title)
        return self.pages.get(title)


@pytest.fixture
def fake_client() -> FakeWikiClient:
    return FakeWikiClient()
