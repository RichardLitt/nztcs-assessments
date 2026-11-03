
import pytest
import responses

from nztcs_wiki_bot import wiki_client as wc
from nztcs_wiki_bot.wiki_client import API_URL, MaxLagExhausted, WikiClient

# -- User-Agent -------------------------------------------------------------

def test_user_agent_format():
    ua = wc.build_user_agent("you@example.org")
    assert wc.USER_AGENT_RE.match(ua), ua
    assert "bot" in ua
    assert wc.PROJECT_URL in ua
    assert "you@example.org" in ua


def test_session_sets_user_agent():
    client = WikiClient()
    ua = client.session.headers["User-Agent"]
    assert ua.startswith("nztcs-wiki-bot/")
    assert "test@example.org" in ua  # from the conftest env var


def test_explicit_contact_overrides_env():
    client = WikiClient(contact="https://example.org/me")
    assert "https://example.org/me" in client.session.headers["User-Agent"]


def test_missing_contact_refuses_to_construct(monkeypatch):
    monkeypatch.delenv(wc.CONTACT_ENV_VAR)
    with pytest.raises(wc.MissingContactError, match="--contact"):
        WikiClient()


@pytest.mark.parametrize("bad", ["", "   ", "just-a-name"])
def test_unusable_contact_rejected(monkeypatch, bad):
    monkeypatch.delenv(wc.CONTACT_ENV_VAR)
    with pytest.raises(wc.MissingContactError):
        wc.resolve_contact(bad)


# -- read-only guard --------------------------------------------------------

def test_non_query_action_rejected():
    client = WikiClient(sleep=lambda s: None, clock=lambda: 0.0)
    with pytest.raises(ValueError, match="read-only"):
        client._request({"action": "edit", "title": "X"})


# -- batching ---------------------------------------------------------------

@responses.activate
def test_resolution_batches_in_fifties():
    captured = []

    def cb(request):
        captured.append(request.params.get("titles", ""))
        # Echo back each requested title as its own (missing) page.
        titles = request.params["titles"].split("|")
        pages = [{"title": t, "missing": True} for t in titles]
        return (200, {}, _json({"query": {"pages": pages}}))

    responses.add_callback(responses.GET, API_URL, callback=cb, content_type="application/json")

    client = WikiClient(sleep=lambda s: None, clock=_fake_clock())
    titles = [f"Genus species{i}" for i in range(120)]
    client.resolve_titles(titles)

    assert len(captured) == 3  # 50 + 50 + 20
    assert len(captured[0].split("|")) == 50
    assert len(captured[2].split("|")) == 20


# -- maxlag retry -----------------------------------------------------------

@responses.activate
def test_maxlag_retries_then_succeeds():
    responses.add(
        responses.GET, API_URL,
        json={"error": {"code": "maxlag", "info": "lagged"}},
        status=200, headers={"Retry-After": "1"},
    )
    responses.add(
        responses.GET, API_URL,
        json={"query": {"pages": [{"title": "Pūriri moth", "revisions": [
            {"slots": {"main": {"content": "hello"}}}]}]}},
        status=200,
    )
    slept = []
    client = WikiClient(sleep=lambda s: slept.append(s), clock=_fake_clock())
    text = client.fetch_wikitext("Pūriri moth")
    assert text == "hello"
    assert 1 in slept  # honoured Retry-After


@responses.activate
def test_maxlag_exhausts_after_max_retries():
    for _ in range(10):
        responses.add(
            responses.GET, API_URL,
            json={"error": {"code": "maxlag"}}, status=200,
            headers={"Retry-After": "1"},
        )
    client = WikiClient(sleep=lambda s: None, clock=_fake_clock())
    with pytest.raises(MaxLagExhausted):
        client.fetch_wikitext("X")


# -- cache ------------------------------------------------------------------

@responses.activate
def test_cache_second_fetch_hits_disk(tmp_path):
    responses.add(
        responses.GET, API_URL,
        json={"query": {"pages": [{"title": "X", "revisions": [
            {"slots": {"main": {"content": "cached-body"}}}]}]}},
        status=200,
    )
    client = WikiClient(cache_dir=tmp_path, sleep=lambda s: None, clock=_fake_clock())
    assert client.fetch_wikitext("X") == "cached-body"
    # Second call must not hit HTTP again.
    assert client.fetch_wikitext("X") == "cached-body"
    assert len(responses.calls) == 1


@responses.activate
def test_deleting_cache_forces_refetch(tmp_path):
    responses.add(
        responses.GET, API_URL,
        json={"query": {"pages": [{"title": "X", "revisions": [
            {"slots": {"main": {"content": "body"}}}]}]}},
        status=200,
    )
    responses.add(
        responses.GET, API_URL,
        json={"query": {"pages": [{"title": "X", "revisions": [
            {"slots": {"main": {"content": "body2"}}}]}]}},
        status=200,
    )
    client = WikiClient(cache_dir=tmp_path, sleep=lambda s: None, clock=_fake_clock())
    assert client.fetch_wikitext("X") == "body"
    for p in tmp_path.glob("*.json.gz"):
        p.unlink()
    assert client.fetch_wikitext("X") == "body2"
    assert len(responses.calls) == 2


@responses.activate
def test_missing_page_returns_none(tmp_path):
    responses.add(
        responses.GET, API_URL,
        json={"query": {"pages": [{"title": "Nope", "missing": True}]}},
        status=200,
    )
    client = WikiClient(cache_dir=tmp_path, sleep=lambda s: None, clock=_fake_clock())
    assert client.fetch_wikitext("Nope") is None


@responses.activate
def test_resolve_follows_redirect():
    responses.add(
        responses.GET, API_URL,
        json={"query": {
            "redirects": [{"from": "Aenetus virescens", "to": "Pūriri moth"}],
            "pages": [{"title": "Pūriri moth"}],
        }},
        status=200,
    )
    client = WikiClient(sleep=lambda s: None, clock=_fake_clock())
    res = client.resolve_titles(["Aenetus virescens"])["Aenetus virescens"]
    assert res.canonical == "Pūriri moth"
    assert not res.missing
    assert res.redirected_from == "Aenetus virescens"


# -- helpers ----------------------------------------------------------------

def _json(obj):
    import json
    return json.dumps(obj)


def _fake_clock():
    """Monotonic clock that advances 10s per call so throttle never sleeps."""
    state = {"t": 0.0}

    def clock():
        state["t"] += 10.0
        return state["t"]

    return clock
