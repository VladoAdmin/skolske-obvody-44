"""
P-d — Jazykové právo (Language rights indicator).

METHODOLOGY §P-d:
  Without a minority-language nárok dataset, value = INSUFFICIENT_DATA.
  school.teaching_language IS available (WFS q9) — stored informational only.
  municipality.minority_language IS available for some municipalities.

  For Prešov: no minority language in municipality record → P-d = INSUFFICIENT_DATA.
  For municipalities with minority_language set: flag if school teaching_language
  does not match, but still INSUFFICIENT_DATA (Fáza 2 for legal verdict).

  Never a legal verdict. Confidence = 0.0.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict
from ingest.supabase_client import query_sql

_METHODOLOGY = {
    "rule": "Pd-language-insufficient",
    "version": METHODOLOGY_VERSION,
    "description": (
        "Vyučovací jazyk školy (WFS q9) je dostupný. "
        "Jazykový nárok dieťaťa v obvode nie je dostupný (GAP). "
        "Bez dát o jazykovom nároku právny verdikt nie je možný."
    ),
    "gap": "Dataset jazykového nároku (municipality minority language enrollment) not available",
    "law_ref": "§44 ods. 8 písm. d)",
    "never_claims": "porušenie jazykového práva ako zákonný verdikt (Fáza 2)",
    "gatekeeping": "INSUFFICIENT_DATA nikdy nezhoršuje zákonný semafor",
}


def check_pd(district: dict) -> Verdict:
    district_id = district["id"]
    school_id = district.get("school_id")
    municipality_id = district.get("municipality_id")
    teaching_language = district.get("teaching_language")

    # Get school teaching language if school_id available
    school_lang = None
    school_name = ""
    if school_id:
        rows = query_sql(f"""
            SELECT teaching_language, name FROM skolske_obvody.schools
            WHERE id = '{school_id}'
        """)
        if rows:
            school_lang = rows[0].get("teaching_language")
            school_name = rows[0].get("name", "")

    # Get municipality minority language
    mun_minority = None
    if municipality_id:
        rows = query_sql(f"""
            SELECT minority_language FROM skolske_obvody.municipalities
            WHERE id = '{municipality_id}'
        """)
        if rows:
            mun_minority = rows[0].get("minority_language")

    provenance = {
        "source": "schools.teaching_language (WFS q9) + municipalities.minority_language (partial)",
        "school_teaching_language": school_lang,
        "municipality_minority_language": mun_minority,
        "gap": "jazykový nárok dieťaťa v obvode — dataset nedostupný",
        "action_required": "Dataset jazykového nároku (CVTI/RÚŠS) odblokuje Fáza 2.",
    }

    evidence = (
        f"MÁLO DÁT: jazykový nárok dieťaťa v obvode nie je dostupný (GAP). "
        f"Škola {school_name}: vyuč. jazyk = {school_lang or 'N/A'}. "
        f"Obec: menšinový jazyk = {mun_minority or 'žiaden/neznámy'}. "
        "Indikátor nevstupuje do zákonného stavu (Fáza 2)."
    )

    return Verdict(
        district_id=district_id,
        condition_code="Pd",
        value=V.INSUFFICIENT_DATA,
        confidence=0.0,
        data_completeness=0.0,
        provenance=provenance,
        methodology=_METHODOLOGY,
        evidence_text=evidence,
        is_proxy=True,
    )
