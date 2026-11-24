"""The only module that writes to Wikipedia. Used by ``nztcs-wiki-bot apply``.

The review run (:mod:`.wiki_client`) stays strictly read-only. This module is
separate on purpose: it logs in with a *bot password* the operator creates on
their own account (Special:BotPasswords), fetches the live text of one page at a
time, and saves an edit only when :mod:`.apply` asks it to, which happens only
after the operator has confirmed that edit.

Each save:

* sends ``baserevid`` / ``basetimestamp`` / ``starttimestamp``, so MediaWiki
  rejects it with an edit conflict if the page changed after it was fetched;
* sends ``nocreate`` (never creates a page) and ``assert=user`` (fails if the
  session has logged out, rather than editing anonymously);
* sends ``maxlag=5`` and backs off on ``maxlag`` errors, like the reader.

The password is only ever sent in the login request. It's never logged,
printed, or stored.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import requests

from .wiki_client import API_URL, MAX_RETRIES, MAXLAG, build_user_agent

USERNAME_ENV_VAR = "NZTCS_BOT_USERNAME"
PASSWORD_ENV_VAR = "NZTCS_BOT_PASSWORD"


class LoginError(RuntimeError):
    """Login with the bot password failed."""


class EditError(RuntimeError):
    """The API refused an edit. ``code`` is the MediaWiki error code."""

    def __init__(self, code: str, info: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {info}" if info else code)


@dataclass
class LivePage:
    title: str
    text: str | None
    revid: int | None
    timestamp: str | None  # of the current revision, for basetimestamp
    fetched_at: str  # server time when fetched, for starttimestamp

    @property
    def missing(self) -> bool:
        return self.text is None


class WikiEditor:
    """A logged-in session that can read one page and save one edit at a time."""

    def __init__(
        self,
        contact: str,
        session: requests.Session | None = None,
        api_url: str = API_URL,
        sleep=time.sleep,
    ) -> None:
        self.api_url = api_url
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = build_user_agent(contact)
        self._sleep = sleep
        self._csrf: str | None = None
        self.username: str | None = None

    # -- session -------------------------------------------------------------

    def login(self, username: str, password: str) -> str:
        """Log in with a bot password (``User@name``). Returns the account name."""
        token = self._get({"action": "query", "meta": "tokens", "type": "login"})["query"][
            "tokens"
        ]["logintoken"]
        body = self._post(
            {"action": "login", "lgname": username, "lgpassword": password, "lgtoken": token}
        )
        result = body.get("login", {})
        if result.get("result") != "Success":
            reason = result.get("reason") or result.get("result") or "unknown error"
            if isinstance(reason, dict):
                reason = reason.get("text") or reason.get("code") or str(reason)
            raise LoginError(str(reason))
        self.username = result.get("lgusername") or username.split("@", 1)[0]
        self._csrf = self._get({"action": "query", "meta": "tokens"})["query"]["tokens"][
            "csrftoken"
        ]
        return self.username

    def has_new_messages(self) -> bool:
        """Whether the account has an unread talk-page message."""
        info = self._get({"action": "query", "meta": "userinfo", "uiprop": "hasmsg"})
        return bool(info.get("query", {}).get("userinfo", {}).get("messages"))

    # -- pages ---------------------------------------------------------------

    def get_page(self, title: str) -> LivePage:
        """Fetch the live wikitext and revision of one page (never cached)."""
        body = self._get(
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content|ids|timestamp",
                "rvslots": "main",
                "titles": title,
                "curtimestamp": 1,
            }
        )
        fetched_at = body.get("curtimestamp", "")
        page = body["query"]["pages"][0]
        if page.get("missing") or not page.get("revisions"):
            return LivePage(page.get("title", title), None, None, None, fetched_at)
        rev = page["revisions"][0]
        return LivePage(
            title=page["title"],
            text=rev["slots"]["main"]["content"],
            revid=rev["revid"],
            timestamp=rev["timestamp"],
            fetched_at=fetched_at,
        )

    def save(self, page: LivePage, text: str, summary: str) -> int | None:
        """Save ``text`` over ``page``. Returns the new revision ID (``None`` if
        MediaWiki saw no change). Raises :class:`EditError` on refusal."""
        if self._csrf is None:
            raise EditError("notloggedin", "call login() first")
        if page.missing:
            raise EditError("missingtitle", "won't create pages")
        params = {
            "action": "edit",
            "title": page.title,
            "text": text,
            "summary": summary,
            "baserevid": page.revid,
            "basetimestamp": page.timestamp,
            "starttimestamp": page.fetched_at,
            "nocreate": 1,
            "assert": "user",
            "token": self._csrf,
        }
        result = self._post(params).get("edit", {})
        if result.get("result") != "Success":
            raise EditError(result.get("result", "unknown"), str(result))
        if result.get("nochange"):
            return None
        return result.get("newrevid")

    # -- transport -------------------------------------------------------------

    def _get(self, params: dict) -> dict:
        return self._call("GET", params)

    def _post(self, params: dict) -> dict:
        return self._call("POST", params)

    def _call(self, method: str, params: dict) -> dict:
        params = {**params, "format": "json", "formatversion": 2, "maxlag": MAXLAG}
        for attempt in range(MAX_RETRIES + 1):
            if method == "GET":
                resp = self.session.get(self.api_url, params=params, timeout=60)
            else:
                resp = self.session.post(self.api_url, data=params, timeout=60)
            resp.raise_for_status()
            body = resp.json()
            err = body.get("error")
            if err and err.get("code") == "maxlag" and attempt < MAX_RETRIES:
                self._sleep(float(resp.headers.get("Retry-After", 5)))
                continue
            if err:
                raise EditError(err.get("code", "unknown"), err.get("info", ""))
            return body
        raise EditError("maxlag", "server lag stayed high")  # pragma: no cover


_BOTS = re.compile(r"\{\{\s*(nobots|bots)\s*(\|[^}]*)?\}\}", re.IGNORECASE)


def allows_bots(text: str, user: str | None) -> bool:
    """Whether ``{{bots}}`` / ``{{nobots}}`` in ``text`` permit this tool to edit.

    Follows https://en.wikipedia.org/wiki/Template:Bots. Assisted edits aren't
    strictly bound by it, but the tool honours it anyway.

    >>> allows_bots("text", "Richlitt")
    True
    >>> allows_bots("{{nobots}}", "Richlitt")
    False
    >>> allows_bots("{{bots|deny=Richlitt,Other}}", "Richlitt")
    False
    >>> allows_bots("{{bots|allow=SomeBot}}", "Richlitt")
    False
    >>> allows_bots("{{bots|allow=all}}", "Richlitt")
    True
    """
    names = {n.lower() for n in (user, "nztcs-wiki-bot") if n}
    for m in _BOTS.finditer(text):
        if m.group(1).lower() == "nobots":
            return False
        args = (m.group(2) or "").lstrip("|")
        for part in args.split("|"):
            key, _, value = part.partition("=")
            listed = {v.strip().lower() for v in value.split(",") if v.strip()}
            if key.strip().lower() == "deny" and (listed & (names | {"all"})):
                return False
            if key.strip().lower() == "allow" and not (listed & (names | {"all"})):
                return False
    return True
