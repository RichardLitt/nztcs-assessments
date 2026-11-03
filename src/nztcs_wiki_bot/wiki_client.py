"""Read-only MediaWiki API client for Wikipedia.

Compliance with Wikimedia policy is baked in (see ``docs/design.md`` §
"Wikipedia API policy compliance"):

* **User-Agent** — informative string with the project URL, the *operator's*
  contact info (required; see :func:`resolve_contact`), and the word "bot".
* **Etiquette** — serial requests, title batching (≤50/call), ``maxlag=5`` with
  ``Retry-After`` backoff, GET for reads, ``format=json&formatversion=2``, a
  self-imposed ≥1 req/sec floor.
* **Caching** — title resolutions and revision fetches are cached on disk.
* **Read-only** — only ``action=query`` is ever issued; no write endpoint.

The only network entrypoints are :meth:`WikiClient.resolve_titles` and
:meth:`WikiClient.fetch_wikitext`.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import requests

from . import __version__

API_URL = "https://en.wikipedia.org/w/api.php"
PROJECT_URL = "https://github.com/RichardLitt/nztcs-assessments"
CONTACT_ENV_VAR = "NZTCS_BOT_CONTACT"
MAXLAG = 5
BATCH_SIZE = 50
MIN_INTERVAL = 1.0  # seconds between requests (self-imposed floor)
MAX_RETRIES = 3


class MaxLagExhausted(RuntimeError):
    """Raised when the API stays lagged after the maximum number of retries."""


class MissingContactError(ValueError):
    """Raised when no usable operator contact is configured."""


def resolve_contact(contact: str | None = None) -> str:
    """Return the operator contact, from ``contact`` or ``$NZTCS_BOT_CONTACT``.

    Wikimedia's User-Agent policy requires *working* contact info for whoever
    runs the tool, so there is deliberately no default: each operator supplies
    their own email address or contact URL.

    >>> resolve_contact("you@example.org")
    'you@example.org'
    >>> resolve_contact("https://example.org/me")
    'https://example.org/me'
    """
    value = (contact or os.environ.get(CONTACT_ENV_VAR, "")).strip()
    if not value:
        raise MissingContactError(
            f"no contact configured: pass --contact or set ${CONTACT_ENV_VAR} "
            "to your email address or a URL where Wikimedia can reach you"
        )
    if "@" not in value and "://" not in value:
        raise MissingContactError(
            f"contact must be an email address or URL, got {value!r}"
        )
    return value


def build_user_agent(contact: str) -> str:
    """Construct the Wikimedia-compliant User-Agent string.

    Format: ``<client>/<version> (<project url>; <contact>) <library>/<version>``.

    >>> ua = build_user_agent("you@example.org")
    >>> ua.startswith("nztcs-wiki-bot/")
    True
    >>> "bot" in ua and "you@example.org" in ua
    True
    """
    return (
        f"nztcs-wiki-bot/{__version__} "
        f"({PROJECT_URL}; {contact}) "
        f"python-requests/{requests.__version__}"
    )


@dataclass
class ResolvedTitle:
    """Outcome of resolving one input title."""

    requested: str
    canonical: str | None  # None when missing
    missing: bool
    redirected_from: str | None = None


@dataclass
class WikiClient:
    """A serial, cached, read-only Wikipedia API client.

    ``contact`` falls back to ``$NZTCS_BOT_CONTACT``; construction fails with
    :class:`MissingContactError` if neither is set.
    """

    contact: str | None = None
    cache_dir: Path | None = None
    session: requests.Session = field(default_factory=requests.Session)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    _last_request_at: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.contact = resolve_contact(self.contact)
        self.session.headers["User-Agent"] = build_user_agent(self.contact)
        if self.cache_dir is not None:
            self.cache_dir = Path(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- public API ---------------------------------------------------------

    def resolve_titles(self, titles: list[str]) -> dict[str, ResolvedTitle]:
        """Resolve titles to canonical articles, following redirects.

        Batches up to 50 titles per API call. Returns a dict keyed by the
        *requested* title.
        """
        out: dict[str, ResolvedTitle] = {}
        unique = list(dict.fromkeys(t for t in titles if t))
        for i in range(0, len(unique), BATCH_SIZE):
            batch = unique[i : i + BATCH_SIZE]
            out.update(self._resolve_batch(batch))
        return out

    def fetch_wikitext(self, title: str) -> str | None:
        """Fetch current wikitext for ``title``; ``None`` if the page is missing.

        Cached on disk by canonical title.
        """
        cached = self._cache_get("wikitext", title)
        if cached is not None:
            return cached or None  # empty string sentinel -> missing

        data = self._request(
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "titles": title,
            }
        )
        pages = data.get("query", {}).get("pages", [])
        text: str | None = None
        for page in pages:
            if page.get("missing"):
                text = None
                break
            revs = page.get("revisions", [])
            if revs:
                text = revs[0].get("slots", {}).get("main", {}).get("content")
        self._cache_put("wikitext", title, text or "")
        return text

    # -- internals ----------------------------------------------------------

    def _resolve_batch(self, batch: list[str]) -> dict[str, ResolvedTitle]:
        cache_key = "resolve:" + "|".join(batch)
        cached = self._cache_get_json("resolve", cache_key)
        if cached is not None:
            return {k: ResolvedTitle(**v) for k, v in cached.items()}

        data = self._request(
            {
                "action": "query",
                "titles": "|".join(batch),
                "redirects": 1,
            }
        )
        query = data.get("query", {})
        # Map normalized + redirect chains back to the requested title.
        norm = {n["from"]: n["to"] for n in query.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in query.get("redirects", [])}
        pages_by_title = {p.get("title"): p for p in query.get("pages", [])}

        result: dict[str, ResolvedTitle] = {}
        for requested in batch:
            step1 = norm.get(requested, requested)
            final = redir.get(step1, step1)
            page = pages_by_title.get(final)
            if page is None or page.get("missing"):
                result[requested] = ResolvedTitle(
                    requested=requested, canonical=None, missing=True
                )
            else:
                result[requested] = ResolvedTitle(
                    requested=requested,
                    canonical=page.get("title"),
                    missing=False,
                    redirected_from=step1 if final != step1 else None,
                )
        self._cache_put_json(
            "resolve", cache_key, {k: vars(v) for k, v in result.items()}
        )
        return result

    def _request(self, params: dict) -> dict:
        """Issue one GET with maxlag retry + rate limiting. Read-only."""
        action = params.get("action")
        if action != "query":
            raise ValueError(f"refusing non-read action={action!r}; client is read-only")

        params = {
            **params,
            "format": "json",
            "formatversion": 2,
            "maxlag": MAXLAG,
        }
        delay = 1.0
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            resp = self.session.get(API_URL, params=params, timeout=30)
            body = resp.json()
            if self._is_maxlag(resp, body):
                if attempt == MAX_RETRIES:
                    raise MaxLagExhausted(
                        f"API still lagged after {MAX_RETRIES} retries"
                    )
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else delay
                self.sleep(wait)
                delay *= 2
                continue
            resp.raise_for_status()
            return body
        raise MaxLagExhausted("unreachable")  # pragma: no cover

    @staticmethod
    def _is_maxlag(resp: requests.Response, body: dict) -> bool:
        if resp.status_code == 503 and "Retry-After" in resp.headers:
            return True
        err = body.get("error", {})
        return err.get("code") == "maxlag"

    def _throttle(self) -> None:
        now = self.clock()
        elapsed = now - self._last_request_at
        if self._last_request_at and elapsed < MIN_INTERVAL:
            self.sleep(MIN_INTERVAL - elapsed)
        self._last_request_at = self.clock()

    # -- disk cache ---------------------------------------------------------

    def _cache_path(self, namespace: str, key: str) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{namespace}-{digest}.json.gz"

    def _cache_get(self, namespace: str, key: str) -> str | None:
        path = self._cache_path(namespace, key)
        if path is None or not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)

    def _cache_put(self, namespace: str, key: str, value: str) -> None:
        path = self._cache_path(namespace, key)
        if path is None:
            return
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(value, f)

    def _cache_get_json(self, namespace: str, key: str):
        path = self._cache_path(namespace, key)
        if path is None or not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)

    def _cache_put_json(self, namespace: str, key: str, value) -> None:
        path = self._cache_path(namespace, key)
        if path is None:
            return
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(value, f)


# A loose validator used by tests to assert UA shape.
USER_AGENT_RE = re.compile(
    r"^nztcs-wiki-bot/\d+\.\d+(\.\d+)?\s+\(https://[^)]+;[^)]+\)\s+python-requests/"
)
