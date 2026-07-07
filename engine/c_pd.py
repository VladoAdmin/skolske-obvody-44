"""
P-d — Bariéry (cesty, koľaje) — physical barriers on the home→school route.

METHODOLOGY §P-d (labels.ts canonical = "Bariéry (cesty, koľaje)"):
  Methodological safety indicator: the route from home to school should not
  cross a busy road without a crossing, nor a railway without an underpass.

  LEGAL ANCHOR (docs/legal-audit-44.md): NONE. § 44 does not mention route
  barriers anywhere. § 44 ods. 8 písm. d) — previously cited here — is about
  the right to education in the state language or a minority language, NOT
  about barriers. P-d therefore carries NO legal citation: it is a clearly
  labeled non-legal indicator and its FAIL is never presented as a § 44
  violation (owner directive 2026-07-06).

  VLA-20 (client 2026-07-06): the "nedostatočné dáta" state was removed from
  the product. The engine must ALWAYS have a barrier input:
    1. district_demo_inputs.pd_barrier (per-district demo scenario), else
    2. skolske_obvody.barriers — explicit barrier INPUT table. Real railway
       data is unavailable, so it is seeded with a FICTIONAL railway line
       flagged is_demo=TRUE (scripts/sql/0045_demo_barriers.sql). The verdict
       is PASS/FAIL from a geometric intersection with the district, carries
       is_mock=TRUE when derived from demo barrier data, and FAIL as an
       indicator maps to ORANGE — never RED (mock-never-RED invariant).
  INSUFFICIENT_DATA remains only as a last-resort guard for an EMPTY barriers
  table; after 0045 is applied that path is unreachable.

  IMPORTANT: P-d is NOT about language. Minority-language teaching is handled as
  "podnet nad rámec § 44 (jazyk)" via a separate non-§44 finding — never under P-d.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.demo_inputs import DEMO_COMPLETENESS, DEMO_CONFIDENCE, get_demo_input
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

_METHODOLOGY = {
    "rule": "Pd-barriers-input-table",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Fyzické bariéry na trase domov→škola (rušná cesta bez priechodu, "
        "železnica bez podchodu). Vstup: district_demo_inputs.pd_barrier, "
        "inak tabuľka bariér (skolske_obvody.barriers) — geometrický prienik "
        "bariéry s obvodom. Ukážkové (is_demo) bariéry sú vždy označené."
    ),
    "data_available": "skolske_obvody.barriers (línie bariér; demo železnica je fiktívna, is_demo)",
    "law_ref": "bez priamej opory v § 44 — metodický indikátor (zákon bariéry nespomína)",
    "never_claims": (
        "porušenie § 44 (bariéry nie sú v zákone); jazykové právo (to nie je P-d); "
        "reálnosť ukážkovej bariéry (is_demo dáta sú fiktívne)"
    ),
    "gatekeeping": "rizikový indikátor — FAIL môže posunúť na ORANGE, nikdy nie RED",
}


def check_pd(district: dict) -> Verdict:
    district_id = district["id"]
    school_name = district.get("school_name", "")

    # DEMO MODE: complete barrier model → decisive PASS/FAIL (barrier on route).
    demo = get_demo_input(district_id)
    if demo is not None and demo.get("pd_barrier") is not None:
        barrier = bool(demo["pd_barrier"])
        kind = demo.get("pd_barrier_kind") or "rušná cesta bez priechodu"
        if barrier:
            evidence = (
                f"FAIL [DEMO]: pešia trasa domov→škola kríži bariéru ({kind}) bez "
                "bezpečného priechodu/podchodu. Metodický indikátor bezpečnosti trasy "
                "bez priamej opory v § 44 — nejde o porušenie zákona. Ukážkové dáta. "
                "(P-d sa netýka jazyka.)"
            )
        else:
            evidence = (
                "PASS [DEMO]: pešia trasa domov→škola nekríži rušnú cestu bez priechodu "
                "ani železnicu bez podchodu. Metodický indikátor bez priamej opory v § 44. "
                "Ukážkové dáta. (P-d sa netýka jazyka.)"
            )
        return Verdict(
            district_id=district_id,
            condition_code="Pd",
            value=V.FAIL if barrier else V.PASS,
            confidence=DEMO_CONFIDENCE,
            data_completeness=DEMO_COMPLETENESS,
            provenance={"source": "DEMO — bariéry na trase (ukážkový model)", "demo": True,
                        "barrier": barrier, "barrier_kind": kind if barrier else None,
                        "school_name": school_name},
            methodology={**_METHODOLOGY, "rule": "Pd-barriers-demo"},
            evidence_text=evidence,
            is_mock=True,
        )

    # Barrier INPUT table (VLA-20): geometric intersection barrier × district.
    # The table is seeded with a fictional is_demo railway (0045), so this
    # path always has an input — no "nedostatočné dáta" state exists anymore.
    crossing = query_sql(f"""
        SELECT b.kind, b.name, b.is_demo
        FROM skolske_obvody.barriers b
        JOIN skolske_obvody.districts d ON d.id = '{district_id}'
        WHERE public.ST_Intersects(b.geom, d.geom)
    """)
    dataset = query_sql(
        "SELECT count(*) AS n, bool_or(is_demo) AS any_demo FROM skolske_obvody.barriers"
    )
    dataset_n = int(dataset[0]["n"]) if dataset else 0
    dataset_demo = bool(dataset[0]["any_demo"]) if dataset else False

    if dataset_n > 0:
        barrier = len(crossing) > 0
        # Verdict is mock whenever it rests on fabricated barrier data: a demo
        # barrier crossing, or a PASS judged against a demo-only dataset.
        from_demo = any(c.get("is_demo") for c in crossing) if barrier else dataset_demo
        if barrier:
            names = ", ".join(c["name"] for c in crossing)
            evidence = (
                f"FAIL{' [DEMO]' if from_demo else ''}: obvodom prechádza bariéra bez "
                f"bezpečného priechodu/podchodu ({names}). Metodický indikátor bezpečnosti "
                "trasy bez priamej opory v § 44 — nejde o porušenie zákona. "
                f"{'Ukážkové dáta. ' if from_demo else ''}(P-d sa netýka jazyka.)"
            )
        else:
            evidence = (
                f"PASS{' [DEMO]' if from_demo else ''}: žiadna bariéra z tabuľky bariér "
                "nepretína obvod. Metodický indikátor bez priamej opory v § 44. "
                f"{'Ukážkové dáta. ' if from_demo else ''}(P-d sa netýka jazyka.)"
            )
        return Verdict(
            district_id=district_id,
            condition_code="Pd",
            value=V.FAIL if barrier else V.PASS,
            confidence=DEMO_CONFIDENCE if from_demo else 0.8,
            data_completeness=DEMO_COMPLETENESS if from_demo else 0.8,
            provenance={
                "source": "skolske_obvody.barriers (tabuľka bariér; demo bariéry sú fiktívne)",
                "demo": from_demo,
                "barrier": barrier,
                "barriers_crossing": [c["name"] for c in crossing],
                "school_name": school_name,
            },
            methodology=_METHODOLOGY,
            evidence_text=evidence,
            is_mock=from_demo,
        )

    # Last-resort guard: EMPTY barriers table (unreachable once 0045 is applied).
    return Verdict(
        district_id=district_id,
        condition_code="Pd",
        value=V.INSUFFICIENT_DATA,
        confidence=0.0,
        data_completeness=0.0,
        provenance={
            "source": "skolske_obvody.barriers — tabuľka je prázdna",
            "school_name": school_name,
            "action_required": "apply scripts/sql/0045_demo_barriers.sql",
        },
        methodology=_METHODOLOGY,
        evidence_text=(
            "Tabuľka bariér je prázdna — indikátor P-d nemá vstup. "
            "Aplikujte scripts/sql/0045_demo_barriers.sql."
        ),
        is_proxy=True,
    )
