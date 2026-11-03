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

NZTCS also has four categories that aren't threat rankings but are assigned in
every DOC report:

| NZTCS category | Group | Meaning |
|---|---|---|
| Coloniser | Non-resident Native | Arrived without human help and reproduces successfully |
| Migrant | Non-resident Native | Visits New Zealand as part of its life cycle |
| Vagrant | Non-resident Native | Rare; arrived on its own and doesn't breed successfully |
| Introduced and Naturalised | — | Deliberately or accidentally introduced to New Zealand |

They're defined in the NZTCS manual (Townsend et al. 2008), are still assigned
in current reports, and are already described in the
[NZTCS article's "Other categories" section](https://en.wikipedia.org/wiki/New_Zealand_Threat_Classification_System#Other_categories).
In the 2025 Lepidoptera report alone, 13 of 507 taxa are in them (6 Vagrant,
5 Introduced and Naturalised, 2 Coloniser). Without module support, editors
can't record those statuses at all.

## Proposed change

Add four codes to `p.NZTCS`, rendered as text linked to the NZTCS article, with
no badge image (these aren't positions on a threat scale, the same way IUCN
`NE` and `NA` are text-only):

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
+   -- These aren't threat rankings, so they have no badge.
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
*Hypolimnas bolina* (Vagrant), *Pieris rapae* (Introduced and Naturalised).

## Text to post

Paste this as a new section on Module talk:Conservation status:

```wikitext
== Add remaining NZTCS categories (Coloniser, Migrant, Vagrant, Introduced and Naturalised) ==

{{Edit template-protected|Module:Conservation status|answered=no}}
<code>p.NZTCS</code> currently has no codes for four categories that the [[New Zealand Threat Classification System]] assigns in every DOC report: '''Coloniser''', '''Migrant''' and '''Vagrant''' (the "Non-resident Native" group) and '''Introduced and Naturalised'''. They are defined in the NZTCS manual (Townsend et al. 2008) and described at [[New Zealand Threat Classification System#Other categories]]. In the 2025 Lepidoptera assessment alone, 13 of 507 taxa fall into them, and at the moment there is no way to record that status in a Speciesbox without getting ''Invalid status''.

Please add these four branches to <code>p.NZTCS</code>, after the <code>DD</code> branch and before the 2002 categories. They are text-only (no badge), since they are not threat rankings, much like IUCN <code>NE</code> and <code>NA</code>:

<syntaxhighlight lang="lua">
   -- Non-resident Native (CO, MI, VA) and Introduced and Naturalised (IN).
   -- These aren't threat rankings, so they have no badge.
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
