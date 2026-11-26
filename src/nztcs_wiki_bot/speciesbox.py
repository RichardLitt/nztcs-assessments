"""Parse, verify, and patch Wikipedia Speciesbox/Taxobox templates.

Uses ``mwparserfromhell`` for robust template-parameter access — never regex on
template params, which breaks on nested ``{{...}}`` values (per the design).

Three things happen here:

* :func:`find_infobox` — locate a ``{{Speciesbox}}`` / ``{{Taxobox}}`` /
  ``{{Automatic taxobox}}`` / ``{{Subspeciesbox}}`` in an article's wikitext.
* :func:`verify_taxon` — confirm the infobox is about the expected binomial.
* :func:`patch_status` — insert/update the NZTCS status block, returning the
  new wikitext (or the original, unchanged, if already up to date).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import mwparserfromhell
from mwparserfromhell.nodes import Template
from mwparserfromhell.nodes.extras import Parameter
from mwparserfromhell.wikicode import Wikicode

INFOBOX_NAMES = {
    "speciesbox",
    "subspeciesbox",
    "infraspeciesbox",
    "taxobox",
    "automatic taxobox",
}

# How many status blocks (``status``, ``status2``, ``status3``) each template
# displays. The others silently ignore ``status3``.
_THREE_STATUS_TEMPLATES = {"speciesbox", "subspeciesbox"}

# Parameters that start the taxon part of an infobox. The Speciesbox and
# Taxobox documentation put the status block after the name and image
# parameters and before these, as do most articles. Any ``unranked_*`` rank
# (legacy Taxobox) also counts.
_TAXON_START_PARAMS = frozenset(
    {"taxon", "parent", "genus", "species", "subspecies", "variety", "regnum", "binomial"}
)


@dataclass
class Infobox:
    """A located species infobox plus its parsed document."""

    template: Template
    code: Wikicode
    name: str  # normalised lower-case template name


def _norm_template_name(name: str | Wikicode) -> str:
    return str(name).strip().lower()


def find_infobox(wikitext: str) -> Infobox | None:
    """Return the first species infobox in ``wikitext``, or ``None``.

    >>> find_infobox("no template here") is None
    True
    >>> ib = find_infobox("{{Speciesbox | genus=Aenetus | species=virescens}}")
    >>> ib.template.get("genus").value.strip()
    'Aenetus'
    """
    code = mwparserfromhell.parse(wikitext)
    for tmpl in code.filter_templates():
        if _norm_template_name(tmpl.name) in INFOBOX_NAMES:
            return Infobox(template=tmpl, code=code, name=_norm_template_name(tmpl.name))
    return None


def _clean_param(value: str | Wikicode) -> str:
    """Strip italics/links/whitespace from a template value for comparison.

    >>> _clean_param("''[[Aenetus]]''")
    'Aenetus'
    """
    text = str(value)
    text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)  # [[link|x]] -> link
    text = text.replace("'''", "").replace("''", "")  # bold/italics
    text = re.sub(r"<[^>]+>", "", text)  # stray HTML
    return text.strip()


def verify_taxon(infobox: Infobox, genus: str, species: str) -> bool:
    """Whether ``infobox`` is about ``genus species``.

    Accepts either explicit ``genus`` + ``species`` params or a combined
    ``taxon = Genus species`` param (used by ``{{Speciesbox}}`` shorthand and
    ``{{Automatic taxobox}}``). Comparison is case-insensitive and ignores
    italic/link markup.
    """
    tmpl = infobox.template
    want_genus = genus.strip().lower()
    want_species = species.strip().lower()

    if tmpl.has("genus") and tmpl.has("species"):
        g = _clean_param(tmpl.get("genus").value).lower()
        s = _clean_param(tmpl.get("species").value).lower()
        # species param sometimes repeats the genus ("Aenetus virescens").
        s = s.split()[-1] if s else s
        return g == want_genus and s == want_species

    for combined in ("taxon", "name"):
        if tmpl.has(combined):
            parts = _clean_param(tmpl.get(combined).value).lower().split()
            if len(parts) >= 2 and parts[0] == want_genus and parts[1] == want_species:
                return True
    return False


def current_status_system(infobox: Infobox) -> str | None:
    """Return the value of ``status_system`` if present, else ``None``."""
    tmpl = infobox.template
    if tmpl.has("status_system"):
        return _clean_param(tmpl.get("status_system").value)
    return None


@dataclass
class PatchResult:
    """Outcome of patching a Speciesbox."""

    before: str
    after: str
    action: str  # "insert" | "update" | "add_secondary" | "noop" | "no_free_slot"

    @property
    def changed(self) -> bool:
        return self.before != self.after


def _taxon_start(tmpl: Template) -> Parameter | None:
    """The first taxon/classification parameter, which a new status block goes
    before. ``None`` if the infobox has none, in which case the block is appended.
    """
    for param in tmpl.params:
        name = param.name.strip().lower()
        if name in _TAXON_START_PARAMS or name.startswith("unranked_"):
            return param
    return None


def _block_names(slot: str) -> tuple[str, str, str]:
    """The parameter names of a status block; ``slot`` is ``""``, ``"2"`` or ``"3"``."""
    return f"status{slot}", f"status{slot}_system", f"status{slot}_ref"


def _status_slots(infobox: Infobox) -> tuple[str, ...]:
    return ("", "2", "3") if infobox.name in _THREE_STATUS_TEMPLATES else ("", "2")


def _value(tmpl: Template, name: str) -> str:
    return _clean_param(tmpl.get(name).value) if tmpl.has(name) else ""


def _choose_slot(infobox: Infobox) -> str | None:
    """The status block to write: the one already holding NZTCS, else the first
    empty one. ``None`` if every block holds another status, which is never
    overwritten.
    """
    tmpl = infobox.template
    slots = _status_slots(infobox)
    for slot in slots:
        if _value(tmpl, f"status{slot}_system").upper().startswith("NZTCS"):
            return slot
    for slot in slots:
        code, system, _ = _block_names(slot)
        if not _value(tmpl, code) and not _value(tmpl, system):
            return slot
    return None


def _block_end_before(tmpl: Template, slot: str) -> Parameter | None:
    """The last parameter of the status blocks before ``slot``, which a new
    secondary block goes after."""
    earlier = {n for s in ("", "2", "3") if s < slot for n in _block_names(s)}
    last = None
    for param in tmpl.params:
        if param.name.strip().lower() in earlier:
            last = param
    return last


def patch_status(
    wikitext: str,
    genus: str,
    species: str,
    status_code: str,
    ref_name: str,
    ref_wikitext: str,
) -> PatchResult:
    """Add or update the NZTCS status block in an article's species infobox.

    Branches (per design):

    1. A status block already has system NZTCS → update its code and ref.
    2. Other statuses (e.g. IUCN3.1, CITES) → add NZTCS in the first empty
       block (``status2*``, then ``status3*`` where the template has it). With
       none empty, change nothing (``no_free_slot``).
    3. No status → insert ``status`` / ``status_system`` / ``status_ref``
       before the first taxon parameter (``taxon``, ``genus``, ``regnum``…),
       where the template documentation and most articles put it.

    Idempotent: re-running on already-patched wikitext is a no-op.
    """
    infobox = find_infobox(wikitext)
    if infobox is None:
        return PatchResult(before=wikitext, after=wikitext, action="noop")

    tmpl = infobox.template
    slot = _choose_slot(infobox)
    if slot is None:
        return PatchResult(before=wikitext, after=wikitext, action="no_free_slot")
    ref_value = f'<ref name="{ref_name}" />' if _ref_defined(wikitext, ref_name) else ref_wikitext

    if _value(tmpl, f"status{slot}_system").upper().startswith("NZTCS"):
        action = _update_block(tmpl, slot, status_code, ref_value, ref_name)
    elif slot:
        action = _add_secondary(tmpl, slot, status_code, ref_value)
    else:
        action = _insert_primary(tmpl, status_code, ref_value)

    after = _keep_reused_definitions(wikitext, str(infobox.code))
    if after == wikitext:
        action = "noop"
    return PatchResult(before=wikitext, after=after, action=action)


_DEFINITION = re.compile(
    r"<ref\s+name\s*=\s*"
    r"(?:\"(?P<dq>[^\"]+)\"|'(?P<sq>[^']+)'|(?P<bare>[^\s\"'/>]+))"
    r"\s*>.*?</ref>",
    re.DOTALL,
)


def _definitions(text: str) -> dict[str, str]:
    """Named ref definitions in ``text``: name → the full ``<ref …>…</ref>``."""
    defs: dict[str, str] = {}
    for m in _DEFINITION.finditer(text):
        name = m.group("dq") or m.group("sq") or m.group("bare")
        defs.setdefault(name, m.group(0))
    return defs


def _keep_reused_definitions(before: str, after: str) -> str:
    """Don't leave reuses of a citation pointing at nothing.

    Replacing ``status_ref`` can remove the full definition of an old citation
    that the article also reuses elsewhere as ``<ref name="X" />``. Wikipedia
    shows those reuses as a cite error. For each definition that disappeared
    but is still reused, put the full definition at its first remaining use.

    >>> before = '| status_ref = <ref name="old">{{cite x}}</ref>\\nText.<ref name="old" />'
    >>> after = '| status_ref = <ref name="new" />\\nText.<ref name="old" />'
    >>> print(_keep_reused_definitions(before, after))
    | status_ref = <ref name="new" />
    Text.<ref name="old">{{cite x}}</ref>
    """
    remaining = _definitions(after)
    for name, full in _definitions(before).items():
        if name in remaining:
            continue
        reuse = re.search(r"<ref\s+" + _name_attr(name) + r"\s*/>", after)
        if reuse:
            after = after[: reuse.start()] + full + after[reuse.end() :]
    return after


def _name_attr(ref_name: str) -> str:
    """Regex for ``name=X`` with X double-quoted, single-quoted or bare."""
    n = re.escape(ref_name)
    return rf"""name\s*=\s*(?:"{n}"|'{n}'|{n}(?=[\s/>]))"""


def _ref_defined(wikitext: str, ref_name: str) -> bool:
    """Whether a full ``<ref name="X">...</ref>`` already exists in the article.

    >>> _ref_defined('<ref name=Hoare2026>{{CiteQ|Q1}}</ref>', "Hoare2026")
    True
    >>> _ref_defined('<ref name="Hoare2026" />', "Hoare2026")
    False
    """
    pattern = re.compile(
        r"<ref\s+" + _name_attr(ref_name) + r"\s*>.*?</ref>",
        re.DOTALL,  # ref names are case-sensitive
    )
    return bool(pattern.search(wikitext))


def _ref_name_in(value: str | Wikicode, ref_name: str) -> bool:
    """Whether a status_ref value already cites ``ref_name`` (full or self-closing).

    >>> _ref_name_in("<ref name=Hoare2026 />", "Hoare2026")
    True
    >>> _ref_name_in('<ref name="Hoare20261" />', "Hoare2026")
    False
    """
    return bool(re.search(_name_attr(ref_name), str(value)))


def _update_block(
    tmpl: Template, slot: str, status_code: str, ref_value: str, ref_name: str
) -> str:
    code, system, ref = _block_names(slot)
    changed = False
    if _value(tmpl, code) != status_code:
        _set_after(tmpl, _block_end_before(tmpl, slot), code, status_code)
        changed = True
    # Only (re)write the ref when it doesn't already cite our ref name.
    if not (tmpl.has(ref) and _ref_name_in(tmpl.get(ref).value, ref_name)):
        _set_after(tmpl, tmpl.get(system), ref, ref_value)
        changed = True
    return "update" if changed else "noop"


def _add_secondary(tmpl: Template, slot: str, status_code: str, ref_value: str) -> str:
    # New lines go straight after the earlier status blocks, in order. Empty
    # placeholders are filled where they are.
    after = _block_end_before(tmpl, slot)
    for name, value in zip(_block_names(slot), (status_code, "NZTCS", ref_value), strict=True):
        after = _set_after(tmpl, after, name, value)
    return "add_secondary"


def _set_after(tmpl: Template, after: Parameter | None, name: str, value: str) -> Parameter:
    """Set ``name``; if it's new, place it right after ``after`` (or append).

    An existing parameter is updated where it is, never moved.
    """
    if tmpl.has(name) or after is None:
        tmpl.add(name, value, preserve_spacing=True)
    else:
        tmpl.add(name, value, after=after, preserve_spacing=True)
    return tmpl.get(name)


def _insert_primary(tmpl: Template, status_code: str, ref_value: str) -> str:
    # Each line goes before the same taxon parameter, so they keep this order.
    # With no taxon parameter, ``before=None`` appends.
    before = _taxon_start(tmpl)
    tmpl.add("status", status_code, before=before, preserve_spacing=True)
    tmpl.add("status_system", "NZTCS", before=before, preserve_spacing=True)
    tmpl.add("status_ref", ref_value, before=before, preserve_spacing=True)
    return "insert"
