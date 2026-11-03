# NZTCS status codes

The NZTCS CSV gives each species a `conservationStatusTitle` such as
"Nationally Vulnerable". The Wikipedia Speciesbox needs a short code
(`status = NV`) plus `status_system = NZTCS`. This page lists every mapping, where it
comes from, and what happens to titles that have no code.

The code lives in
[`src/nztcs_wiki_bot/status_map.py`](../src/nztcs_wiki_bot/status_map.py).

## Codes Wikipedia can render

The Speciesbox draws its conservation badge through
[Module:Conservation status](https://en.wikipedia.org/wiki/Module:Conservation_status).
Its `p.NZTCS` function is the source of truth for which codes display. Anything
else renders as ***Invalid status*** and puts the article in
[Category:Invalid conservation status](https://en.wikipedia.org/wiki/Category:Invalid_conservation_status).

As of 2026-11-03 the module accepts:

| Code | Renders as | NZTCS era |
|---|---|---|
| `EX` | Extinct | current |
| `NC` | Nationally Critical | 2019 + |
| `NE` | Nationally Endangered | 2019 + |
| `NV` | Nationally Vulnerable | 2019 + |
| `NI` | Nationally Increasing | 2019 + |
| `D` | Declining | 2019 + |
| `Rel` | Relict | 2019 + |
| `NU` | Naturally Uncommon | 2019 + |
| `R` | Recovering | 2008 (folded into NI in 2019) |
| `NT` | Not Threatened | current |
| `DD` | Data Deficit *(sic)* | current |
| `SD`, `GD`, `SP`, `RR` | Serious Decline, Gradual Decline, Sparse, Range Restricted | 2002, not produced by this tool |

A unit test (`test_every_mapped_code_renders_on_wikipedia`) pins the tool's
codes to this list. If Wikipedia adds or drops a code, update the test and this
page together.

## Mapping table

| NZTCS `conservationStatusTitle` | Speciesbox code | Source / note |
|---|---|---|
| Nationally Critical | `NC` | Module; e.g. [Powelliphanta augusta](https://en.wikipedia.org/wiki/Powelliphanta_augusta) |
| Nationally Endangered | `NE` | Module |
| Nationally Vulnerable | `NV` | Module |
| Nationally Increasing | `NI` | Module |
| Declining | `D` | Module |
| Recovering | `R` | Module (2008 category, still renders) |
| Relict | `Rel` | Module (also accepts `REL`, `rel`) |
| Naturally Uncommon | `NU` | Module |
| Uncommon | `NU` | **Judgement call.** Later NZTCS reports use "Uncommon" for the category Wikipedia calls Naturally Uncommon. |
| Not Threatened | `NT` | Module |
| Data Deficient | `DD` | Module |
| Extinct | `EX` | Module |

## Titles with no code

These go to `unmapped.tsv` and produce no patch. The `reason` column says which
case applies.

| Title | Reason | Why |
|---|---|---|
| Migrant | `no-wikipedia-code` | Real NZTCS category with no badge in the module. |
| Vagrant | `no-wikipedia-code` | Same. |
| Coloniser | `no-wikipedia-code` | Same. |
| Introduced and Naturalised | `no-wikipedia-code` | Same. |
| Not assessed | `non-status` | The species has no assessment. |
| Taxonomically indistinct | `non-status` | Not a distinct taxon for assessment purposes. |
| *anything else* | `unknown-status-title` | A title this table has never seen. See below. |

If Wikipedia later adds badges for the `no-wikipedia-code` titles, move them
into `STATUS_CODES` with the module's code.

## Why unknown titles fail loudly

A missing mapping must never turn into a silently wrong edit, or a silently
missing one. So an unrecognised title isn't guessed, defaulted or dropped. It is
listed in `unmapped.tsv` as `unknown-status-title`, so whoever runs the report
sees it and makes a deliberate decision. See
[adding-a-report.md](adding-a-report.md#4-check-unmappedtsv) for how to add one.

Calling `status_map.status_code()` directly on an unknown title raises
`UnknownStatusError`.
