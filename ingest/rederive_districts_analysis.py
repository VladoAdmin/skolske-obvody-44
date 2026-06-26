"""
STEP 3 — analyse & re-derive school districts on the CLEAN address data.

Read-only / diagnosis only. Does NOT mutate districts, geometry, address tables
or the legal Š1–Š3 verdict views. Produces docs/district-rederivation-analysis.md.

(a) ASSIGN every clean address (skolske_obvody.register_adries_clean) to a
    school district via the VZN street->district mapping (vzn_street_ranges),
    matched on the normalised street name. Reports:
      - per-district authoritative habitable-address + distinct-street counts,
      - coverage gaps: clean streets that match NO VZN district,
      - VZN streets with zero clean register addresses.

(b) GEOMETRIC VALIDATION on the 748 geocoded points (register_geocode):
    for each geocoded address compute which district POLYGON (districts.geom)
    actually ST_Covers its point, and compare to the district its VZN street
    assigns. Reports MISMATCHES (street says A, coordinate falls in B / none),
    quantified per district. These are the § 44-relevant geometry/assignment
    inconsistencies.

(c) Honest Š1 note (see the report): this register is BUILDINGS/addresses, not
    pupil-to-school records, so it does NOT resolve Š1's pupil requirement.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/rederive_districts_analysis.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import query_sql

REPORT_PATH = Path(__file__).parent.parent / "docs" / "district-rederivation-analysis.md"

PRESOV = "(SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')"

# Same normalisation family as build_register_adries_clean / build_street_districts.
NORM = lambda col: f"""
  btrim(regexp_replace(
    regexp_replace(
      regexp_replace(
        lower(unaccent(
          replace(replace({col}, 'Arm. gen.', 'Armádneho generála'), 'č.', '')
        )),
        '^ulica\\s+|\\s+ulica$', '', 'g'),
      '[.]', ' ', 'g'),
    '\\s+', ' ', 'g'))
"""

# Distinct (district_id, normalised VZN street) for Prešov.
VZN_CTE = f"""
vzn AS (
  SELECT DISTINCT vr.district_id, {NORM('vr.street')} AS nname
  FROM skolske_obvody.vzn_street_ranges vr
  JOIN skolske_obvody.districts d ON d.id = vr.district_id
  WHERE d.municipality_id = {PRESOV}
)
"""


# ---------------------------------------------------------------------------
# (a) VZN street -> district assignment on the CLEAN register
# ---------------------------------------------------------------------------
def assignment_per_district() -> list[dict]:
    """Per-district authoritative habitable-address + distinct-street counts.

    A clean street assigned by the VZN to >1 district is counted for EACH such
    district (the per-house range split is what geometry resolves; for the count
    signal both districts legitimately list the street)."""
    sql = f"""
WITH {VZN_CTE},
clean AS (
  SELECT ulica_norm AS nname, ulica
  FROM skolske_obvody.register_adries_clean
),
joined AS (
  SELECT v.district_id, c.nname, c.ulica
  FROM vzn v
  JOIN clean c ON c.nname = v.nname
)
SELECT d.name,
       count(*)                        AS habitable_addresses,
       count(DISTINCT j.nname)         AS distinct_streets
FROM joined j
JOIN skolske_obvody.districts d ON d.id = j.district_id
GROUP BY d.name
ORDER BY habitable_addresses DESC
"""
    return query_sql(sql)


def assignment_totals() -> dict:
    """Clean rows assigned to >=1 district vs unassigned (coverage gap rows)."""
    sql = f"""
WITH {VZN_CTE},
clean AS (SELECT id, ulica_norm AS nname FROM skolske_obvody.register_adries_clean)
SELECT
  count(*)                                                   AS clean_total,
  count(*) FILTER (WHERE v.nname IS NOT NULL)                AS assigned,
  count(*) FILTER (WHERE v.nname IS NULL)                    AS unassigned
FROM clean c
LEFT JOIN (SELECT DISTINCT nname FROM vzn) v ON v.nname = c.nname
"""
    return query_sql(sql)[0]


def coverage_gap_streets() -> list[dict]:
    """Clean streets that match NO VZN district (with their address counts)."""
    sql = f"""
