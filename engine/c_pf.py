"""
P-f — Inklúzia ŠVVP (Special educational needs — NOT_EVALUATED for demo).

METHODOLOGY §P-f:
  ŠVVP data is a GAP. No dataset available.
  value = NOT_EVALUATED, confidence = 0.0, completeness = 0.0.
  is_mock = True (Fáza 2).
  Never enters legal semafor.
"""

from __future__ import annotations

from engine.constants import V, METHODOLOGY_VERSION
from engine.verdict import Verdict

_METHODOLOGY = {
    "rule": "Pf-svvp-not-evaluated",
    "version": METHODOLOGY_VERSION,
    "description": "ŠVVP (špeciálne výchovno-vzdelávacie potreby) — dáta GAP, Fáza 2.",
    "gap": "CVTI/RÚŠS ŠVVP dataset not available",
    "law_ref": "§44 ods. 8 písm. f)",
    "never_claims": "inklúzia ŠVVP — Fáza 2; ilustračné",
    "panel": "analytické signály",
    "gatekeeping": "NOT_EVALUATED nikdy v zákonnom semafore",
}


def check_pf(district: dict) -> Verdict:
    district_id = district["id"]
    return Verdict(
        district_id=district_id,
        condition_code="Pf",
        value=V.NOT_EVALUATED,
        confidence=0.0,
        data_completeness=0.0,
        provenance={
            "source": "ŠVVP dataset — GAP",
            "note": "Dáta CVTI/RÚŠS o ŠVVP žiakoch nie sú dostupné. Fáza 2.",
        },
        methodology=_METHODOLOGY,
        evidence_text=(
            "NEVYHODNOTENÉ: ŠVVP dáta nie sú dostupné (GAP). "
            "Analytický signál — nevstupuje do zákonného stavu. Fáza 2."
        ),
        is_mock=True,
    )
