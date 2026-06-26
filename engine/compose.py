"""
Semafor composition — per PRD §5 explicit rule.

Inputs: dict of condition_code → Verdict for one district.
Output: {"color": "RED"|"ORANGE"|"GREEN", "reason": str, "details": dict}

Composition rules:
  RED    = any of Š1/Š2/Š3 value == FAIL
  ORANGE = Š1/Š2/Š3 all PASS but some == INCOMPLETE
           OR any of Pa/Pb/Pc/Pd == RISK or INSUFFICIENT_DATA
  GREEN  = all Š1–Š3 == PASS AND no Pa–Pd RISK/INSUFFICIENT_DATA

Gatekeeping:
  - Pe / Pf: ALWAYS analytical-signals sub-panel; NEVER degrade legal semafor.
  - ILUSTR. (Pc, is_illustrative=True): never degrades legal status.
  - PROXY / MOCK flags: never worsen legal status.
  - INSUFFICIENT_DATA for Pa/Pd/Pf: never RED.
  - ILUSTR_NO_DATA: never RED.

Legal status is determined ONLY by Š1–Š3.
Pa–Pd are risk indicators that can push to ORANGE but not RED.
"""

from __future__ import annotations

from engine.constants import Color, V

# Condition codes that determine legal compliance
LEGAL_CONDITIONS = {"S1", "S2", "S3"}
# Condition codes that are risk indicators (can push to ORANGE)
INDICATOR_CONDITIONS = {"Pa", "Pb", "Pc", "Pd"}
# Analytical signal conditions (never affect semafor)
SIGNAL_CONDITIONS = {"Pe", "Pf"}

# Values that cause RED (legal FAIL)
RED_TRIGGERS = {V.FAIL}
# Values that cause ORANGE (in legal conditions: INCOMPLETE; in indicators: RISK or INSUFFICIENT_DATA)
ORANGE_LEGAL_TRIGGERS = {V.INCOMPLETE}
ORANGE_INDICATOR_TRIGGERS = {V.RISK, V.INSUFFICIENT_DATA}


def compose_color(verdicts: dict) -> dict:
    """
    Compose semafor color from a dict of {condition_code: Verdict}.

    Returns:
        {
            "color": "RED" | "ORANGE" | "GREEN",
            "reason": str,
            "legal_status": dict,    # Š1–Š3 breakdown
            "indicator_status": dict, # Pa–Pd breakdown
            "signal_status": dict,    # Pe–Pf (never degrades semafor)
        }
    """
    legal_status = {}
    indicator_status = {}
    signal_status = {}

    for code, v in verdicts.items():
        if code in LEGAL_CONDITIONS:
            legal_status[code] = v.value
        elif code in INDICATOR_CONDITIONS:
            # Illustrative indicators never degrade
            if v.is_illustrative:
                indicator_status[code] = v.value + " [ILUSTR.]"
            else:
                indicator_status[code] = v.value
        elif code in SIGNAL_CONDITIONS:
            signal_status[code] = v.value

    # --- RED check ---
    red_codes = [
        code for code, val in legal_status.items()
        if val in RED_TRIGGERS
    ]
    if red_codes:
        return {
            "color": Color.RED,
            "reason": f"FAIL v zákonných podmienkach: {', '.join(sorted(red_codes))}",
            "legal_status": legal_status,
            "indicator_status": indicator_status,
            "signal_status": signal_status,
        }

    # --- ORANGE check ---
    orange_legal = [
        code for code, val in legal_status.items()
        if val in ORANGE_LEGAL_TRIGGERS
    ]
    # Indicators: only non-illustrative ones count
    orange_indicators = []
    for code, v in verdicts.items():
        if code in INDICATOR_CONDITIONS and not v.is_illustrative:
            if v.value in ORANGE_INDICATOR_TRIGGERS:
                orange_indicators.append(code)

    if orange_legal or orange_indicators:
        parts = []
        if orange_legal:
            parts.append(f"NEÚPLNÉ zákonné podmienky: {', '.join(sorted(orange_legal))}")
        if orange_indicators:
            parts.append(f"Rizikové indikátory: {', '.join(sorted(orange_indicators))}")
        return {
            "color": Color.ORANGE,
            "reason": "; ".join(parts),
            "legal_status": legal_status,
            "indicator_status": indicator_status,
            "signal_status": signal_status,
        }

    # --- GREEN ---
    # All legal conditions PASS, no risky indicators
    return {
        "color": Color.GREEN,
        "reason": "Š1–Š3 PASS, žiadne rizikové indikátory",
        "legal_status": legal_status,
        "indicator_status": indicator_status,
        "signal_status": signal_status,
    }
