"""
JAZYK — Podnet nad rámec § 44 (jazyk).

Minority teaching language is NOT one of the nine § 44 conditions. It is therefore
NEVER part of the semafor and NEVER uses code P-d. When a district's assigned
school teaches only in a minority language while the surrounding pupils' nearest
school teaches in SK (or vice-versa), that is a real geometric statement worth
surfacing — but explicitly as a "podnet nad rámec § 44 (jazyk)", outside the legal
verdict.

Value:
  SIGNAL        = assigned school teaches in a minority language code
                  (anything other than SK/SLOVE/NULL).
  NO_SIGNAL     = school teaches in Slovak — DECISIVELY evaluated, "bez
                  jazykového podnetu — vyučovanie v slovenčine".
  NOT_EVALUATED = teaching language genuinely unknown (real data only). In DEMO
                  mode JAZYK is ALWAYS decisively evaluated (NO_SIGNAL / SIGNAL),
                  never the literal NOT_EVALUATED.

condition_code = 'JAZYK' (deliberately NOT in LEGAL/INDICATOR/SIGNAL groups, so
compose_color ignores it entirely — JAZYK never enters the semafor regardless of
value; it is rendered "mimo semaforu").
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.demo_inputs import DEMO_COMPLETENESS, DEMO_CONFIDENCE, get_demo_input
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

# Codes that count as "majority / Slovak" teaching language (no minority podnet).
_MAJORITY_LANGS = {"SK", "SLOVE", "SLOVAK", "SLOVENSKY"}

_METHODOLOGY = {
    "rule": "jazyk-podnet-mimo-44",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Vyučovací jazyk pridelenej školy. Menšinový jazyk je podnet NAD RÁMEC § 44 "
        "— nie je to zákonná podmienka a nevstupuje do semaforu. Nepoužíva sa kód P-d."
    ),
    "data_source": "schools.teaching_language (WFS q9)",
    "law_ref": "mimo § 44 (jazykové práva menšín — iný právny režim)",
    "never_claims": "porušenie § 44; jazyk nie je § 44 podmienka",
    "panel": "podnet nad rámec § 44 — NIKDY v zákonnom semafore",
}


def check_lang(district: dict) -> Verdict:
    district_id = district["id"]
    school_id = district.get("school_id")
    school_name = district.get("school_name", "")

    # DEMO MODE: jazyk podnet driven by demo input (minority code → SIGNAL).
    demo = get_demo_input(district_id)
    if demo is not None:
        dlang = (demo.get("jazyk_language") or "").strip().upper() or None
        if dlang and dlang not in _MAJORITY_LANGS:
            return Verdict(
                district_id=district_id,
                condition_code="JAZYK",
                value=V.SIGNAL,
                confidence=DEMO_CONFIDENCE,
                data_completeness=DEMO_COMPLETENESS,
                provenance={"source": "DEMO — vyučovací jazyk (ukážkové dáta)",
                            "teaching_language": dlang, "scope": "mimo § 44", "demo": True},
                methodology=_METHODOLOGY,
                evidence_text=(
                    f"PODNET NAD RÁMEC § 44 (jazyk) [DEMO]: pridelená škola {school_name} "
                    f"vyučuje v menšinovom jazyku ({dlang}). Žiaci, ktorí potrebujú výučbu "
                    "v slovenčine, musia dochádzať do školy v inom obvode. Toto NIE je "
                    "§ 44 podmienka a NEVSTUPUJE do semaforu (nepoužíva sa kód P-d). "
                    "Ukážkové dáta."
                ),
                is_mock=True,
            )
        # DEMO present, no minority language → decisively evaluated NO_SIGNAL.
        # The demo must never show the literal NOT_EVALUATED for JAZYK (owner
        # requirement): Slovak-teaching districts read "bez jazykového podnetu".
        return Verdict(
            district_id=district_id,
            condition_code="JAZYK",
            value=V.NO_SIGNAL,
            confidence=DEMO_CONFIDENCE,
            data_completeness=DEMO_COMPLETENESS,
            provenance={"source": "DEMO — vyučovací jazyk (ukážkové dáta)",
                        "teaching_language": "SK", "scope": "mimo § 44", "demo": True},
            methodology=_METHODOLOGY,
            evidence_text=(
                f"Bez jazykového podnetu: pridelená škola {school_name} vyučuje v "
                "slovenčine. Jazyk je mimo § 44 — nevstupuje do semaforu. Ukážkové dáta."
            ),
            is_mock=True,
        )

    lang = None
    is_demo = False
    if school_id:
        rows = query_sql(f"""
            SELECT teaching_language,
                   COALESCE((metadata ->> 'lang_is_demo')::boolean, FALSE) AS lang_is_demo
            FROM skolske_obvody.schools WHERE id = '{school_id}'
        """)
        if rows:
            lang = (rows[0].get("teaching_language") or "").strip().upper() or None
            is_demo = bool(rows[0].get("lang_is_demo"))

    base_prov = {
        "source": "schools.teaching_language (WFS q9)",
        "school_name": school_name,
        "teaching_language": lang,
        "lang_is_demo": is_demo,
        "scope": "mimo § 44",
    }

    if lang is None or lang in _MAJORITY_LANGS:
        return Verdict(
            district_id=district_id,
            condition_code="JAZYK",
            value=V.NOT_EVALUATED,
            confidence=0.0,
            data_completeness=0.0,
            provenance=base_prov,
            methodology=_METHODOLOGY,
            evidence_text=(
                f"Bez podnetu: škola {school_name} vyučuje v slovenčine ({lang or 'neznáme'}). "
                "Jazyk je mimo § 44 — nevstupuje do zákonného stavu."
            ),
        )

    return Verdict(
        district_id=district_id,
        condition_code="JAZYK",
        value=V.SIGNAL,
        confidence=0.5,
        data_completeness=0.5,
        provenance=base_prov,
        methodology=_METHODOLOGY,
        evidence_text=(
            f"PODNET NAD RÁMEC § 44 (jazyk): pridelená škola {school_name} vyučuje v "
            f"menšinovom jazyku ({lang}). Žiaci, ktorí potrebujú výučbu v slovenčine, "
            "musia dochádzať do školy v inom obvode. Toto NIE je § 44 podmienka a "
            "NEVSTUPUJE do semaforu (nepoužíva sa kód P-d)."
            + (" [DEMO]" if is_demo else "")
        ),
        is_mock=is_demo,
    )
