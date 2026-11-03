# Proposal: render the remaining NZTCS categories on Wikipedia

**Status:** draft, not yet posted.
**Where it goes:** [Module talk:Conservation status](https://en.wikipedia.org/wiki/Module_talk:Conservation_status)
(the module is template-editor protected, so the change has to be made by a
template editor).

## Background

`{{Speciesbox}}` and `{{Taxobox}}` render `status_system = NZTCS` through
`p.NZTCS` in [Module:Conservation status](https://en.wikipedia.org/wiki/Module:Conservation_status).
As of 2026-11-04 it accepts `EX`, `NC`, `NE`, `NV`, `NI`, `D`, `Rel`, `NU`,
`R`, `NT`, `DD`, and the 2002-era `SD`, `GD`, `SP`, `RR`. Anything else renders
"*Invalid status*" and adds the article to
[Category:Invalid conservation status](https://en.wikipedia.org/wiki/Category:Invalid_conservation_status).

NZTCS also has four categories that every DOC report assigns but that aren't
threat assessments. The current manual (Rolfe et al. 2022, §5, pp. 31–32)
defines them as:

| NZTCS category | Group | Definition (Rolfe et al. 2022) |
|---|---|---|
| Coloniser | Non-resident Native | "Taxa that would trigger one of the Threatened categories because of their small population sizes but have arrived in New Zealand without direct or indirect help from humans and have been successfully reproducing in the wild for fewer than 50 years" |
| Migrant | Non-resident Native | "Taxa that predictably and cyclically visit New Zealand as part of their normal life cycle (with a minimum of 15 individuals being known or presumed to visit each year) but do not breed here" |
| Vagrant | Non-resident Native | "Taxa that are found unexpectedly in New Zealand and whose presence in this region is naturally transitory or migratory taxa that have fewer than 15 individuals being known or presumed to visit each year" |
| Introduced and Naturalised | — | "Taxa that have become naturalised in New Zealand after being deliberately or accidentally introduced by human agency" (a self-sustaining wild population over at least three generations, spread beyond the initial site) |

The manual is explicit that taxa in these categories are *listed* by category
but "their conservation statuses are not assessed under the NZTCS" (§2, p. 14).
So the category is the NZTCS status of record for these taxa, but it isn't a
position on the threat scale.

DOC reports have used the 2022 manual since July 2024; the categories carry
over from the 2008 manual (Townsend et al. 2008), and Wikipedia's
[NZTCS article](https://en.wikipedia.org/wiki/New_Zealand_Threat_Classification_System#Other_categories)
lists them under "Other categories". In the 2025 Lepidoptera report alone, 13
of 507 taxa are in them (6 Vagrant, 5 Introduced and Naturalised, 2 Coloniser).
Without module support, editors can't record those statuses at all.

## Proposed change

Add four codes to `p.NZTCS`, rendered as text linked to the NZTCS article, with
no badge image. These categories aren't threat assessments, so a threat-scale
badge would misrepresent them; IUCN `NE` and `NA` are text-only for the same
reason:

| Code | Renders as |
|---|---|
| `CO` / `co` | Coloniser |
| `MI` / `mi` | Migrant |
| `VA` / `va` | Vagrant |
| `IN` / `in` | Introduced and Naturalised |

NZTCS doesn't define short codes for these, so the codes are new. None collides
with an existing NZTCS code or alias.

Diff against the live module (insert after the `DD` branch, before the 2002
categories):

```diff
    elseif status == "DD" or status == "dd" then
     	output = p.addImage("Status 2019 NZTCS DD.svg", "Data Deficit" ) .. "Data Deficit" 
+
+   -- Non-resident Native (CO, MI, VA) and Introduced and Naturalised (IN).
+   -- Not assessed for threat under the NZTCS, so no badge.
+   elseif status == "CO" or status == "co" then
+    	output = "[[New Zealand Threat Classification System#Other categories|Coloniser]]"
+   elseif status == "MI" or status == "mi" then
+    	output = "[[New Zealand Threat Classification System#Other categories|Migrant]]"
+   elseif status == "VA" or status == "va" then
+    	output = "[[New Zealand Threat Classification System#Other categories|Vagrant]]"
+   elseif status == "IN" or status == "in" then
+    	output = "[[New Zealand Threat Classification System#Other categories|Introduced and Naturalised]]"
    
    --  Older categories (version 2002): SD,GD,SP,RR
```

`Module:Conservation status/sandbox` is currently behind the live module (it
lacks the TSPA system), so it should be synced from the live version before the
change is applied there for testing.

### Test cases

`{{Speciesbox}}` and `{{Taxobox}}` pass NZTCS codes straight through
`{{Taxobox/species}}` to the module, so no template change is needed. Each of
these should render the label shown, with no "Invalid status" and no
maintenance category:

| Wikitext | Expected |
|---|---|
| `{{Taxobox/species\|NZTCS\|CO}}` | Coloniser |
| `{{Taxobox/species\|NZTCS\|MI}}` | Migrant |
| `{{Taxobox/species\|NZTCS\|VA}}` | Vagrant |
| `{{Taxobox/species\|NZTCS\|IN}}` | Introduced and Naturalised |
| `{{Taxobox/species\|NZTCS\|NT}}` | Not Threatened (unchanged) |

Real examples from the 2025 Lepidoptera report: *Danaus petilia* (Coloniser),
*Hypolimnas bolina* (Vagrant; the manual itself uses *H. bolina nerina* as a
Vagrant example), *Pieris rapae* (Introduced and Naturalised).

## References

- Rolfe, J.; Hitchmough, R.; Michel, P.; Makan, T.; Cooper, J.A.; de Lange, P.J.;
  Townsend, C.A.J.; Miskelly, C.M.; Molloy, J. 2022. *New Zealand Threat
  Classification System manual 2022. Part 1: Assessments.* Department of
  Conservation, Wellington.
  [DOC page](https://www.doc.govt.nz/about-us/science-publications/conservation-publications/nz-threat-classification-system/nz-threat-classification-system-manual-2022/)
- Townsend, A.J.; de Lange, P.J.; Duffy, C.A.J.; Miskelly, C.M.; Molloy, J.;
  Norton, D.A. 2008. *New Zealand Threat Classification System manual.*
  Department of Conservation, Wellington.

## Text to post

Paste this as a new section on Module talk:Conservation status:

```wikitext
== Add remaining NZTCS categories (Coloniser, Migrant, Vagrant, Introduced and Naturalised) ==

{{Edit template-protected|Module:Conservation status|answered=no}}
<code>p.NZTCS</code> currently has no codes for four categories that the [[New Zealand Threat Classification System]] assigns in every DOC report: '''Coloniser''', '''Migrant''' and '''Vagrant''' (the "Non-resident Native" group) and '''Introduced and Naturalised'''. They are defined in the current NZTCS manual (Rolfe et al. 2022, §5) and described at [[New Zealand Threat Classification System#Other categories]]. The manual lists taxa in these categories without assessing their threat status, so for those taxa the category is the NZTCS status of record. In the 2025 Lepidoptera assessment alone, 13 of 507 taxa fall into them, and at the moment there is no way to record that status in a Speciesbox without getting ''Invalid status''.

Please add these four branches to <code>p.NZTCS</code>, after the <code>DD</code> branch and before the 2002 categories. They are text-only (no badge), since they are not threat assessments, much like IUCN <code>NE</code> and <code>NA</code>:

<syntaxhighlight lang="lua">
   -- Non-resident Native (CO, MI, VA) and Introduced and Naturalised (IN).
   -- Not assessed for threat under the NZTCS, so no badge.
   elseif status == "CO" or status == "co" then
    	output = "[[New Zealand Threat Classification System#Other categories|Coloniser]]"
   elseif status == "MI" or status == "mi" then
    	output = "[[New Zealand Threat Classification System#Other categories|Migrant]]"
   elseif status == "VA" or status == "va" then
    	output = "[[New Zealand Threat Classification System#Other categories|Vagrant]]"
   elseif status == "IN" or status == "in" then
    	output = "[[New Zealand Threat Classification System#Other categories|Introduced and Naturalised]]"
</syntaxhighlight>

NZTCS has no official short codes for these, so <code>CO</code>, <code>MI</code>, <code>VA</code> and <code>IN</code> are new; none collides with an existing NZTCS code. Note that the sandbox is currently behind the live module (it lacks TSPA), so it would need syncing first. I'm happy to update [[Wikipedia:Conservation status]] and the Speciesbox documentation once this is in. ~~~~
```

## After it's accepted

1. Move the four entries from `PENDING_WIKIPEDIA_CODES` to `STATUS_CODES` in
   `src/nztcs_wiki_bot/status_map.py`, using whatever codes were finally
   adopted.
2. Add them to `WIKIPEDIA_NZTCS_CODES` in `tests/unit/test_status_map.py`.
3. Update `docs/nztcs-status-codes.md` and this file's status line.
