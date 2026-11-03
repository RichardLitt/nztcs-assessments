"""Serve the fake wiki in ``fixtures/api_responses/site.json`` over mocked HTTP.

Lets integration tests drive the *real* :class:`WikiClient` (User-Agent,
batching, caching, read-only guard) without touching the network, and records
every request so tests can assert on exactly what was sent.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import responses

from nztcs_wiki_bot.wiki_client import API_URL
from tests.conftest import FIXTURES, wikitext

SITE = json.loads((FIXTURES / "api_responses" / "site.json").read_text(encoding="utf-8"))


def _resolve(titles: list[str]) -> dict:
    redirects, pages, seen = [], [], set()
    for t in titles:
        target = SITE["redirects"].get(t)
        if target:
            redirects.append({"from": t, "to": target})
        final = target or t
        if final in seen:
            continue
        seen.add(final)
        if final in SITE["pages"]:
            pages.append({"title": final})
        else:
            pages.append({"title": final, "missing": True})
    return {"query": {"redirects": redirects, "pages": pages}}


def _revisions(title: str) -> dict:
    if title not in SITE["pages"]:
        return {"query": {"pages": [{"title": title, "missing": True}]}}
    fixture = SITE["pages"][title]
    page: dict = {"title": title}
    if fixture is not None:
        page["revisions"] = [{"slots": {"main": {"content": wikitext(fixture)}}}]
    return {"query": {"pages": [page]}}


def _callback(request):
    params = {k: v[0] for k, v in parse_qs(urlparse(request.url).query).items()}
    if "redirects" in params:
        body = _resolve(params["titles"].split("|"))
    else:
        body = _revisions(params["titles"])
    return (200, {"Content-Type": "application/json"}, json.dumps(body))


def install(rsps: responses.RequestsMock) -> None:
    """Register the fake wiki on an active ``responses`` mock."""
    rsps.add_callback(responses.GET, API_URL, callback=_callback)
    # Anything that isn't a GET to the API fails loudly as an unmatched request.
