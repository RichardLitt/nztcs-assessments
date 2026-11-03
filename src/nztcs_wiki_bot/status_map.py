"""Map NZTCS ``conservationStatusTitle`` values to Speciesbox ``|status=`` codes.

Only codes that Wikipedia can actually render are mapped. The source of truth is
the ``p.NZTCS`` function in
https://en.wikipedia.org/wiki/Module:Conservation_status, which shows
"Invalid status" (and adds a maintenance category) for anything else.

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


# Real NZTCS categories (mostly non-resident or introduced species) that
# Wikipedia's Module:Conservation status has no badge for. Patching these would
# render "Invalid status", so they are routed to ``unmapped`` instead.
NO_WIKIPEDIA_CODE_TITLES: frozenset[str] = frozenset(
    {
        "Migrant",
        "Vagrant",
        "Coloniser",
        "Introduced and Naturalised",
    }
)


def unmapped_reason(title: str) -> str:
    """Why a title has no code: ``non-status``, ``no-wikipedia-code`` or
    ``unknown-status-title`` (a title this table has never seen).

    >>> unmapped_reason("Vagrant")
    'no-wikipedia-code'
    >>> unmapped_reason("Something New")
    'unknown-status-title'
    """
    key = (title or "").strip()
    if key in NON_STATUS_TITLES:
        return "non-status"
    if key in NO_WIKIPEDIA_CODE_TITLES:
        return "no-wikipedia-code"
    return "unknown-status-title"


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
