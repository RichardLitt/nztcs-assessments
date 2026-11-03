"""Opt-in live test against the real Wikipedia API.

Run with: ``pytest -m live``  (deselected by default in pyproject.toml).
Catches breakage from real-world API changes that mocks would miss.
"""

import os

import pytest

from nztcs_wiki_bot import speciesbox
from nztcs_wiki_bot.wiki_client import CONTACT_ENV_VAR, WikiClient

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get(CONTACT_ENV_VAR),
        reason=f"set ${CONTACT_ENV_VAR} to your real contact to run live tests",
    ),
]


def test_puriri_moth_resolves_and_has_speciesbox():
    client = WikiClient()
    res = client.resolve_titles(["Aenetus virescens"])["Aenetus virescens"]
    assert not res.missing
    assert res.canonical  # redirects to "Pūriri moth"

    wikitext = client.fetch_wikitext(res.canonical)
    assert wikitext
    infobox = speciesbox.find_infobox(wikitext)
    assert infobox is not None
    assert speciesbox.verify_taxon(infobox, "Aenetus", "virescens")
