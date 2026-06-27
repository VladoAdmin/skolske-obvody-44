"""
P-f — Demografia detí / kapacita (district demand vs assigned-school capacity).

METHODOLOGY §P-f (labels.ts canonical = "Demografia detí"):
  Compare the number of children/pupils in the district against the assigned
  school's capacity. When demand exceeds capacity, the district is overloaded
  → analytical SIGNAL (preťaženie).

  Demand source (in priority order):
    1. schools.student_count (real enrolment, WFS/EDUZBER) when available,
    2. else NOT evaluated for demand (no per-district REGOB child counts in DB).
  Capacity source: schools.capacity (EDUZBER). Real Prešov rows are currently
  empty; a DEMO INPUT capacity + student_count may be set on a school to make
  overcrowding demonstrable (verdict flagged is_mock when capacity is demo).

  Value (Pf ∈ SIGNAL_CONDITIONS — NEVER affects the legal semafor):
    SIGNAL        = student_count > capacity (preťaženie).
    NO_SIGNAL     = student_count <= capacity (kapacita postačuje).
    NOT_EVALUATED = capacity or demand unavailable.

  law_ref: §44 ods. 8 písm. f) — kapacita školy vs počet detí v obvode.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

_METHODOLOGY = {
    "rule": "Pf-demografia-kapacita",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Počet detí/žiakov v obvode voči kapacite pridelenej školy (EDUZBER). "
        "Preťaženie (žiaci > kapacita) = analytický signál."
    ),
    "demand_source": "schools.student_count (EDUZBER/WFS)",
    "capacity_source": "schools.capacity (EDUZBER)",
    "gap": "per-obvodové počty detí (REGOB) nie sú dostupné; používa sa zápis školy",
    "law_ref": "§44 ods. 8 písm. f)",
    "never_claims": "kapacita/preťaženie ako zákonný verdikt — analytický signál",
    "panel": "analytické signály — NIKDY v zákonnom semafore",
    "gatekeeping": "Pf nikdy nezhoršuje zákonný semafor",
}


def check_pf(district: dict) -> Verdict:
    district_id = district["id"]
    school_id = district.get("school_id")
    school_name = district.get("school_name", "")

    capacity = None
    student_count = None
    is_demo_cap = False
    if school_id:
        rows = query_sql(f"""
            SELECT
                s.capacity,
                s.student_count,
                COALESCE((s.metadata ->> 'pf_capacity_is_demo')::boolean, FALSE) AS cap_is_demo
            FROM skolske_obvody.schools s
            WHERE s.id = '{school_id}'
        """)
        if rows:
            capacity = rows[0].get("capacity")
            student_count = rows[0].get("student_count")
            is_demo_cap = bool(rows[0].get("cap_is_demo"))

    base_prov = {
        "source": "schools.capacity + schools.student_count (EDUZBER)",
        "school_name": school_name,
        "capacity": capacity,
        "student_count": student_count,
        "capacity_is_demo": is_demo_cap,
    }

    if capacity is None or student_count is None:
        return Verdict(
            district_id=district_id,
            condition_code="Pf",
            value=V.NOT_EVALUATED,
            confidence=0.0,
            data_completeness=0.0,
            provenance={
                **base_prov,
                "gap": "kapacita alebo počet žiakov (EDUZBER) nedostupný",
                "action_required": "Import kapacít + zápisu z EDUZBER odblokuje P-f.",
            },
            methodology=_METHODOLOGY,
            evidence_text=(
                "NEVYHODNOTENÉ: kapacita školy alebo počet žiakov (EDUZBER) nie sú dostupné. "
                f"Škola: {school_name}. Analytický signál — nevstupuje do zákonného stavu."
            ),
            is_mock=is_demo_cap,
        )

    capacity = int(capacity)
    student_count = int(student_count)
    util = round(student_count / capacity * 100, 1) if capacity > 0 else 0.0

    if student_count > capacity:
        value = V.SIGNAL
        evidence = (
            f"SIGNÁL preťaženia: zapísaných žiakov {student_count} > kapacita {capacity} "
            f"({util} %). Škola {school_name}. "
            "Analytický signál (demografia/kapacita) — nevstupuje do zákonného stavu."
            + (" [DEMO dáta]" if is_demo_cap else "")
        )
    else:
        value = V.NO_SIGNAL
        evidence = (
            f"BEZ SIGNÁLU: žiakov {student_count} ≤ kapacita {capacity} ({util} %). "
            f"Škola {school_name}. Analytický signál — nevstupuje do zákonného stavu."
            + (" [DEMO dáta]" if is_demo_cap else "")
        )

    return Verdict(
        district_id=district_id,
        condition_code="Pf",
        value=value,
        confidence=0.6 if not is_demo_cap else 0.5,
        data_completeness=0.6,
        provenance={**base_prov, "utilization_pct": util},
        methodology=_METHODOLOGY,
        evidence_text=evidence,
        is_mock=is_demo_cap,
    )