WITH {VZN_CTE},
gap AS (
  SELECT c.ulica_norm AS nname,
         min(c.ulica)  AS sample_spelling,
         count(*)      AS addresses
  FROM skolske_obvody.register_adries_clean c
  WHERE NOT EXISTS (SELECT 1 FROM vzn v WHERE v.nname = c.ulica_norm)
  GROUP BY c.ulica_norm
)
SELECT sample_spelling, nname, addresses FROM gap
ORDER BY addresses DESC, nname
"""
    return query_sql(sql)


def vzn_streets_without_addresses() -> list[dict]:
    """VZN streets with zero clean register addresses."""
    sql = f"""
WITH {VZN_CTE},
clean AS (SELECT DISTINCT ulica_norm AS nname FROM skolske_obvody.register_adries_clean)
SELECT d.name AS district, v.nname AS vzn_street_norm
FROM vzn v
JOIN skolske_obvody.districts d ON d.id = v.district_id
WHERE NOT EXISTS (SELECT 1 FROM clean c WHERE c.nname = v.nname)
ORDER BY d.name, v.nname
"""
    return query_sql(sql)


# ---------------------------------------------------------------------------
# (b) Geometric validation on the 748 geocoded points
# ---------------------------------------------------------------------------
def geometric_validation() -> dict:
    """For each geocoded address: VZN-street district(s) vs the polygon that
    ST_Covers its point. Classify each point as MATCH / MISMATCH / NO_VZN /
    NO_POLYGON.

    A geocoded street that the VZN assigns to several districts is a MATCH if the
    containing polygon is ANY of those VZN districts (the split is legitimate and
    the point lands in one of the assigned districts)."""
    sql = f"""
WITH {VZN_CTE},
pts AS (
  SELECT g.adresa, g.ulica, g.geom, {NORM('g.ulica')} AS nname
  FROM skolske_obvody.register_geocode g
  WHERE g.geom IS NOT NULL
),
-- polygon that actually covers each point (district id), if any
in_poly AS (
  SELECT p.adresa, p.nname, p.geom,
    (SELECT d.id FROM skolske_obvody.districts d
       WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
         AND public.ST_Covers(d.geom, p.geom)
       LIMIT 1) AS poly_did
  FROM pts p
),
-- set of VZN districts for the point's street
vzn_for_pt AS (
  SELECT ip.adresa,
         array_agg(v.district_id) AS vzn_dids
  FROM in_poly ip
  JOIN vzn v ON v.nname = ip.nname
  GROUP BY ip.adresa
)
SELECT
  ip.adresa, ip.nname, ip.poly_did, vp.vzn_dids
FROM in_poly ip
LEFT JOIN vzn_for_pt vp ON vp.adresa = ip.adresa
"""
    rows = query_sql(sql)
    out = {"total": len(rows), "match": 0, "mismatch": 0, "no_vzn": 0,
           "no_polygon": 0, "mismatch_rows": []}
    for r in rows:
        vzn_dids = r.get("vzn_dids")
        poly = r.get("poly_did")
        if not vzn_dids:
            out["no_vzn"] += 1
            continue
        if poly is None:
            out["no_polygon"] += 1
            out["mismatch_rows"].append({**r, "kind": "NO_POLYGON"})
            continue
        if poly in vzn_dids:
            out["match"] += 1
        else:
            out["mismatch"] += 1
            out["mismatch_rows"].append({**r, "kind": "MISMATCH"})
    return out


def mismatch_detail() -> list[dict]:
    """Per geocoded mismatch: address, street, VZN district name(s), polygon
    district name (or NONE). Quantified per containing polygon district."""
    sql = f"""
WITH {VZN_CTE},
pts AS (
  SELECT g.adresa, g.ulica, g.geom, {NORM('g.ulica')} AS nname
  FROM skolske_obvody.register_geocode g
  WHERE g.geom IS NOT NULL
),
in_poly AS (
  SELECT p.adresa, p.ulica, p.nname, p.geom,
    (SELECT d.id FROM skolske_obvody.districts d
       WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
         AND public.ST_Covers(d.geom, p.geom)
       LIMIT 1) AS poly_did
  FROM pts p
),
vzn_for_pt AS (
  SELECT ip.adresa, array_agg(DISTINCT vd.name ORDER BY vd.name) AS vzn_names,
         array_agg(DISTINCT v.district_id) AS vzn_dids
  FROM in_poly ip
  JOIN vzn v ON v.nname = ip.nname
  JOIN skolske_obvody.districts vd ON vd.id = v.district_id
  GROUP BY ip.adresa
)
SELECT ip.adresa, ip.ulica,
       vp.vzn_names,
       pd.name AS poly_name
