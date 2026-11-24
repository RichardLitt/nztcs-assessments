"""Extract a clean binomial from an NZTCS species name and apply skip rules.

The NZTCS ``nztcsSpeciesName`` carries the author + year and assorted
annotations, e.g. ``"Aenetus virescens (Doubleday, 1843)"``. Wikipedia article
titles use the bare binomial, so we strip the authority before lookup.

These names are skipped before any Wikipedia lookup (per the design):

* **undescribed** — contains an ``sp.`` placeholder (``Archyala sp. A (...)``).
* **quoted-genus** — the genus is in scare quotes (``"Acroclita" discariana``),
  signalling an uncertain generic assignment that won't match an article.
* **uncertain identification** — ``cf.`` or ``aff.`` before the epithet
  (``Chalastra cf. pellurgata``): a provisional identification, not the
  named species.
* **subspecies** — a trinomial (``Vanessa gonerilla ida``). The assessment is
  for the subspecies, so it must not go on the species article.
* **taxon concept** — ``s.l.`` / ``s.s.`` after the species
  (``Pyrgotis pyramidias s.s.``): the report assesses a broad or narrow concept
  of the species separately, so neither status belongs to the article as such.

A ``s.l.`` / ``s.s.`` straight after the *genus* (``Hierodoris s.l. insignis``)
only qualifies the genus, so it is dropped and the species is looked up.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# An undescribed-species marker: "sp." optionally followed by a designator.
# Matches "sp.", "sp. A", "sp. nov.", "spp.".
_UNDESCRIBED_RE = re.compile(r"\bsp{1,2}\.", re.IGNORECASE)

# "cf." / "aff.": the specimen is compared with, or akin to, the named species.
_UNCERTAIN_RE = re.compile(r"\b(?:cf|aff)\.", re.IGNORECASE)

# Sensu lato / sensu stricto, abbreviated or not.
_SENSU = r"(?:s\.\s?[ls]\.|sensu\s+(?:lato|stricto))"
# ... straight after the genus: qualifies the genus only, so drop it.
_GENUS_SENSU_RE = re.compile(r"^([A-Z][a-zÀ-ſ-]+)\s+" + _SENSU + r"\s+", re.IGNORECASE)
# ... after the species: a separately assessed concept of the species.
_SPECIES_SENSU_RE = re.compile(r"^[A-Z][a-zÀ-ſ-]+\s+[a-zÀ-ſ-]+\s+" + _SENSU, re.IGNORECASE)

# Lowercase words that can start an authority and so aren't subspecies names.
_AUTHORITY_PARTICLES = frozenset({"de", "von", "van", "der", "du", "da", "di", "la", "le"})

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
SKIP_UNCERTAIN = "uncertain_identification"
SKIP_SUBSPECIES = "subspecies"
SKIP_TAXON_CONCEPT = "taxon_concept"


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
    >>> clean_name("Vanessa gonerilla ida (Alfken, 1899)").skip_reason
    'subspecies'
    >>> clean_name("Pyrgotis pyramidias s.s. Meyrick, 1901").skip_reason
    'taxon_concept'
    >>> clean_name("Chalastra cf. pellurgata (NZAC04193100)").skip_reason
    'uncertain_identification'
    >>> clean_name("Hierodoris s.l. insignis Philpott, 1926").binomial
    'Hierodoris insignis'
    """
    text = _normalise(raw)

    if _QUOTED_GENUS_RE.match(text):
        return CleanName(raw=raw, skip_reason=SKIP_QUOTED_GENUS)
    if _UNDESCRIBED_RE.search(text):
        return CleanName(raw=raw, skip_reason=SKIP_UNDESCRIBED)
    if _UNCERTAIN_RE.search(text):
        return CleanName(raw=raw, skip_reason=SKIP_UNCERTAIN)
    if _SPECIES_SENSU_RE.match(text):
        return CleanName(raw=raw, skip_reason=SKIP_TAXON_CONCEPT)
    text = _GENUS_SENSU_RE.sub(r"\1 ", text)

    m = _BINOMIAL_RE.match(text)
    if not m:
        return CleanName(raw=raw, skip_reason=SKIP_UNPARSEABLE)

    genus, species, third = m.group(1), m.group(2), m.group(3)
    # Authorities start with an uppercase letter, which the regex already
    # excludes, or with a lowercase particle such as "de".
    if third and third.lower() not in _AUTHORITY_PARTICLES:
        return CleanName(raw=raw, skip_reason=SKIP_SUBSPECIES)
    return CleanName(raw=raw, binomial=f"{genus} {species}", genus=genus, species=species)
