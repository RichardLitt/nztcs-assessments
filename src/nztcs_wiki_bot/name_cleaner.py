"""Extract a clean binomial from an NZTCS species name and apply skip rules.

The NZTCS ``nztcsSpeciesName`` carries the author + year and assorted
annotations, e.g. ``"Aenetus virescens (Doubleday, 1843)"``. Wikipedia article
titles use the bare binomial, so we strip the authority before lookup.

Two classes of name are skipped before any Wikipedia lookup (per the design):

* **undescribed** — contains an ``sp.`` placeholder (``Archyala sp. A (...)``).
* **quoted-genus** — the genus is in scare quotes (``"Acroclita" discariana``),
  signalling an uncertain generic assignment that won't match an article.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# An undescribed-species marker: "sp." optionally followed by a designator.
# Matches "sp.", "sp. A", "sp. nov.", "spp.".
_UNDESCRIBED_RE = re.compile(r"\bsp{1,2}\.", re.IGNORECASE)

# Leading double quote (straight or curly) marks a scare-quoted genus.
_QUOTED_GENUS_RE = re.compile(r'^\s*["“”‘’]')

# Authority tail: "(Author, 1843)" or "Author, 1843" trailing the binomial.
# We anchor on the first occurrence of a 4-digit year and trim from the token
# that begins the authority. Simpler and safer: capture the leading
# Genus + species (+ optional subspecies) Latin words.
_BINOMIAL_RE = re.compile(
    r"^([A-Z][a-zÀ-ſ-]+)\s+([a-zÀ-ſ-]+)"
    r"(?:\s+([a-zÀ-ſ-]+))?"
)

SKIP_UNDESCRIBED = "undescribed"
SKIP_QUOTED_GENUS = "quoted_genus"
SKIP_UNPARSEABLE = "unparseable_name"


@dataclass(frozen=True)
class CleanName:
    """Result of cleaning an NZTCS name.

    Exactly one of ``binomial`` / ``skip_reason`` is set.
    """

    raw: str
    binomial: str | None = None
    genus: str | None = None
    species: str | None = None
    subspecies: str | None = None
    skip_reason: str | None = None

    @property
    def skipped(self) -> bool:
        return self.skip_reason is not None


def _normalise(text: str) -> str:
    """Normalise unicode, NBSP, and dash variants; collapse whitespace.

    >>> _normalise('Aenetus\\xa0virescens')
    'Aenetus virescens'
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ")  # NBSP
    # Normalise en/em dashes and minus to ASCII hyphen for year ranges.
    for dash in ("–", "—", "−"):
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(raw: str) -> CleanName:
    """Clean an NZTCS name into a binomial or a skip decision.

    >>> clean_name("Aenetus virescens (Doubleday, 1843)").binomial
    'Aenetus virescens'
    >>> clean_name("Archyala sp. A (NZAC04239001; Mataroa)").skip_reason
    'undescribed'
    >>> clean_name('"Acroclita" discariana Philpott, 1930').skip_reason
    'quoted_genus'
    """
    text = _normalise(raw)

    if _QUOTED_GENUS_RE.match(text):
        return CleanName(raw=raw, skip_reason=SKIP_QUOTED_GENUS)
    if _UNDESCRIBED_RE.search(text):
        return CleanName(raw=raw, skip_reason=SKIP_UNDESCRIBED)

    m = _BINOMIAL_RE.match(text)
    if not m:
        return CleanName(raw=raw, skip_reason=SKIP_UNPARSEABLE)

    genus, species, subspecies = m.group(1), m.group(2), m.group(3)
    # A bare subspecies word is only kept if it is not the start of an authority
    # (authorities start with an uppercase letter, already excluded by the regex
    # requiring a lowercase token). Build the canonical binomial.
    parts = [genus, species]
    if subspecies:
        parts.append(subspecies)
    binomial = " ".join(parts[:2])  # Wikipedia titles key on genus + species
    return CleanName(
        raw=raw,
        binomial=binomial,
        genus=genus,
        species=species,
        subspecies=subspecies,
    )
