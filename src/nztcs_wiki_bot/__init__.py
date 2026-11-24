"""NZTCS → Wikipedia Speciesbox bot.

Generates a *review queue* of wikitext patches that add NZ Threat Classification
System conservation statuses to Wikipedia species articles. The review run is
strictly read-only against the MediaWiki API. ``nztcs-wiki-bot apply`` can then
save reviewed patches from the operator's own account, asking before each edit
(see :mod:`.apply` and :mod:`.editor`).

See ``docs/design.md`` for the full design.
"""

__version__ = "0.1.0"
