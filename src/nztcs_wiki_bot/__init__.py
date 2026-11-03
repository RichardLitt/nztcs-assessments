"""NZTCS → Wikipedia Speciesbox bot.

Generates a *review queue* of wikitext patches that add NZ Threat Classification
System conservation statuses to Wikipedia species articles. The bot is strictly
read-only against the MediaWiki API; it never performs live edits.

See ``docs/design.md`` for the full design.
"""

__version__ = "0.1.0"