FROM in_poly ip
JOIN vzn_for_pt vp ON vp.adresa = ip.adresa
LEFT JOIN skolske_obvody.districts pd ON pd.id = ip.poly_did
WHERE ip.poly_did IS NULL
   OR NOT (ip.poly_did = ANY (vp.vzn_dids))
ORDER BY poly_name NULLS FIRST, ip.ulica, ip.adresa
"""
    return query_sql(sql)


def mismatch_per_district() -> list[dict]:
    """Count of mismatched points whose coordinate falls in each district's
    polygon (the polygon that 'wins' the point against its VZN street)."""
    sql = f"""
WITH {VZN_CTE},
pts AS (
  SELECT g.adresa, g.geom, {NORM('g.ulica')} AS nname
  FROM skolske_obvody.register_geocode g WHERE g.geom IS NOT NULL
),
in_poly AS (
  SELECT p.adresa, p.geom, p.nname,
    (SELECT d.id FROM skolske_obvody.districts d
       WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
         AND public.ST_Covers(d.geom, p.geom) LIMIT 1) AS poly_did
  FROM pts p
),
vzn_for_pt AS (
  SELECT ip.adresa, array_agg(DISTINCT v.district_id) AS vzn_dids
  FROM in_poly ip JOIN vzn v ON v.nname = ip.nname GROUP BY ip.adresa
),
mism AS (
  SELECT ip.poly_did
  FROM in_poly ip JOIN vzn_for_pt vp ON vp.adresa = ip.adresa
  WHERE ip.poly_did IS NOT NULL AND NOT (ip.poly_did = ANY (vp.vzn_dids))
)
SELECT COALESCE(d.name, '(no polygon)') AS poly_name, count(*) AS mismatches
FROM mism m LEFT JOIN skolske_obvody.districts d ON d.id = m.poly_did
GROUP BY d.name ORDER BY mismatches DESC
"""
    return query_sql(sql)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def write_report(per_district, totals, gaps, vzn_empty, geo, mism_rows,
                 mism_per_dist, clean_summary) -> None:
    L = []
    a = L.append
    a("# District re-derivation analysis (clean authoritative address data)")
    a("")
    a(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
    a("")
    a("Diagnosis only. No district geometry, address table, or legal Š1–Š3 "
      "verdict was changed by this analysis. Source of truth for the street→"
      "district assignment is `skolske_obvody.vzn_street_ranges`; the "
      "authoritative address inventory is the City-of-Prešov "
      "**Register adries a stavieb** (`skolske_obvody.register_adries`), "
      "cleaned into `skolske_obvody.register_adries_clean` (Step 2).")
    a("")

    # ---- Step 2 clean summary -------------------------------------------
    a("## 1. Clean address set (Step 2)")
    a("")
    a("| Metric | Value |")
    a("|---|---:|")
    a(f"| Input register rows | {clean_summary['input']} |")
    a(f"| Dropped — not habitable (`obyvatelna≠true`) | {clean_summary['not_habitable']} |")
    a(f"| Dropped — withdrawn (`vyradena≠false`) | {clean_summary['withdrawn']} |")
    a(f"| Dropped — empty street after normalisation | {clean_summary['empty_street']} |")
    a(f"| Dropped — exact duplicates on (street_norm, súpisné, orientačné) | {clean_summary['dup_dropped']} |")
    a(f"| **Kept (clean canonical)** | **{clean_summary['kept']}** |")
    a(f"| Distinct clean streets | {clean_summary['distinct_streets']} |")
    a("")
    a("Stored as `skolske_obvody.register_adries_clean` (+ public read view "
      "`public.so_register_adries_clean`). Street normalisation is identical to "
      "the geometry build's `NORM` (lower + unaccent + strip leading `Ulica ` + "
      "drop `č.`/dots + expand `Arm. gen.` + collapse whitespace).")
    a("")

    # ---- (a) assignment --------------------------------------------------
    a("## 2. (a) VZN street → district assignment on clean data")
    a("")
    a(f"- Clean addresses total: **{totals['clean_total']}**")
    a(f"- Assigned to ≥1 district via a VZN street: **{totals['assigned']}** "
      f"({100*int(totals['assigned'])/int(totals['clean_total']):.1f}%)")
    a(f"- **Coverage gap** (clean address whose street matches NO VZN district): "
      f"**{totals['unassigned']}**")
    a("")
    a("A clean street the VZN assigns to several districts (range split) is "
      "counted for each such district, so per-district counts can sum above the "
      "assigned total. The per-house split is what geocoding resolves; for the "
      "count signal each district legitimately lists the street.")
    a("")
    a("### Per-district authoritative counts (from the register, not Google guesses)")
    a("")
    a("| District | Habitable addresses | Distinct streets |")
    a("|---|---:|---:|")
    for r in per_district:
        a(f"| {r['name']} | {r['habitable_addresses']} | {r['distinct_streets']} |")
    a("")

    a("### Coverage gaps — clean streets matching NO VZN district")
    a("")
    if gaps:
        gap_addr = sum(int(g["addresses"]) for g in gaps)
        a(f"{len(gaps)} distinct clean streets ({gap_addr} addresses) are present "
          "in the authoritative register but are not assigned to any district by "
          "the VZN. These are real § 44 coverage candidates: addresses an "
          "authoritative register lists for which the VZN names no school.")
        a("")
        a("| Sample spelling | Normalised | Addresses |")
        a("|---|---|---:|")
        for g in gaps:
            a(f"| {g['sample_spelling']} | {g['nname']} | {g['addresses']} |")
    else:
        a("_None — every clean street matches at least one VZN district._")
    a("")

    a("### VZN streets with zero clean register addresses")
    a("")
    if vzn_empty:
        a(f"{len(vzn_empty)} VZN street→district assignments have no habitable "
          "clean address in the register. Either the street has no habitable "
          "buildings, or the VZN spelling does not fold to a register spelling "
          "(see the separate `vzn-register-validation-report.md` for the "
          "spelling cross-check).")
        a("")
        a("| District | VZN street (normalised) |")
        a("|---|---|")
        for v in vzn_empty:
            a(f"| {v['district']} | {v['vzn_street_norm']} |")
    else:
        a("_None._")
    a("")

    # ---- (b) geometric validation ---------------------------------------
    a("## 3. (b) Geometric validation (748 geocoded points vs district polygons)")
    a("")
    a("For each geocoded address we compute which district **polygon** "
      "(`districts.geom`) actually `ST_Covers` its real coordinate, and compare "
      "to the district its **VZN street** assigns. A point is a MATCH if the "
      "covering polygon is any of the street's VZN district(s).")
    a("")
    a("| Outcome | Count |")
    a("|---|---:|")
    a(f"| Geocoded points checked | {geo['total']} |")
    a(f"| MATCH (coordinate in a VZN-assigned district polygon) | {geo['match']} |")
    a(f"| **MISMATCH (street says A, coordinate falls in polygon B)** | **{geo['mismatch']}** |")
    a(f"| Coordinate falls in NO district polygon | {geo['no_polygon']} |")
    a(f"| Street not in any VZN district (no baseline to compare) | {geo['no_vzn']} |")
    a("")
    comparable = geo['match'] + geo['mismatch']
    if comparable:
        a(f"Of {comparable} points that have both a VZN-street district and a "
          f"covering polygon, **{geo['mismatch']} "
          f"({100*geo['mismatch']/comparable:.1f}%) disagree** — the coordinate "
          "lands in a different district's polygon than its VZN street names. "
          "These are the § 44-relevant geometry/assignment inconsistencies.")
    a("")
    a("Caveat on interpretation: the geocodes are a mix of `border_house` "
      "(real per-house coordinates) and `street_anchor` (one representative "
      "point per street). For a street the VZN **splits** across districts by "
      "house-number range (e.g. Sabinovská → Bajkalská/Šmeralova), a real house "
      "coordinate can legitimately fall in a third district's polygon, which "
      "surfaces here as a mismatch. Each mismatch is therefore a place to "
      "**look**, not an automatic error: it flags where the drawn polygon and "
      "the VZN street assignment do not agree on the ground.")
    a("")
    a("### Mismatches per containing polygon district")
    a("")
    if mism_per_dist:
        a("| Polygon the coordinate fell into | Mismatched points |")
        a("|---|---:|")
        for r in mism_per_dist:
            a(f"| {r['poly_name']} | {r['mismatches']} |")
    else:
        a("_No mismatches._")
    a("")
    a("### Mismatch detail (address-level)")
    a("")
    if mism_rows:
        a("| Address | Street | VZN district(s) | Coordinate falls in polygon |")
        a("|---|---|---|---|")
        for r in mism_rows:
            vzn_names = r.get("vzn_names") or []
            if isinstance(vzn_names, str):
                vzn_names = [vzn_names]
            a(f"| {r['adresa']} | {r['ulica']} | "
              f"{'; '.join(vzn_names)} | {r['poly_name'] or '(none)'} |")
    else:
        a("_No mismatches._")
    a("")

    # ---- (c) Š1 honesty --------------------------------------------------
    a("## 4. (c) What this means for Š1 — honest scope")
    a("")
    a("The § 44 methodology's **Š1** is *\"the addresses of all PUPILS fall in "
      "the correct district\"*. This register holds **BUILDINGS / addresses**, "
      "not pupil→school enrolment records. Therefore this analysis **does NOT by "
      "itself resolve Š1's pupil requirement** — we have no pupil data here.")
    a("")
    a("What the clean data DOES provide:")
    a("")
    a("- an **authoritative address inventory** per district (Section 2), "
      "replacing earlier Google-derived guesses with register counts;")
    a("- a **geometric consistency check** of the district derivation "
      "(Section 3): where the VZN-street assignment and the drawn polygon "
      "disagree for a real coordinate.")
    a("")
    a("These are necessary inputs toward Š1, not a discharge of it. The legal "
      "Š1/Š2/Š3 verdicts are **left untouched**; the findings above are reported "
      "so a human can decide whether they change a verdict.")
    a("")

    a("## 5. Artifacts")
    a("")
    a("- `skolske_obvody.register_adries_clean` / `public.so_register_adries_clean` — clean canonical address set (additive).")
    a("- `scripts/sql/0026_register_adries_clean.sql` — schema.")
    a("- `ingest/build_register_adries_clean.py` — Step 2 builder.")
    a("- `ingest/rederive_districts_analysis.py` — Step 3 analysis (this report).")
    a("")

    REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[report] written {REPORT_PATH}")


def clean_summary_from_db() -> dict:
    total = int(query_sql("SELECT count(*) n FROM skolske_obvody.register_adries")[0]["n"])
    drop = query_sql(f"""
      SELECT
        count(*) FILTER (WHERE obyvatelna IS NOT TRUE)                      AS not_habitable,
        count(*) FILTER (WHERE obyvatelna = TRUE AND vyradena IS NOT FALSE) AS withdrawn,
        count(*) FILTER (WHERE obyvatelna = TRUE AND vyradena = FALSE
                            AND {NORM('ulica')} = '')                       AS empty_street
      FROM skolske_obvody.register_adries
    """)[0]
    kept = int(query_sql("SELECT count(*) n FROM skolske_obvody.register_adries_clean")[0]["n"])
    distinct_streets = int(query_sql(
        "SELECT count(DISTINCT ulica_norm) n FROM skolske_obvody.register_adries_clean")[0]["n"])
    eligible = total - int(drop["not_habitable"]) - int(drop["withdrawn"]) - int(drop["empty_street"])
    return {
        "input": total, "not_habitable": int(drop["not_habitable"]),
        "withdrawn": int(drop["withdrawn"]), "empty_street": int(drop["empty_street"]),
        "dup_dropped": eligible - kept, "kept": kept, "distinct_streets": distinct_streets,
    }


def main() -> dict:
    validate_config()
    print("=" * 70)
    print("STEP 3 — re-derive & analyse districts on clean data (diagnosis only)")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    clean_summary = clean_summary_from_db()
    per_district = assignment_per_district()
    totals = assignment_totals()
    gaps = coverage_gap_streets()
    vzn_empty = vzn_streets_without_addresses()
    geo = geometric_validation()
    mism_rows = mismatch_detail()
    mism_per_dist = mismatch_per_district()

    write_report(per_district, totals, gaps, vzn_empty, geo, mism_rows,
                 mism_per_dist, clean_summary)

    print("\nSUMMARY")
    print(f"  clean addresses     = {totals['clean_total']}")
    print(f"  assigned (VZN)      = {totals['assigned']}")
    print(f"  coverage gaps       = {totals['unassigned']}")
    print(f"  gap streets         = {len(gaps)}")
    print(f"  vzn empty streets   = {len(vzn_empty)}")
    print(f"  geocoded checked    = {geo['total']}")
    print(f"  geo MATCH           = {geo['match']}")
    print(f"  geo MISMATCH        = {geo['mismatch']}")
    print(f"  geo NO_POLYGON      = {geo['no_polygon']}")
    print(f"  geo NO_VZN          = {geo['no_vzn']}")
    print(f"Finished: {datetime.now().isoformat()}")
    return {
        "clean_total": int(totals["clean_total"]),
        "assigned": int(totals["assigned"]),
        "coverage_gaps": int(totals["unassigned"]),
        "geo_mismatches": geo["mismatch"],
    }


if __name__ == "__main__":
    main()
