"""``nztcs-wiki-bot apply``: save reviewed patches, one confirmed edit at a time.

This is *assisted editing*: the operator sees every change and decides whether
to save it, and edits are made from their own account. Nothing is saved without
an explicit ``y``.

For each entry in ``matched.jsonl`` the live article is fetched again, and the
entry is skipped, without prompting, if:

* the article has changed since the run (live text ≠ the run's ``before``),
  so the patch might overwrite someone else's edit. Re-run the tool to refresh.
* the patch is already there (live text == ``after``).
* ``{{nobots}}`` or ``{{bots}}`` excludes this tool or account.
* the citation still contains the scaffold's TODO marker.

Saves are spaced at least ``interval`` seconds apart, and the run stops at
once if the account gets a talk-page message. Every outcome is appended to
``applied.tsv`` in the review folder.
"""

from __future__ import annotations

import argparse
import difflib
import getpass
import json
import os
import sys
import time
import webbrowser
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from . import status_map
from .citation import TODO_AUTHORS
from .editor import (
    PASSWORD_ENV_VAR,
    USERNAME_ENV_VAR,
    EditError,
    LoginError,
    WikiEditor,
    allows_bots,
)
from .speciesbox import find_infobox
from .wiki_client import CONTACT_ENV_VAR, MissingContactError, resolve_contact

DEFAULT_INTERVAL = 10.0  # seconds between saves
TOOL_NOTE = "assisted edit with nztcs-wiki-bot"

_LABELS = {code: title for title, code in status_map.STATUS_CODES.items()}


@dataclass
class Entry:
    species_id: str
    binomial: str
    title: str
    status_code: str
    action: str
    before: str
    after: str
    diff: str


def load_entries(path: Path) -> list[Entry]:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        entries.append(
            Entry(
                species_id=str(d["species_id"]),
                binomial=d["binomial"],
                title=d["title"],
                status_code=d["status_code"],
                action=d["action"],
                before=d["before"],
                after=d["after"],
                diff=d.get("diff", ""),
            )
        )
    return entries


def edit_summary(entry: Entry) -> str:
    """The edit summary for an entry.

    >>> e = Entry("1", "A b", "A b", "NT", "insert", "", "", "")
    >>> edit_summary(e)
    'Add NZTCS conservation status: Not Threatened (NT); assisted edit with nztcs-wiki-bot'
    """
    label = _LABELS.get(entry.status_code, entry.status_code)
    status = f"{label} ({entry.status_code})" if label != entry.status_code else label
    if entry.action == "update":
        what = f"Update NZTCS conservation status to {status}"
    elif entry.action == "add_secondary":
        what = f"Add NZTCS conservation status alongside existing status: {status}"
    else:
        what = f"Add NZTCS conservation status: {status}"
    return f"{what}; {TOOL_NOTE}"


def _article_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))


_GREEN, _RED, _RESET = "\033[32m", "\033[31m", "\033[0m"


def infobox_view(entry: Entry, color: bool = False) -> str:
    """The whole infobox as it will be after the edit, every line shown.

    Added lines start with ``+``, removed lines with ``-``, and unchanged lines
    are indented, so existing ``status`` lines are visible at a glance. Falls
    back to the full diff if either version has no infobox.

    >>> before = "{{Speciesbox\\n| genus = A\\n}}"
    >>> after = "{{Speciesbox\\n| status = NT\\n| genus = A\\n}}"
    >>> e = Entry("1", "A b", "A b", "NT", "insert", before, after, "")
    >>> print(infobox_view(e))
        {{Speciesbox
      + | status = NT
        | genus = A
        }}
    """
    before, after = find_infobox(entry.before), find_infobox(entry.after)
    if before is None or after is None:
        return entry.diff
    a = str(before.template).splitlines()
    b = str(after.template).splitlines()

    def paint(text: str, code: str) -> str:
        return f"{code}{text}{_RESET}" if color else text

    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            out += [f"    {line}" for line in a[i1:i2]]
            continue
        out += [paint(f"  - {line}", _RED) for line in a[i1:i2]]
        out += [paint(f"  + {line}", _GREEN) for line in b[j1:j2]]
    return "\n".join(out)


def _use_color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


