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

As of 2026-11-04 the module accepts the codes below. The last column says which
NZTCS manual the status belongs to: Molloy et al. 2002, Townsend et al. 2008, or
Rolfe et al. 2022, which DOC reports have used since July 2024.

| Code | Renders as | NZTCS manual |
|---|---|---|
| `EX` | Extinct | 2008, 2022 |
| `NC` | Nationally Critical | 2008, 2022 |
| `NE` | Nationally Endangered | 2008, 2022 |
| `NV` | Nationally Vulnerable | 2008, 2022 |
| `NI` | Nationally Increasing | 2022 (was At Risk – Recovering A in 2008) |
| `D` | Declining | 2008, 2022 |
| `R` | Recovering | 2008 (Recovering B), 2022 |
| `Rel` | Relict | 2008 only; a qualifier since 2022 |
| `NU` | Naturally Uncommon | 2008 only; widened to Uncommon in 2022 |
| `NT` | Not Threatened | 2008, 2022 |
| `DD` | Data Deficit *(sic)* | 2008, 2022 |
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
| Relict | `Rel` | Module (also accepts `REL`, `rel`). Only in reports assessed under the 2008 manual. |
| Naturally Uncommon | `NU` | Module |
| Uncommon, criteria `UNCn…` | `NU` | 2022 manual (§2.2): Uncommon with a natural population state is what the 2008 manual called Naturally Uncommon. |
| Not Threatened | `NT` | Module |
| Data Deficient | `DD` | Module |
| Extinct | `EX` | Module |

## Titles with no code

These go to `unmapped.tsv` and produce no patch. The `reason` column says which
case applies.

| Title | Reason | Why |
|---|---|---|
| Coloniser | `no-wikipedia-code` | Real NZTCS category the module doesn't render yet. Proposed code `CO`. |
| Migrant | `no-wikipedia-code` | Same. Proposed code `MI`. |
| Vagrant | `no-wikipedia-code` | Same. Proposed code `VA`. |
| Introduced and Naturalised | `no-wikipedia-code` | Same. Proposed code `IN`. |
| Uncommon, criteria `UNCu…`, `UNCx…` or blank | `no-wikipedia-code` | The population isn't natural (or is unknown, which the manual treats as unnatural), so "Naturally Uncommon" would be wrong. Proposed code `U`. |
| Not assessed | `non-status` | The species has no assessment. |
| Taxonomically indistinct | `non-status` | Not a distinct taxon for assessment purposes. |
| *anything else* | `unknown-status-title` | A title this table has never seen. See below. |

Adding the `no-wikipedia-code` categories to the module is proposed in
[proposals/module-conservation-status-nztcs.md](proposals/module-conservation-status-nztcs.md).
Their codes are kept in `status_map.PENDING_WIKIPEDIA_CODES`. Once the module
accepts them, move those entries into `STATUS_CODES`, using the codes the
module adopted.

## Why unknown titles fail loudly

A missing mapping must never turn into a silently wrong edit, or a silently
missing one. So an unrecognised title isn't guessed, defaulted or dropped. It is
listed in `unmapped.tsv` as `unknown-status-title`, so whoever runs the report
sees it and makes a deliberate decision. See
[adding-a-report.md](adding-a-report.md#4-check-unmappedtsv) for how to add one.

Calling `status_map.status_code()` directly on an unknown title raises
`UnknownStatusError`.
