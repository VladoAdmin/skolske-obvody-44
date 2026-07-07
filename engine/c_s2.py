"""
Š2 — Neprekrývanie (Non-overlap): the SAME full address (ulica + súpisné/orientačné
číslo) must not be assigned to two districts of the same school_type +
teaching_language.

ADDRESS-BASED (streets-pivot, 2026-06-28):
  The previous polygon ST_Intersects(d1.geom, d2.geom) test is retired. With the
  map rendering districts as their STREETS (not polygons), a street shared by two
  districts (crossing/boundary street) is normal and NOT a violation. The only
  structural overlap that can ever be a § 44 finding is the SAME FULL ADDRESS
  (street + house number) claimed by two districts of the same type — one address
  must belong to exactly one obvod.

METHODOLOGY §Š2:
  PASS = no full address (street + house number) appears in 2+ same-type districts.
  FAIL = at least one full address assigned to 2+ same-type/same-language districts.
  INCOMPLETE = missing school_type/teaching_language attribute.

Source of address→district assignment: skolske_obvody.house_geocodes (one row per
VZN-derived house address, district_id = the district the VZN assigns it to).

DEMO/LIVE SEPARATION (Step 2 Sprint 1):
  house_geocodes rows can carry is_demo=TRUE (an explicit demo address, e.g. the
  "same full address in 2 districts" demo scenario — see
  scripts/sql/0041_demo_s2_address_overlap.sql). Those rows must NEVER affect a
  live/prod Š2 verdict just by existing in the table. This checker EXCLUDES
  is_demo=TRUE rows from the overlap query unless demo_mode_enabled() is TRUE —
  by construction, not by convention, so turning demo mode off makes Š2 blind to
  demo addresses regardless of what is seeded. When a demo row IS the cause of an
  overlap, the resulting Verdict is flagged is_mock=True.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.demo_inputs import DEMO_COMPLETENESS, DEMO_CONFIDENCE, demo_mode_enabled
from engine.evidence_trail import build_s2_trail
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

_METHODOLOGY = {
    "rule": "Š2-address-overlap",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Address-level non-overlap test: the same full address (street + house "
        "number) must not be assigned to two districts of the same school_type "
        "AND teaching_language. Shared/boundary STREETS are NOT a violation — only "
        "a duplicated full address is."
    ),
    "law_ref": "§ 44 ods. 1 a 7",
    "never_claims": "a shared boundary street = an administrative overlap",
}


def check_s2(district: dict, all_districts: list[dict], municipality_id: str) -> Verdict:
    district_id = district["id"]
    school_type = district.get("school_type")
    teaching_language = district.get("teaching_language")

    if not school_type:
        return Verdict(
            district_id=district_id,
            condition_code="S2",
            value=V.INCOMPLETE,
            confidence=0.0,
            data_completeness=0.0,
            provenance={"source": "districts table", "reason": "missing school_type attribute"},
            methodology=_METHODOLOGY,
            evidence_text="NEÚPLNÉ: chýba atribút school_type — test neprebehol.",
        )

    # TRUST BOUNDARY (Sprint 1 review): school_type/teaching_language are
    # f-string interpolated directly into the SQL below, not parameterised.
    # This is internal-trusted-only — both values originate from the
    # `districts` table (ingested from WFS/VZN, never end-user input), not
    # from any HTTP/user-facing input path. Not refactored this sprint per
    # the review's explicit scope (documentation only, no behaviour change).
    lang_filter = (
        f"AND d2.teaching_language = '{teaching_language}'"
        if teaching_language
        else "AND d2.teaching_language IS NULL"
    )

    # Demo addresses (house_geocodes.is_demo=TRUE) only enter this query when
    # demo mode is on — otherwise a demo row can NEVER produce a live/prod Š2
    # FAIL, by construction (see module docstring).
    demo_on = demo_mode_enabled()
    demo_exclusion = "" if demo_on else "AND h1.is_demo IS NOT TRUE AND h2.is_demo IS NOT TRUE"

    # Same full address (normalised street + house number) assigned to THIS
    # district AND to another district of the same school_type + teaching_language.
    overlap_rows = query_sql(f"""
        SELECT
            d2.id   AS partner_id,
            d2.name AS partner_name,
            count(DISTINCT lower(trim(h1.street)) || '|' || trim(h1.house_number)) AS shared_addresses,
            (array_agg(DISTINCT trim(h1.street) || ' ' || trim(h1.house_number)))[1:5] AS example_addresses,
            bool_or(h1.is_demo OR h2.is_demo) AS any_demo
        FROM skolske_obvody.house_geocodes h1
        JOIN skolske_obvody.house_geocodes h2
          ON h1.id <> h2.id
         AND h1.district_id <> h2.district_id
         AND lower(trim(h1.street)) = lower(trim(h2.street))
         AND trim(h1.house_number)  = trim(h2.house_number)
         AND h1.house_number IS NOT NULL
         {demo_exclusion}
        JOIN skolske_obvody.districts d2
          ON d2.id = h2.district_id
         AND d2.school_type = '{school_type}'
         {lang_filter}
         AND d2.municipality_id = '{municipality_id}'
        WHERE h1.district_id = '{district_id}'
        GROUP BY d2.id, d2.name
    """)

    is_mock = bool(overlap_rows) and any(r.get("any_demo") for r in overlap_rows)

    if not overlap_rows:
        return Verdict(
            district_id=district_id,
            condition_code="S2",
            value=V.PASS,
            confidence=0.7,
            data_completeness=0.7,
            provenance={
                "source": "house_geocodes (address→district assignment)",
                "school_type": school_type,
                "teaching_language": teaching_language,
                "method": "same-full-address-in-2+-districts",
            },
            methodology=_METHODOLOGY,
            evidence_text=(
                f"0 adries (ulica + číslo) zdieľaných s iným obvodom typu "
                f"{school_type}/{teaching_language}. Zdieľané hraničné ulice nie sú nález."
            ),
        )

    partners = sorted({r["partner_name"] for r in overlap_rows if r["partner_name"]})
    total_shared = sum(int(r["shared_addresses"] or 0) for r in overlap_rows)
    shared_examples = sorted({
        ex for r in overlap_rows for ex in (r.get("example_addresses") or [])
    })
    demo_suffix = " Ukážkové dáta." if is_mock else ""
    return Verdict(
        district_id=district_id,
        condition_code="S2",
        value=V.FAIL,
        confidence=DEMO_CONFIDENCE if is_mock else 0.7,
        data_completeness=DEMO_COMPLETENESS if is_mock else 0.7,
        provenance={
            "source": "house_geocodes (address→district assignment)",
            "school_type": school_type,
            "teaching_language": teaching_language,
            "overlap_partners": partners,
            "shared_addresses": total_shared,
            "method": "same-full-address-in-2+-districts",
            "demo": is_mock,
            # VLA-15: structured evidence trail (VZN citation, register state,
            # geometry, conclusion) for the street/address-assignment class.
            "evidence_trail": build_s2_trail(district_id, partners, shared_examples),
        },
        methodology=_METHODOLOGY,
        evidence_text=(
            f"FAIL: {total_shared} adries (ulica + číslo) nárokujú dva obvody "
            f"rovnakého typu naraz — s {', '.join(partners)} (§ 44 ods. 1 a 7). "
            f"Jedna adresa musí patriť práve jednému obvodu.{demo_suffix}"
        ),
        is_mock=is_mock,
    )
