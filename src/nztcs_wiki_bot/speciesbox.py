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
    action: str  # "insert" | "update" | "add_secondary" | "noop"

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


def _primary_block_end(tmpl: Template) -> Parameter | None:
    """The last of ``status`` / ``status_system`` / ``status_ref``, which a new
    ``status2`` block goes after."""
    last = None
    for param in tmpl.params:
        if param.name.strip().lower() in ("status", "status_system", "status_ref"):
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

    1. Already ``status_system = NZTCS`` → update ``status`` + ``status_ref``.
    2. A non-NZTCS ``status_system`` (e.g. IUCN3.1) → add ``status2*`` block.
    3. No status block → insert ``status`` / ``status_system`` / ``status_ref``
       before the first taxon parameter (``taxon``, ``genus``, ``regnum``…),
       where the template documentation and most articles put it.

    Idempotent: re-running on already-patched wikitext is a no-op.
    """
    infobox = find_infobox(wikitext)
    if infobox is None:
        return PatchResult(before=wikitext, after=wikitext, action="noop")

    tmpl = infobox.template
    system = current_status_system(infobox)
    ref_value = f'<ref name="{ref_name}" />' if _ref_defined(wikitext, ref_name) else ref_wikitext

    if system is not None and system.upper().startswith("NZTCS"):
        action = _update_primary(tmpl, status_code, ref_value, ref_name)
    elif system is not None:
        action = _add_secondary(tmpl, status_code, ref_value, ref_name)
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


def _update_primary(tmpl: Template, status_code: str, ref_value: str, ref_name: str) -> str:
    changed = False
    has_code = tmpl.has("status") and _clean_param(tmpl.get("status").value) == status_code
    if not has_code:
        tmpl.add("status", status_code, preserve_spacing=True)
        changed = True
    if not tmpl.has("status_system") or not _clean_param(
        tmpl.get("status_system").value
    ).upper().startswith("NZTCS"):
        tmpl.add("status_system", "NZTCS", preserve_spacing=True)
        changed = True
    # Only (re)write status_ref when it doesn't already cite our ref name.
    if not (tmpl.has("status_ref") and _ref_name_in(tmpl.get("status_ref").value, ref_name)):
        tmpl.add("status_ref", ref_value, preserve_spacing=True)
        changed = True
    return "update" if changed else "noop"


def _add_secondary(tmpl: Template, status_code: str, ref_value: str, ref_name: str) -> str:
    has_nztcs_secondary = tmpl.has("status2_system") and _clean_param(
        tmpl.get("status2_system").value
    ).upper().startswith("NZTCS")
    changed = False
    # New status2* lines go straight after the primary status block, in order.
    after = _primary_block_end(tmpl)
    has_code = tmpl.has("status2") and _clean_param(tmpl.get("status2").value) == status_code
    if not has_code:
        after = _set_after(tmpl, after, "status2", status_code)
        changed = True
    elif tmpl.has("status2"):
        after = tmpl.get("status2")
    if not has_nztcs_secondary:
        after = _set_after(tmpl, after, "status2_system", "NZTCS")
        changed = True
    elif tmpl.has("status2_system"):
        after = tmpl.get("status2_system")
    if not (tmpl.has("status2_ref") and _ref_name_in(tmpl.get("status2_ref").value, ref_name)):
        _set_after(tmpl, after, "status2_ref", ref_value)
        changed = True
    if not changed:
        return "noop"
    return "update" if has_nztcs_secondary else "add_secondary"


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
