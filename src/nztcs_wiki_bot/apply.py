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
import re
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
# A page on the operator's account explaining the tool. Edit summaries link to
# it once it exists (see docs/assisted-editing.md).
TOOL_PAGE = "User:{account}/nztcs-wiki-bot"

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


def previously_skipped(log_path: Path) -> set[tuple[str, str]]:
    """``(species_id, title)`` pairs whose latest decision in the log is a skip.

    Only your own answers count: ``skipped`` (you said n) and ``saved``. If you
    saved an entry after skipping it, the save wins. Other outcomes (``changed``,
    ``error:…`` and so on) aren't decisions and are ignored.

    >>> import tempfile
    >>> log = Path(tempfile.mkdtemp()) / "applied.tsv"
    >>> _ = log.write_text(
    ...     "time\\tspecies_id\\ttitle\\toutcome\\trevid\\n"
    ...     "t\\t1\\tMonarch butterfly\\tskipped\\t\\n"
    ...     "t\\t2\\tYellow admiral\\tskipped\\t\\n"
    ...     "t\\t2\\tYellow admiral\\tsaved\\t99\\n"
    ...     "t\\t3\\tZizina otis\\tchanged\\t\\n")
    >>> sorted(previously_skipped(log))
    [('1', 'Monarch butterfly')]
    """
    if not log_path.exists():
        return set()
    latest: dict[tuple[str, str], str] = {}
    for line in log_path.read_text(encoding="utf-8").splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) >= 4 and cols[3] in ("skipped", "saved"):
            latest[(cols[1], cols[2])] = cols[3]
    return {key for key, outcome in latest.items() if outcome == "skipped"}


def tool_note(tool_page: str | None) -> str:
    """The end of every edit summary: a link to the tool page, if there is one.

    >>> tool_note("User:Richlitt/nztcs-wiki-bot")
    'assisted edit with [[User:Richlitt/nztcs-wiki-bot|nztcs-wiki-bot]]'
    >>> tool_note(None)
    'assisted edit with nztcs-wiki-bot'
    """
    return f"assisted edit with [[{tool_page}|nztcs-wiki-bot]]" if tool_page else TOOL_NOTE


def edit_summary(entry: Entry, note: str = TOOL_NOTE) -> str:
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
    return f"{what}; {note}"


def _article_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))


# Status names that might appear in an article's prose: every NZTCS title the
# tool knows, plus the group names and older (2002/2008) categories.
_STATUS_NAMES = sorted(
    {
        *status_map.STATUS_CODES,
        *status_map.PENDING_WIKIPEDIA_CODES,
        "At Risk", "Threatened", "Serious Decline", "Gradual Decline", "Sparse",
        "Range Restricted", "Non-resident Native",
    },
    key=len,
    reverse=True,
)
_STATUS_NAME = re.compile("|".join(re.escape(n) for n in _STATUS_NAMES), re.IGNORECASE)
_NZTCS_HINT = re.compile(r"Threat Classification|NZTCS|Department of Conservation", re.IGNORECASE)