class Applier:
    """Walk the entries, asking before each save. Injectable for tests."""

    def __init__(
        self,
        editor: WikiEditor,
        log_path: Path,
        ask: Callable[[str], str] = input,
        say: Callable[[str], None] = print,
        interval: float = DEFAULT_INTERVAL,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        open_url: Callable[[str], object] | None = None,
        color: bool | None = None,
    ) -> None:
        self.color = _use_color() if color is None else color
        self.editor = editor
        self.log_path = log_path
        self.ask = ask
        self.say = say
        self.interval = interval
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.open_url = open_url or webbrowser.open
        self._last_save: float | None = None
        self.outcomes: Counter[str] = Counter()

    def run(self, entries: list[Entry]) -> Counter[str]:
        total = len(entries)
        for i, entry in enumerate(entries, 1):
            outcome = self._one(entry, i, total)
            if outcome == "quit":
                self.say("Stopped.")
                break
            if outcome == "stop-messages":
                self.say(
                    "\nYou have a new message on your talk page. Stopping so you can read it:\n"
                    "  https://en.wikipedia.org/wiki/Special:MyTalk"
                )
                break
        return self.outcomes

    # -- one entry -------------------------------------------------------------

    def _one(self, entry: Entry, i: int, total: int) -> str:
        head = f"\n[{i}/{total}] {entry.binomial} → {entry.title}"
        if TODO_AUTHORS in entry.after:
            return self._skip(entry, head, "needs-citation", "the citation still has a TODO")
        page = self.editor.get_page(entry.title)
        if page.missing:
            return self._skip(entry, head, "missing", "the article no longer exists")
        if page.text == entry.after:
            return self._skip(entry, head, "already-applied", "this change is already there")
        if page.text != entry.before:
            return self._skip(
                entry, head, "changed", "the article changed since your run; re-run the tool"
            )
        if not allows_bots(page.text or "", self.editor.username):
            return self._skip(entry, head, "nobots", "the article opts out with {{bots}}")

        self.say(head)
        self.say(_article_url(entry.title))
        label = _LABELS.get(entry.status_code, entry.status_code)
        self.say(f"NZTCS status: {entry.status_code} ({label}) · {entry.action}\n")
        self.say("Infobox after this edit (+ added, - removed):\n")
        self.say(infobox_view(entry, self.color))
        while True:
            answer = self.ask("\nSave this edit? [y]es [n]o [d]iff [o]pen [q]uit: ").strip().lower()
            if answer in ("d", "diff"):
                self.say(entry.diff)
            elif answer in ("o", "open"):
                self.open_url(_article_url(entry.title))
            elif answer in ("n", "no"):
                self._record(entry, "skipped")
                return "skipped"
            elif answer in ("q", "quit"):
                return "quit"
            elif answer in ("y", "yes"):
                return self._save(entry, page)

    def _save(self, entry: Entry, page) -> str:
        if self._last_save is not None:
            wait = self.interval - (self.clock() - self._last_save)
            if wait > 0:
                self.say(f"(waiting {wait:.0f}s between saves)")
                self.sleep(wait)
        try:
            revid = self.editor.save(page, entry.after, edit_summary(entry))
        except EditError as e:
            self.say(f"  Not saved: {e}")
            self._record(entry, f"error:{e.code}")
            return "error"
        self._last_save = self.clock()
        if revid is None:
            self.say("  No change was needed.")
            self._record(entry, "no-change")
        else:
            self.say(f"  Saved: https://en.wikipedia.org/w/index.php?diff={revid}")
            self._record(entry, "saved", revid)
        if self.editor.has_new_messages():
            return "stop-messages"
        return "saved"

    def _skip(self, entry: Entry, head: str, outcome: str, why: str) -> str:
        self.say(f"{head}\n  Skipped: {why}.")
        self._record(entry, outcome)
        return outcome

    def _record(self, entry: Entry, outcome: str, revid: int | None = None) -> None:
        self.outcomes[outcome] += 1
        new = not self.log_path.exists()
        with self.log_path.open("a", encoding="utf-8") as f:
            if new:
                f.write("time\tspecies_id\ttitle\toutcome\trevid\n")
            when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            f.write(f"{when}\t{entry.species_id}\t{entry.title}\t{outcome}\t{revid or ''}\n")


# -- command line ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nztcs-wiki-bot apply",
        description="Save the patches in a review folder to Wikipedia, from your own account, "
        "asking before every edit. Uses a bot password (Special:BotPasswords). "
        "See docs/assisted-editing.md.",
    )
    p.add_argument("--review", default="review", help="Review folder (default: review/)")
    p.add_argument(
        "--username",
        default=None,
        help=f"Bot password username, e.g. You@nztcs (default: ${USERNAME_ENV_VAR}, or asks)",
    )
    p.add_argument(
        "--contact",
        default=None,
        help=f"Your email or contact URL for the User-Agent (default: ${CONTACT_ENV_VAR})",
    )
    p.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Minimum seconds between saves (default: {DEFAULT_INTERVAL:.0f})",
    )
    p.add_argument("--species", default=None, help="Only entries whose binomial contains this")
    p.add_argument("--limit", type=int, default=None, help="Look at most N entries")
    return p


def main(
    argv: list[str] | None = None,
    editor_factory: Callable[[str], WikiEditor] = WikiEditor,
    ask: Callable[[str], str] = input,
    get_password: Callable[[str], str] = getpass.getpass,
) -> int:
    args = build_parser().parse_args(argv)
    review = Path(args.review)
    jsonl = review / "matched.jsonl"
    if not jsonl.exists():
        print(f"error: {jsonl} not found. Run the tool first.", file=sys.stderr)
        return 2
    if args.interval < 5:
        print("error: --interval must be at least 5 seconds.", file=sys.stderr)
        return 2
    try:
        contact = resolve_contact(args.contact)
    except MissingContactError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    entries = load_entries(jsonl)
    if args.species:
        entries = [e for e in entries if args.species.lower() in e.binomial.lower()]
    if args.limit is not None:
        entries = entries[: args.limit]
    if not entries:
        print("Nothing to apply.")
        return 0

    username = args.username or os.environ.get(USERNAME_ENV_VAR) or ask("Bot password username: ")
    password = os.environ.get(PASSWORD_ENV_VAR) or get_password("Bot password (not shown): ")
    editor = editor_factory(contact)
    try:
        account = editor.login(username.strip(), password)
    except LoginError as e:
        print(f"error: login failed: {e}", file=sys.stderr)
        return 2
    finally:
        del password

    print(
        f"Logged in as {account}. Edits are saved from this account, and you're "
        f"responsible for each one.\n{len(entries)} entries to look at; nothing is saved "
        "unless you answer y."
    )
    applier = Applier(editor, review / "applied.tsv", ask=ask, interval=args.interval)
    outcomes = applier.run(entries)
    summary = ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())) or "nothing done"
    print(f"\nDone: {summary}. Log: {review / 'applied.tsv'}")
    return 0
