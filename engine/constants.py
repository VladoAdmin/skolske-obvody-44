"""
Engine constants — condition codes, value enums, versioning.
"""

import subprocess

# Condition codes
CONDITION_CODES = ["S1", "S2", "S3", "Pa", "Pb", "Pc", "Pd", "Pe", "Pf"]

# Value enum (canonical strings written to DB)
class V:
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    RISK = "RISK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    SIGNAL = "SIGNAL"
    NO_SIGNAL = "NO_SIGNAL"
    NOT_EVALUATED = "NOT_EVALUATED"
    ILUSTR_NO_DATA = "ILUSTR_NO_DATA"
    ILUSTRATIVE_AVAILABLE = "ILUSTRATIVE_AVAILABLE"

# Semafor colors
class Color:
    RED = "RED"
    ORANGE = "ORANGE"
    GREEN = "GREEN"

# Version info
METHODOLOGY_VERSION = "0.1"

def _get_engine_version() -> str:
    try:
        short = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return f"{short}+voronoi"
    except Exception:
        return "unknown+voronoi"

ENGINE_VERSION = _get_engine_version()

# Dataset version — sourced from latest ingest run
DATASET_VERSION = "sprint-k+presov-2026-06-25"

# Thresholds (METHODOLOGY §P-b)
PB_PASS_DISTANCE_M = 2000     # 2 km for ZS 1. stupeň
PB_PASS_DURATION_S = 1800     # 30 min
PB_RISK_DISTANCE_M = 4000     # 4 km

# P-e: MRK area share triggering SIGNAL
PE_MRK_AREA_THRESHOLD = 0.10  # 10% of district area

# Presov municipality ID (live DB)
PRESOV_MUN_ID = "e74cc008-e6e3-4b4d-abae-0c62d240ba01"
