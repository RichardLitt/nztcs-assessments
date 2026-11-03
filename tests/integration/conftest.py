import pytest

from nztcs_wiki_bot import wiki_client


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    """The CLI builds a real WikiClient; skip its 1 req/sec floor in tests."""
    monkeypatch.setattr(wiki_client, "MIN_INTERVAL", 0.0)
