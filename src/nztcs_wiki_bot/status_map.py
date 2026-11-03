"""Map NZTCS ``conservationStatusTitle`` values to Speciesbox ``|status=`` codes.

The mapping is verified against
https://en.wikipedia.org/wiki/Wikipedia:Conservation_status and real articles
(e.g. *Powelliphanta augusta* uses ``status = NC``, ``status_system = NZTCS``).

Design rule: the bot must **fail loudly** on an unknown status title rather than
silently skip it, so a new NZTCS category can never slip through as a missing
diff. Callers catch :class:`UnknownStatusError` and route the row to a dedicated
``unmapped`` bucket (and log the title so this table can be extended).
"""

from __future__ import annotations

# CSV conservationStatusTitle -> Speciesbox NZTCS short code.
STATUS_CODES: dict[str, str] = {
    "Nationally Critical": "NC",
    "Nationally Endangered": "NE",
    "Nationally Vulnerable": "NV",
    "Nationally Increasing": "NI",
    "Declining": "D",
    "Recovering": "R",
    "Relict": "Rel",
    "Naturally Uncommon": "NU",
    # 2025 manual renamed "Naturally Uncommon" -> "Uncommon"; same category.
    "Uncommon": "NU",
    "Not Threatened": "NT",
    "Data Deficient": "DD",
    "Extinct": "EX",
    "Migrant": "M",
    "Vagrant": "V",
    "Coloniser": "C",
    "Introduced and Naturalised": "IN",
}

# Titles that appear in NZTCS data but are deliberately NOT conservation codes:
# the species has no assessable threat status, so there is nothing to patch.
# These are recognised (routed to the ``unmapped`` bucket with a clear reason)
# rather than treated as a never-before-seen title that demands a table update.
NON_STATUS_TITLES: frozenset[str] = frozenset(
    {
        "Not assessed",
        "Taxonomically indistinct",
    }
)


class UnknownStatusError(ValueError):
    """Raised when a ``conservationStatusTitle`` has no mapping."""

    def __init__(self, title: str) -> None:
        self.title = title
        super().__init__(f"unknown NZTCS conservationStatusTitle: {title!r}")


def status_code(title: str) -> str:
    """Return the Speciesbox code for an NZTCS status title.

    >>> status_code("Nationally Critical")
    'NC'
    >>> status_code("Uncommon")
    'NU'

    Raises :class:`UnknownStatusError` on an unmapped title.
    """
    key = (title or "").strip()
    try:
        return STATUS_CODES[key]
    except KeyError:
        raise UnknownStatusError(title) from None


def is_known(title: str) -> bool:
    """Whether ``title`` maps to a code (without raising)."""
    return (title or "").strip() in STATUS_CODES
