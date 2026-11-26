"""Safety boundary: a full run only ever sends read-only GET action=query requests.

Drives the real WikiClient through the CLI and inspects every request that
reached the (mocked) wire. Write actions are listed explicitly so a failure
names what went wrong. See https://www.mediawiki.org/wiki/API:Edit.
"""

from urllib.parse import parse_qs, urlparse

import pytest
import responses

from nztcs_wiki_bot.cli import main
from nztcs_wiki_bot.wiki_client import API_URL, WikiClient
from tests.integration import wiki_site
from tests.integration.test_end_to_end import CSV

WRITE_ACTIONS = {
    "edit", "login", "clientlogin", "createaccount", "rollback", "delete", "undelete",
    "move", "protect", "upload", "patrol", "purge", "options", "watch", "emailuser",
}
WRITE_PARAMS = {"token", "csrftoken", "lgpassword", "lgtoken"}


def test_full_run_sends_only_read_queries(tmp_path):
    with responses.RequestsMock() as rsps:
        wiki_site.install(rsps)
        rc = main(["--csv", str(CSV), "--out", str(tmp_path / "r"), "--cache", str(tmp_path / "c")])
        calls = list(rsps.calls)

    assert rc == 0
    assert calls, "expected the run to make requests"
    for call in calls:
        req = call.request
        params = {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}
        assert req.method == "GET", req.url
        assert req.body in (None, b"", ""), req.url
        assert params.get("action") == "query", req.url
        assert params.get("action") not in WRITE_ACTIONS
        assert not WRITE_PARAMS & params.keys(), req.url


def test_refnames_sends_only_read_queries():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, API_URL, json={"query": {"search": [{"title": "Aus"}]}})
        rsps.add(responses.GET, API_URL, json={"query": {"search": []}})
        rsps.add(responses.GET, API_URL, json={"query": {"pages": [{"title": "Aus"}]}})
        rc = main(["refnames", "Lepidoptera 2025 (Hoare et al. 2026)"])
        calls = list(rsps.calls)

    assert rc == 0
    assert len(calls) == 3
    for call in calls:
        req = call.request
        params = {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}
        assert req.method == "GET", req.url
        assert params.get("action") == "query", req.url
        assert not WRITE_PARAMS & params.keys(), req.url


@pytest.mark.parametrize("action", sorted(WRITE_ACTIONS))
def test_client_refuses_every_write_action(action):
    client = WikiClient(sleep=lambda s: None, clock=lambda: 0.0)
    with responses.RequestsMock() as rsps:  # any request at all would fail here
        with pytest.raises(ValueError, match="read-only"):
            client._request({"action": action})
        assert not rsps.calls
