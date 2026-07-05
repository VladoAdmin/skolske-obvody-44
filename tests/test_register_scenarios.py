"""
Step 2 Sprint 3 Checkpoint 4 — findings register scenario-type filter.

WHY these matter:
  * The register's scenario filter (app/findings/scenarios.ts) is a TS mirror
    of SCENARIO_FIELDS in engine/demo_inputs.py — the engine's single source
    of truth for the six demo scenario families. The GUI must never invent or
    re-derive scenario→condition mappings (engine is the sole source of
    truth), so these tests fail if the mirror drifts: a scenario added,
    removed, or remapped on either side without the other breaks CI.
  * The filter narrows on condition_code values the engine emits. If the TS
    map listed a condition the engine never writes, the filter would silently
    show an empty register for that scenario — the mapping check catches that
    by construction.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.demo_inputs import SCENARIO_FIELDS

SCENARIOS_TS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "app", "findings", "scenarios.ts"
)

# Matches each entry of SCENARIO_TYPES_SK, e.g.
#   address_overlap: { label: 'Prekryv adries', conditions: ['S2'], order: 6 }
_TS_ENTRY_RE = re.compile(
    r"(\w+):\s*\{\s*"
    r"label:\s*'([^']+)',\s*"
    r"conditions:\s*\[([^\]]*)\],\s*"
    r"order:\s*(\d+)",
    re.DOTALL,
)


def _parse_ts_scenarios() -> dict[str, dict]:
    with open(SCENARIOS_TS_PATH, encoding="utf-8") as fh:
        source = fh.read()
    entries = {}
    for key, label, conditions_raw, order in _TS_ENTRY_RE.findall(source):
        conditions = [c.strip().strip("'\"") for c in conditions_raw.split(",") if c.strip()]
        entries[key] = {"label": label, "conditions": conditions, "order": int(order)}
    return entries


def _engine_conditions(scenario: str) -> set[str]:
    # engine/demo_inputs.py writes multi-condition scenarios as 'Pa/Pb'.
    return set(SCENARIO_FIELDS[scenario]["condition"].split("/"))


def test_ts_mirror_covers_exactly_the_engine_scenarios():
    ts = _parse_ts_scenarios()
    assert set(ts) == set(SCENARIO_FIELDS), (
        "app/findings/scenarios.ts must mirror engine/demo_inputs.py "
        f"SCENARIO_FIELDS exactly; TS={sorted(ts)} engine={sorted(SCENARIO_FIELDS)}"
    )


def test_ts_condition_codes_match_engine_per_scenario():
    ts = _parse_ts_scenarios()
    for scenario, entry in ts.items():
        assert set(entry["conditions"]) == _engine_conditions(scenario), (
            f"{scenario}: TS filter conditions {entry['conditions']} != "
            f"engine condition '{SCENARIO_FIELDS[scenario]['condition']}'"
        )


def test_ts_labels_are_present_and_orders_unique():
    ts = _parse_ts_scenarios()
    assert all(entry["label"].strip() for entry in ts.values()), "empty SK label"
    orders = [entry["order"] for entry in ts.values()]
    assert len(orders) == len(set(orders)), "duplicate sort order in SCENARIO_TYPES_SK"