def _plain(text: str) -> str:
    """Wikitext → readable text: drop refs, comments, templates and markup."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    return re.sub(r"'{2,}", "", text)


def status_sentences(entry: Entry, limit: int = 3) -> list[str]:
    """Sentences outside the infobox that describe an NZTCS status.

    A sentence counts if it mentions the NZTCS (or the Department of
    Conservation) and a status name. The infobox patch doesn't change prose,
    so these may contradict the new status.

    >>> before = ("{{Speciesbox\\n| genus = A\\n}}\\nA moth. In 2017 the "
    ...           "[[Department of Conservation]] classified it as ''Nationally "
    ...           "Vulnerable''.<ref>x</ref> It flies at night.")
    >>> status_sentences(Entry("1", "A b", "A b", "DD", "insert", before, before, ""))
    ['In 2017 the Department of Conservation classified it as Nationally Vulnerable.']
    """
    box = find_infobox(entry.before)
    text = entry.before.replace(str(box.template), "", 1) if box else entry.before
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", _plain(text)):
        sentence = " ".join(sentence.split())
        if _NZTCS_HINT.search(sentence) and _STATUS_NAME.search(sentence):
            found.append(sentence if len(sentence) <= 300 else sentence[:299] + "…")
            if len(found) == limit:
                break
    return found


def mentions_status(sentence: str, code: str) -> bool:
    """Whether a sentence names the status for ``code``.

    >>> mentions_status("classified as Data Deficient", "DD")
    True
    >>> mentions_status("classified as Nationally Vulnerable", "DD")
    False
    """
    label = _LABELS.get(code, code)
    return label.lower() in sentence.lower()


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


def changes_outside_infobox(entry: Entry) -> bool:
    """Whether the edit also changes text outside the infobox, which
    :func:`infobox_view` doesn't show (for example, a citation definition moved
    into the body so its other uses keep working)."""
    before, after = find_infobox(entry.before), find_infobox(entry.after)
    if before is None or after is None:
        return False
    rest_before = entry.before.replace(str(before.template), "", 1)
    rest_after = entry.after.replace(str(after.template), "", 1)
    return rest_before != rest_after


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
        note: str = TOOL_NOTE,
    ) -> None:
        self.color = _use_color() if color is None else color
        self.note = note
        self.editor = editor
        self.log_path = log_path
        self.ask = ask
        self.say = say
        self.interval = interval
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.open_url = open_url or webbrowser.open
        self._last_save: float | None = None
        self._asked = False
        self.outcomes: Counter[str] = Counter()

    def run(self, entries: list[Entry], limit: int | None = None) -> Counter[str]:
        """Go through ``entries``. With ``limit``, stop after asking about that
        many; entries skipped without asking (already applied, changed, …)
        don't count towards it."""
        total = len(entries)
        asked = 0
        for i, entry in enumerate(entries, 1):
            if limit is not None and asked >= limit:
                self.say(f"\nReached --limit {limit}.")
                break
            self._asked = False
            outcome = self._one(entry, i, total)
            asked += self._asked
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
        self._warn_about_prose(entry)
        self.say("Infobox after this edit (+ added, - removed):\n")
        self.say(infobox_view(entry, self.color))
        if changes_outside_infobox(entry):
            self.say(
                "\nThis edit also changes text outside the infobox, such as an old "
                "citation moved so its other uses keep working. Press d to see it."
            )
        self._asked = True
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

    def _warn_about_prose(self, entry: Entry) -> None:
        sentences = status_sentences(entry)
        if not sentences:
            return
        label = _LABELS.get(entry.status_code, entry.status_code)
        self.say("The article text also describes a conservation status:")
        for sentence in sentences:
            self.say(f'  "{sentence}"')
        if all(mentions_status(s, entry.status_code) for s in sentences):
            self.say(f"It mentions {label}, which matches.")
        else:
            self.say(
                f"Note: the text may not match the new status ({label}). This tool only "
                "changes the infobox, so open the article (o) and update the text yourself "
                "if needed."
            )
        self.say("")

    def _save(self, entry: Entry, page) -> str:
        if self._last_save is not None:
            wait = self.interval - (self.clock() - self._last_save)
            if wait > 0:
                self.say(f"(waiting {wait:.0f}s between saves)")
                self.sleep(wait)
        try:
            revid = self.editor.save(page, entry.after, edit_summary(entry, self.note))
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
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ask about at most N entries. Entries skipped without asking (already applied, "
        "changed since the run, skipped before, …) don't count.",
    )
    p.add_argument(
        "--show-skipped",
        action="store_true",
        help="Also show entries you skipped (answered n) in earlier sessions. They're hidden "
        "by default; the record is kept in applied.tsv in the review folder.",
    )
    p.add_argument(
        "--tool-page",
        default=None,
        help="Page explaining the tool, linked from edit summaries once it exists "
        "(default: User:<your account>/nztcs-wiki-bot)",
    )
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
    if not args.show_skipped:
        skipped_before = previously_skipped(review / "applied.tsv")
        hidden = [e for e in entries if (e.species_id, e.title) in skipped_before]
        if hidden:
            entries = [e for e in entries if (e.species_id, e.title) not in skipped_before]
            print(
                f"Not showing {len(hidden)} entr{'y' if len(hidden) == 1 else 'ies'} you skipped "
                "before. Use --show-skipped to see them again."
            )
    if args.species:
        entries = [e for e in entries if args.species.lower() in e.binomial.lower()]
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
        f"responsible for each one.\n{len(entries)} entries to look at"
        + (f", asking about at most {args.limit}" if args.limit is not None else "")
        + "; nothing is saved unless you answer y."
    )
    tool_page = args.tool_page or TOOL_PAGE.format(account=account)
    if editor.get_page(tool_page).missing:
        print(
            f"\nTip: create the page [[{tool_page}]] explaining what this tool does "
            "(there's a draft in docs/assisted-editing.md). Edit summaries will link to "
            "it once it exists. For now they say 'assisted edit with nztcs-wiki-bot'."
        )
        tool_page = None
    applier = Applier(
        editor, review / "applied.tsv", ask=ask, interval=args.interval, note=tool_note(tool_page)
    )
    outcomes = applier.run(entries, limit=args.limit)
    summary = ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())) or "nothing done"
    print(f"\nDone: {summary}. Log: {review / 'applied.tsv'}")
    return 0
