# Proposal: render the remaining NZTCS statuses on Wikipedia

**Status:** posted 2026-11-24 as an `{{Edit template-protected}}` request on
[Module talk:Conservation status](https://en.wikipedia.org/wiki/Module_talk:Conservation_status).
Waiting for a template editor to reply. There's nothing more to do until then.

| What | Where |
|---|---|
| The request | [Module talk:Conservation status](https://en.wikipedia.org/wiki/Module_talk:Conservation_status), section "Add remaining NZTCS statuses (Coloniser, Migrant, Vagrant, Introduced and Naturalised, Uncommon)" |
| The proposed module | [Module:Sandbox/Richlitt/Conservation status](https://en.wikipedia.org/wiki/Module:Sandbox/Richlitt/Conservation_status) |
| Diff against the live module | [Special:ComparePages](https://en.wikipedia.org/w/index.php?title=Special:ComparePages&page1=Module%3AConservation+status&page2=Module%3ASandbox%2FRichlitt%2FConservation+status) |
| Test page | [User:Richlitt/Conservation status testcases](https://en.wikipedia.org/wiki/User:Richlitt/Conservation_status_testcases) |

The module is template-editor protected, so a template editor has to make the
change.

## Background

`{{Speciesbox}}` and `{{Taxobox}}` render `status_system = NZTCS` through
`p.NZTCS` in [Module:Conservation status](https://en.wikipedia.org/wiki/Module:Conservation_status).
As of revision 1385652069 (2026-11-14) it accepts `EX`, `NC`, `NE`, `NV`, `NI`,
`D`, `REL`, `NU`, `R`, `NT`, `DD`, and the 2002-era `SD`, `GD`, `SP`, `RR`.
Anything else renders "*Invalid status*" and adds the article to
[Category:Invalid conservation status](https://en.wikipedia.org/wiki/Category:Invalid_conservation_status).

NZTCS also has four categories that every DOC report assigns but that aren't
threat assessments. The current manual (Rolfe et al. 2022, §5, pp. 32–33)
defines them as:

| NZTCS category | Group | Definition (Rolfe et al. 2022) |
|---|---|---|
| Coloniser | Non-resident Native | "Taxa that would trigger one of the Threatened categories because of their small population sizes but have arrived in New Zealand without direct or indirect help from humans and have been successfully reproducing in the wild for fewer than 50 years" |
| Migrant | Non-resident Native | "Taxa that predictably and cyclically visit New Zealand as part of their normal life cycle (with a minimum of 15 individuals being known or presumed to visit each year) but do not breed here" |
| Vagrant | Non-resident Native | "Taxa that are found unexpectedly in New Zealand and whose presence in this region is naturally transitory or migratory taxa that have fewer than 15 individuals being known or presumed to visit each year" |
| Introduced and Naturalised | — | "Taxa that have become naturalised in New Zealand after being deliberately or accidentally introduced by human agency" (a self-sustaining wild population over at least three generations, spread beyond the initial site) |

The manual is explicit that taxa in these categories are *listed* by category
but "their conservation statuses are not assessed under the NZTCS" (§3, p. 15).
So the category is the NZTCS status of record for these taxa, but it isn't a
position on the threat scale.

DOC reports have used the 2022 manual since July 2024; the categories carry
over from the 2008 manual (Townsend et al. 2008), and Wikipedia's
[NZTCS article](https://en.wikipedia.org/wiki/New_Zealand_Threat_Classification_System#Other_categories)
lists them under "Other categories". In the 2025 Lepidoptera report alone, 13
of 507 taxa are in them (6 Vagrant, 5 Introduced and Naturalised, 2 Coloniser).
Without module support, editors can't record those statuses at all.

The 2022 manual also changed one threat status. "At Risk – Naturally Uncommon"
was renamed "At Risk – Uncommon" and widened: it now covers all stable or
increasing taxa that meet the At Risk population-size criteria, "regardless of
whether their state is natural or unnatural", with the population state
recorded separately (Rolfe et al. 2022, §2.2, p. 10). The state is part of each
assessment's criteria code: `UNCn…` is natural, `UNCu…` unnatural, and `UNCx…`
unknown, which the manual treats as unnatural (§3.2.2, p. 17). The module's `NU`
renders "Naturally Uncommon", which is right for `UNCn` taxa but wrong for the
rest. In the 2025 Lepidoptera report, 71 of the 84 Uncommon taxa are `UNCu` or
`UNCx`, and 4 have no criteria code.

## Proposed change

Add five codes to `p.NZTCS`, each rendered as a plain-text label:

| Code | Renders as | For |
|---|---|---|
| `CO` | Coloniser | Non-resident Native |
| `MI` | Migrant | Non-resident Native |
| `VA` | Vagrant | Non-resident Native |
| `IN` | Introduced and Naturalised | Introduced and Naturalised |
| `U` | Uncommon | At Risk – Uncommon, where the population state isn't natural. `NU` stays as it is for Naturally Uncommon. |

NZTCS doesn't define short codes for any of these, so the codes are new. None
collides with an existing NZTCS code or alias. `p._main` upper-cases the status
before calling `p.NZTCS`, so lowercase input (`co`, `u`) works without
separate checks; the existing lowercase checks in `p.NZTCS` never match.

### Why no badges or links

Every existing NZTCS code except the 2002 ones has a "Status 2019 NZTCS" badge
on Commons, but there are none for these five, so they can't look exactly like
the others. Plain text follows the module's own precedent:

- IUCN `NE` (Not evaluated) and `NR` (Not recognized) are text-only, because
  they aren't positions on the scale. They're the closest match to the four
  non-threat categories.
- Four systems (QLDNCA, NSWBCA, CITES, TSPA) have no badges at all.
- No system uses a blank badge (Commons has a `Status 2019 NZTCS blank.svg`)
  for categories outside its scale.

`U` is a real At Risk category, so it should eventually get a badge. Someone
would have to draw one; it can be added later without changing the code.

The labels aren't links, matching the other NZTCS labels. The
"(NZ TCS)" that the module appends after every NZTCS status already links to
the NZTCS article.

### Diff against the live module

```diff
@@ -556,6 +556,22 @@
     	output = p.addImage("Status 2019 NZTCS NT.svg", "Not Threatened" ) .. "Not Threatened" 
    elseif status == "DD" or status == "dd" then
     	output = p.addImage("Status 2019 NZTCS DD.svg", "Data Deficient" ) .. "Data Deficient" 
+
+   -- Non-resident Native (Coloniser, Migrant, Vagrant) and Introduced and Naturalised:
+   -- listed by the NZTCS but not assessed for threat (manual 2022, §5). No badge,
+   -- like IUCN NE and NR.
+   elseif status == "CO" then
+    	output = "Coloniser"
+   elseif status == "MI" then
+    	output = "Migrant"
+   elseif status == "VA" then
+    	output = "Vagrant"
+   elseif status == "IN" then
+    	output = "Introduced and Naturalised"
+   -- At Risk – Uncommon (manual 2022) where the population state isn't natural;
+   -- natural ones keep NU. No badge exists on Commons yet.
+   elseif status == "U" then
+    	output = "Uncommon"
    
    --  Older categories (version 2002): SD,GD,SP,RR
    elseif status == "SD"  then
```

### Where the change lives

The proposed module is a personal copy,
[Module:Sandbox/Richlitt/Conservation status](https://en.wikipedia.org/wiki/Module:Sandbox/Richlitt/Conservation_status),
rather than the shared `Module:Conservation status/sandbox`. That shared
sandbox is out of date: it lacks the TSPA system, still says "Data Deficit",
and has an older `addImage`. The personal copy is the live module at revision
1385652069 plus the diff above, so the request asks a template editor to copy
the whole page over the live module.

**If the live module is edited before the request is handled**, that whole-page
copy would revert the other edit. In that case, rebuild the personal copy from
the new live source, re-apply the diff, and reply on the request to say so.

## Test cases

`{{Speciesbox}}` and `{{Taxobox}}` pass NZTCS codes straight through
`{{Taxobox/species}}` to the module's `status` entry point, so no template
change is needed.

[User:Richlitt/Conservation status testcases](https://en.wikipedia.org/wiki/User:Richlitt/Conservation_status_testcases)
has two parts:

1. **How it looks in a species infobox.** The conservation-status box for real
   taxa from the 2025 Lepidoptera report, live and proposed side by side:
   *Danaus petilia* (Coloniser), *Hypolimnas bolina* (Vagrant), *Pieris rapae*
   (Introduced and Naturalised), *"Schiffermuelleria" orthophanes* (Uncommon,
   `UNCu2l`), a generic Migrant (the report has none), and *Aenetus virescens*
   (pūriri moth, Not Threatened) as a control.
2. **Every NZTCS code.** A table of all codes plus a made-up one. Only the five
   new codes differ: live shows *Invalid status*, proposed shows the label.

Before posting, the proposed module was also run locally in Lua against the
live one, with stubs for the MediaWiki functions it calls: 165 cases, covering
every existing code in six systems (unchanged), the new codes in upper, lower
and padded form, and the new codes in other systems (still invalid).

## Out of scope: qualifiers

NZTCS qualifiers (`CD`, `DPT`, `RR` and so on) aren't part of this request.
Wikipedia doesn't show them in the infobox; editors write them in the
article's "Conservation status" section. Three of them (`RR`, `Sp`, `Rel`)
also share codes with old statuses in the module. Generating that article
text is tracked as possible future work in
[issue #8](https://github.com/RichardLitt/nztcs-assessments/issues/8).

## Text as posted

Posted on 2026-11-24 as a new section on Module talk:Conservation status:

```wikitext
== Add remaining NZTCS statuses (Coloniser, Migrant, Vagrant, Introduced and Naturalised, Uncommon) ==

{{Edit template-protected|Module:Conservation status|answered=no}}
<code>p.NZTCS</code> currently has no codes for four categories that the [[New Zealand Threat Classification System]] assigns in every DOC report: '''Coloniser''', '''Migrant''' and '''Vagrant''' (the "Non-resident Native" group) and '''Introduced and Naturalised'''. They are defined in the current NZTCS manual (Rolfe et al. 2022, §5) and described at [[New Zealand Threat Classification System#Other categories]]. The manual lists taxa in these categories without assessing their threat status, so for those taxa the category is the NZTCS status of record. In the 2025 Lepidoptera assessment alone, 13 of 507 taxa fall into them, and at the moment there is no way to record that status in a Speciesbox without getting ''Invalid status''.

The 2022 manual also renamed '''At Risk – Naturally Uncommon''' to '''At Risk – Uncommon''' and widened it to cover small stable populations "regardless of whether their state is natural or unnatural" (Rolfe et al. 2022, §2.2, p. 10); the state is recorded in the criteria code (<code>UNCn</code> natural, <code>UNCu</code> unnatural, <code>UNCx</code> unknown). <code>NU</code> renders "Naturally Uncommon", which is wrong for most Uncommon taxa: 71 of 84 in the 2025 Lepidoptera report are not natural. So I'd also like to add <code>U</code> for "Uncommon", keeping <code>NU</code> for taxa whose state is natural.

'''The change is ready to copy''' from [[Module:Sandbox/Richlitt/Conservation status]], which is the live module plus five new branches in <code>p.NZTCS</code>, after <code>DD</code> and before the 2002 categories ([https://en.wikipedia.org/w/index.php?title=Special:ComparePages&page1=Module%3AConservation+status&page2=Module%3ASandbox%2FRichlitt%2FConservation+status diff against the live module]). All five are plain-text labels with no badge. The four non-threat categories follow IUCN <code>NE</code> and <code>NR</code>, which are also text-only because they aren't positions on the scale; <code>U</code> is text-only because there is no Uncommon badge on Commons yet. [[User:Richlitt/Conservation status testcases]] shows them in infobox form for real taxa, plus every NZTCS code side by side: the five new ones render, and all existing ones are unchanged. To apply it, a template editor can copy the whole of my sandbox page over the live module. (The sandbox and test-case links in the box above go to the shared [[Module:Conservation status/sandbox]], which is out of date and doesn't contain this change; please use the links in this paragraph instead.)

NZTCS has no official short codes for these, so <code>CO</code>, <code>MI</code>, <code>VA</code>, <code>IN</code> and <code>U</code> are new; none collides with an existing NZTCS code, and since <code>_main</code> upper-cases the status, lowercase works too. If a template editor would prefer different codes, I'm happy to change them. Once this is in, I'll update [[Wikipedia:Conservation status]] and the Speciesbox documentation. ~~~~
```

## After it's accepted

1. Move the entries from `PENDING_WIKIPEDIA_CODES` to `STATUS_CODES` in
   `src/nztcs_wiki_bot/status_map.py`, using whatever codes were finally
   adopted. For Uncommon, change `status_map.code_for()` to return the new code
   instead of `None` when the state isn't natural.
2. Add them to `WIKIPEDIA_NZTCS_CODES` in `tests/unit/test_status_map.py`.
3. Update `docs/nztcs-status-codes.md` and this file's status line.
4. Update [Wikipedia:Conservation status](https://en.wikipedia.org/wiki/Wikipedia:Conservation_status)
   and the Speciesbox documentation, as the request promised.

If the request is declined or changed, record the outcome in the status line
and adjust `PENDING_WIKIPEDIA_CODES` to match.

## References

- Rolfe, J.; Hitchmough, R.; Michel, P.; Makan, T.; Cooper, J.A.; de Lange, P.J.;
  Townsend, C.A.J.; Miskelly, C.M.; Molloy, J. 2022. *New Zealand Threat
  Classification System manual 2022. Part 1: Assessments.* Department of
  Conservation, Wellington.
  [DOC page](https://www.doc.govt.nz/about-us/science-publications/conservation-publications/nz-threat-classification-system/nz-threat-classification-system-manual-2022/)
- Townsend, A.J.; de Lange, P.J.; Duffy, C.A.J.; Miskelly, C.M.; Molloy, J.;
  Norton, D.A. 2008. *New Zealand Threat Classification System manual.*
  Department of Conservation, Wellington.
