# Evidence-less district parts — absorb report

Vlado QA backlog, bod 7.

## RESOLUTION (applied): re-run the existing area-keyed sliver pass

Bod-7's slivers persisted only because `ingest/absorb_sliver_islands.py` (area
key: part < 0.05 km² AND < 2% of district total) was never re-run after the
street-line rebuild (`645383b`) regenerated `geom`. Re-running it against the
current geom:

- **38 micro-slivers absorbed**, every one < 0.05 km² (max 0.0359 km²); **no
  substantial body touched** — none of the 9 km²-scale parts (Československej
  20.52, Kúpeľná 10.72/8.39, Lesnícka 7.69, Sibírska 3.44/1.35, …) appear in the
  absorb list.
- **Mirka Nešpora: 4 parts → 2 parts.** Its two evidence-less micro-slivers
  (0.0046 km²/Gorazdova, 0.0004 km²/Koceľova) are gone; the two remaining parts
  are substantial real VZN bodies (1.55 km² with 11 streets/1 house, 0.71 km²
  with 3 streets/1 house) and stay as review flags. Its <2% guard did NOT exclude
  the slivers — Mirka is large enough that both sit well under 2%.
- Safety (the pass's own gates): overlap pairs **0**, total area **70.3870 km²**
  = Prešov boundary (drift 0.000000). Self-backup in `geom_island_backup`.
- `flag_multipart_districts.py` re-run afterwards: **8** multi-part districts now
  flagged (down from pre-absorption), Mirka Nešpora = 2 parts / 1 review flag.

So bod-7 is fixed by the already-Vlado-accepted area pass; the evidence-keyed pass
below was NOT applied. Its analysis is retained because it documents why a naive
"zero evidence" rule is unsafe (the house-only lens catches real km²-scale bodies)
— useful context for any future refinement of the sliver heuristic.

---

## Evidence-keyed pass (`absorb_evidenceless_parts.py`) — NOT applied

## Outcome: NOTHING ABSORBED — premise does not hold under the canonical join

The pass was written to absorb MultiPolygon parts that carry **zero address
evidence** into the adjacent district they share the longest border with. Under
the evidence join the codebase already uses (`build_street_districts.ABSORB_SQL`):

    evidence(part) = (# street_geocodes points of the part's district within it)
                   + (# valid house_geocodes of the part's district within it)

**0 parts are evidence-less.** Production `geom` was NOT mutated.

## Why bod-7's two Mirka Nešpora slivers are NOT evidence-less

| district | idx | area km² | street_geocodes in part | valid houses in part |
|---|---:|---:|---:|---:|
| Mirka Nešpora | 0 | 0.00461 | 1 (Gorazdova) | 0 |
| Mirka Nešpora | 1 | 0.00037 | 1 (Koceľova) | 0 |

Each micro-sliver contains one `street_geocodes` fallback POINT (the synthetic
centroid used for a VZN street with no OSM centerline). Under the canonical join
that counts as evidence (= 1), which is exactly why `build_street_districts.py`'s
own `absorb_unsupported` pass did not absorb them. They have **0 houses** but
**not** 0 streets.

## The house-only lens is unsafe (refused by the anomaly guard)

The only join under which those slivers read as zero is **house_geocodes only**.
Applying that lens flags **29** parts as "evidence-less" — including substantial,
real VZN bodies that must never be auto-merged:

| district | idx | area km² | street_geocodes | houses |
|---|---:|---:|---:|---:|
| Základná škola, Československej... | 0 | 20.51567 | 47 | 0 |
| Základná škola, Kúpeľná č. 2 | 0 | 10.71698 | 82 | 0 |
| Základná škola, Kúpeľná č. 2 | 3 | 8.39352 | 21 | 0 |
| Základná škola, Lesnícka č. 1 | 0 | 7.69366 | 34 | 0 |
| Základná škola, Sibírska č. 4 | 0 | 3.44462 | 30 | 0 |
| Základná škola s mat. šk. | 2 | 1.60049 | 11 | 0 |
| Základná škola, Sibírska č. 4 | 1 | 1.34882 | 15 | 0 |
| Základná škola, Šmeralova | 22 | 1.33215 | 7 | 0 |
| Základná škola, Lesnícka č. 1 | 1 | 0.63222 | 5 | 0 |
| ...(20 more micro-fragments < 0.5 km²) | | | | |

These km²-scale parts carry dozens of VZN `street_geocodes` points; they are the
exact substantial splits that `flag_multipart_districts.py` keeps as review
anomalies (Kúpeľná's 8.6 km² body, Sibírska's 1.5/1.1, etc.). They look "empty"
only because their addresses failed to geocode into `house_geocodes` — a geocode
**coverage gap**, not absence of an address basis. Merging them would silently
destroy real VZN district bodies.

The script enforces an anomaly guard (`ABSORB_MAX_KM2 = 0.10`): a candidate part
larger than the ceiling is refused and the run aborts without writing, per the
project rule "only force-merge parts that carry no evidence; never merge parts
that carry real addresses".

## Conclusion

Bod-7's two Mirka Nešpora micro-slivers (0.0046 / 0.0004 km²) are real
micro-fragments with no houses but with a VZN street geocode each. They cannot be
cleaned by a generic "zero evidence" rule without also catching the city's largest
legitimate bodies. Two defensible follow-ups, neither applied here (both need
Vlado's call on the VZN-fidelity tradeoff):

1. Treat a lone `street_geocodes` fallback POINT inside a sub-`SLIVER_MAX_KM2`
   fragment as non-evidence (area-bounded), so the micro-slivers absorb while the
   km²-scale bodies stay — i.e. extend `absorb_sliver_islands.py`, not this pass.
2. Fix the upstream `house_geocodes` coverage gap so the large bodies stop reading
   as house-less, which also makes the canonical join fully trustworthy.

## Live-state safety confirmation

- `geom` untouched: districts total area = 70.3870 km² = Prešov boundary; overlaps = 0.
- Mirka Nešpora still has 4 parts (unchanged).
- `geom_evidenceless_backup` column added but 0 rows populated (dry-run path skips
  the geom backup/write).
