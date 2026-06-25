#!/usr/bin/env python3
"""
Dump composition fixtures for Sprint C parity tests.

Usage:
    python3 scripts/dump_composition_fixtures.py > tests/fixtures/composition.json

Outputs a JSON array of fixture cases, each with:
  - district_id: deterministic UUID (uuid5 for synthetic; real UUID from DB for real districts)
  - kind: "real" | "synthetic"
  - name: human name
  - verdicts: {condition_code: value_str}
  - expected: composition color ("RED" | "ORANGE" | "GREEN" | "NONE")

For real Prešov districts: queries $DATABASE_URL for district IDs.
If $DATABASE_URL is not set, uses uuid5(NAMESPACE, name) placeholders and
marks them as "real_placeholder" kind.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any

# Ensure engine package is importable when run from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.constants import CONDITION_CODES, Color

NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")  # constant

# 12 real Prešov district names (from Sprint A engine run)
PRESOV_DISTRICT_NAMES = [
    "Obvod ZŠ Bajkalská",
    "Obvod ZŠ Bajzova",
    "Obvod ZŠ Budovateľská",
    "Obvod ZŠ Curie",
    "Obvod ZŠ Francisciho",
    "Obvod ZŠ Fučíkova",
    "Obvod ZŠ Holého",
    "Obvod ZŠ Kúpeľná",
    "Obvod ZŠ Lesnícka",
    "Obvod ZŠ Obrancov mieru",
    "Obvod ZŠ Prostějovská",
    "Obvod ZŠ Šrobárova",
]


class FakeVerdict:
    """Minimal verdict-like object for compose_color() calls."""

    def __init__(self, value: str, is_illustrative: bool = False):
        self.value = value
        self.is_illustrative = is_illustrative
        self.is_proxy = False
        self.is_mock = False


def _load_real_districts() -> list[dict[str, Any]]:
    """Try to load real district IDs from $DATABASE_URL via psql.
    Returns list of {district_id, name}. Falls back to uuid5 placeholders."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        # Placeholder mode
        return [
            {
                "district_id": str(uuid.uuid5(NAMESPACE, name)),
                "name": name,
                "kind": "real_placeholder",
            }
            for name in PRESOV_DISTRICT_NAMES
        ]

    try:
        import subprocess
        result = subprocess.run(
            [
                "psql",
                db_url,
                "-t",
                "-A",
                "-c",
                """
                SELECT id || '|' || name
                FROM skolske_obvody.districts d
                JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
                WHERE m.slug = 'presov'
                ORDER BY d.name
                """,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        rows = []
        for line in result.stdout.strip().splitlines():
            if "|" in line:
                did, name = line.split("|", 1)
                rows.append({"district_id": did.strip(), "name": name.strip(), "kind": "real"})
        if rows:
            return rows
    except Exception as e:
        print(f"# WARN: could not load real districts from DB: {e}", file=sys.stderr)
        print("# Using uuid5 placeholders", file=sys.stderr)

    return [
        {
            "district_id": str(uuid.uuid5(NAMESPACE, name)),
            "name": name,
            "kind": "real_placeholder",
        }
        for name in PRESOV_DISTRICT_NAMES
    ]


def _fetch_real_verdicts(district_id: str, db_url: str) -> dict[str, str]:
    """Fetch latest verdicts from DB for a real district. Returns {code: value}."""
    try:
        import subprocess
        result = subprocess.run(
            [
                "psql",
                db_url,
                "-t",
                "-A",
                "-c",
                f"""
                SELECT DISTINCT ON (condition_code)
                  condition_code || '|' || value || '|' || is_illustrative::text
                FROM skolske_obvody.verdicts
                WHERE district_id = '{district_id}'
                ORDER BY condition_code, computed_at DESC
                """,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {}
        verdicts = {}
        is_illustrative = {}
        for line in result.stdout.strip().splitlines():
            parts = line.split("|")
            if len(parts) >= 3:
                code, val, illustr = parts[0], parts[1], parts[2]
                verdicts[code] = val
                is_illustrative[code] = illustr.lower() == "true"
        return verdicts, is_illustrative
    except Exception:
        return {}, {}


# Synthetic edge cases — cover all branches in compose.py
SYNTHETIC: list[tuple[str, dict[str, str], dict[str, bool]]] = [
    # name, verdicts, is_illustrative overrides
    ("synth_all_pass", {c: "PASS" for c in CONDITION_CODES}, {}),
    ("synth_s1_fail", {**{c: "PASS" for c in CONDITION_CODES}, "S1": "FAIL"}, {}),
    ("synth_s2_incomplete", {**{c: "PASS" for c in CONDITION_CODES}, "S2": "INCOMPLETE"}, {}),
    ("synth_s3_fail", {**{c: "PASS" for c in CONDITION_CODES}, "S3": "FAIL"}, {}),
    ("synth_pa_fail", {**{c: "PASS" for c in CONDITION_CODES}, "Pa": "FAIL"}, {}),
    ("synth_pc_risk", {**{c: "PASS" for c in CONDITION_CODES}, "Pc": "RISK"}, {}),
    # Illustrative Pc should NOT degrade semafor — stays GREEN
    ("synth_pc_risk_illustrative", {**{c: "PASS" for c in CONDITION_CODES}, "Pc": "RISK"}, {"Pc": True}),
    # Pe/Pf NEVER degrade semafor
    ("synth_pe_signal_only", {**{c: "PASS" for c in CONDITION_CODES}, "Pe": "SIGNAL", "Pf": "NOT_EVALUATED"}, {}),
    ("synth_empty", {}, {}),
    # INSUFFICIENT_DATA in Pa → ORANGE (not RED)
    ("synth_pa_insufficient", {**{c: "PASS" for c in CONDITION_CODES}, "Pa": "INSUFFICIENT_DATA"}, {}),
]


def main() -> None:
    from engine.compose import compose_color

    real_districts = _load_real_districts()
    db_url = os.environ.get("DATABASE_URL", "")

    out = []

    # Real districts
    for d in real_districts:
        verdicts_dict: dict[str, str] = {}
        is_illustrative: dict[str, bool] = {}

        if d["kind"] == "real" and db_url:
            verdicts_dict, is_illustrative = _fetch_real_verdicts(d["district_id"], db_url)

        if not verdicts_dict:
            # No verdicts → NONE
            out.append(
                {
                    "district_id": d["district_id"],
                    "kind": d["kind"],
                    "name": d["name"],
                    "verdicts": {},
                    "is_illustrative": {},
                    "expected": "NONE",
                }
            )
            continue

        fake_verdicts = {
            code: FakeVerdict(val, is_illustrative.get(code, False))
            for code, val in verdicts_dict.items()
        }
        result = compose_color(fake_verdicts)
        out.append(
            {
                "district_id": d["district_id"],
                "kind": d["kind"],
                "name": d["name"],
                "verdicts": verdicts_dict,
                "is_illustrative": {k: v for k, v in is_illustrative.items() if v},
                "expected": result["color"],
            }
        )

    # Synthetic cases
    for name, verdicts, illustr_overrides in SYNTHETIC:
        uid = str(uuid.uuid5(NAMESPACE, name))
        if not verdicts:
            expected = "NONE"
        else:
            fake_verdicts = {
                code: FakeVerdict(val, illustr_overrides.get(code, False))
                for code, val in verdicts.items()
            }
            result = compose_color(fake_verdicts)
            expected = result["color"]

        out.append(
            {
                "district_id": uid,
                "kind": "synthetic",
                "name": name,
                "verdicts": verdicts,
                "is_illustrative": illustr_overrides,
                "expected": expected,
            }
        )

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
