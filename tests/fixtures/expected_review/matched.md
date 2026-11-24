# Matched — proposed NZTCS patches

_2 confident matches. Each entry gives the lines to copy into the article as they are, with the full diff underneath for checking._

<a id="speciesId-1"></a>
## Aenetus virescens → [Pūriri moth](https://en.wikipedia.org/wiki/Pūriri_moth)

- **Common name:** pūriri moth
- **NZTCS status:** `NV`
- **Patch action:** insert

**Add** these lines directly above `| genus = Aenetus`:

```wikitext
| status = NV
| status_system = NZTCS
| status_ref = <ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>
```

<details>
<summary>Full diff</summary>

```diff
--- Pūriri moth (current)
+++ Pūriri moth (proposed)
@@ -1,6 +1,9 @@
 {{Short description|Species of moth endemic to New Zealand}}
 {{Speciesbox
 | image = Aenetus virescens.jpg
+| status = NV
+| status_system = NZTCS
+| status_ref = <ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>
 | genus = Aenetus
 | species = virescens
 | authority = ([[Edward Doubleday|Doubleday]], 1843)
```

</details>

<a id="speciesId-2"></a>
## Powelliphanta augusta → [Powelliphanta augusta](https://en.wikipedia.org/wiki/Powelliphanta_augusta)

- **Common name:** —
- **NZTCS status:** `NE`
- **Patch action:** update

**Replace** this line:

```wikitext
| status = NC
```

**with:**

```wikitext
| status = NE
```

**Replace** this line:

```wikitext
| status_ref = <ref name="oldref">{{cite report |title=old}}</ref>
```

**with:**

```wikitext
| status_ref = <ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>
```

<details>
<summary>Full diff</summary>

```diff
--- Powelliphanta augusta (current)
+++ Powelliphanta augusta (proposed)
@@ -2,9 +2,9 @@
 | genus = Powelliphanta
 | species = augusta
 | authority = Walker, 2003
-| status = NC
+| status = NE
 | status_system = NZTCS
-| status_ref = <ref name="oldref">{{cite report |title=old}}</ref>
+| status_ref = <ref name="NZTCS2025">{{CiteQ|Q139379012}}</ref>
 }}
 '''''Powelliphanta augusta''''' is a species of large land snail.
 
```

</details>

