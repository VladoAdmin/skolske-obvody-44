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
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
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
    "law_ref": "§44 ods. 1 a 7",
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

    lang_filter = (
        f"AND d2.teaching_language = '{teaching_language}'"
        if teaching_language
        else "AND d2.teaching_language IS NULL"
    )

    # Same full address (normalised street + house number) assigned to THIS
    # district AND to another district of the same school_type + teaching_language.
    overlap_rows = query_sql(f"""
        SELECT
            d2.id   AS partner_id,
            d2.name AS partner_name,
            count(DISTINCT lower(trim(h1.street)) || '|' || trim(h1.house_number)) AS shared_addresses
        FROM skolske_obvody.house_geocodes h1
        JOIN skolske_obvody.house_geocodes h2
          ON h1.id <> h2.id
         AND h1.district_id <> h2.district_id
         AND lower(trim(h1.street)) = lower(trim(h2.street))
         AND trim(h1.house_number)  = trim(h2.house_number)
         AND h1.house_number IS NOT NULL
        JOIN skolske_obvody.districts d2
          ON d2.id = h2.district_id
         AND d2.school_type = '{school_type}'
         {lang_filter}
         AND d2.municipality_id = '{municipality_id}'
        WHERE h1.district_id = '{district_id}'
        GROUP BY d2.id, d2.name
    """)

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
    return Verdict(
        district_id=district_id,
        condition_code="S2",
        value=V.FAIL,
        confidence=0.7,
        data_completeness=0.7,
        provenance={
            "source": "house_geocodes (address→district assignment)",
            "school_type": school_type,
            "teaching_language": teaching_language,
            "overlap_partners": partners,
            "shared_addresses": total_shared,
            "method": "same-full-address-in-2+-districts",
        },
        methodology=_METHODOLOGY,
        evidence_text=(
            f"FAIL: {total_shared} adries (ulica + číslo) nárokujú dva obvody "
            f"rovnakého typu naraz — s {', '.join(partners)} (§ 44 ods. 1 a 7). "
            "Jedna adresa musí patriť práve jednému obvodu."
        ),
    )
