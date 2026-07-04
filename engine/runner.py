"""
Engine runner — orchestrates all checkers per district, writes verdicts + findings.

Usage:
    python3 -m engine.runner

Idempotent: re-running same engine_version overwrites verdicts via UPSERT
on (district_id, condition_code, engine_version).

Emits a per-district summary table to stdout.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, ".")

from engine.c_s1 import check_s1
from engine.c_s2 import check_s2
from engine.c_s3 import check_s3
from engine.c_pa import check_pa
from engine.c_pb import check_pb
from engine.c_pc import check_pc
from engine.c_pd import check_pd
from engine.c_pe import check_pe
from engine.c_pf import check_pf
from engine.c_lang import check_lang
from engine.compose import compose_color, LEGAL_CONDITIONS, INDICATOR_CONDITIONS, SIGNAL_CONDITIONS
from engine.constants import ENGINE_VERSION, PRESOV_MUN_ID
from engine.verdict import Verdict, strip_demo_tags
from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql


MUNICIPALITY_ID = PRESOV_MUN_ID

# STREETS PIVOT step 1 (2026-06-28): ship a clean street map with ZERO findings.
# The engine still computes + persists every verdict (SSOT intact), but the
# findings register/panel is wiped pending the step-2 mock-analysis rebuild.
# Set SO_EMIT_FINDINGS=1 to re-enable finding writes (step 2).
import os as _os
EMIT_FINDINGS = _os.environ.get("SO_EMIT_FINDINGS", "0") == "1"


class RedOnlyStructuralError(AssertionError):
    """A district composed to RED for a reason other than an Š1/Š2/Š3 FAIL."""


def _assert_red_only_structural(
    district_name: str, color: str, verdicts: dict
) -> None:
    """
    Hard runtime guard: a RED district MUST be driven by a FAIL in a structural
    legal condition (Š1/Š2/Š3) and nothing else. Mock/indicator/signal conditions
    (Pa–Pf, JAZYK) can never produce a RED district. Fails loudly so a future
    mock or indicator change can never silently colour a district red.
    """
    if color != "RED":
        return
    red_drivers = [
        code for code, v in verdicts.items()
        if code in LEGAL_CONDITIONS and v.value == "FAIL"
    ]
    if not red_drivers:
        raise RedOnlyStructuralError(
            f"{district_name}: RED with no Š1/Š2/Š3 FAIL — a non-structural "
            f"condition drove RED. Verdicts: "
            f"{ {c: v.value for c, v in verdicts.items()} }"
        )
    non_structural_fail_red = [
        code for code, v in verdicts.items()
        if code not in LEGAL_CONDITIONS and v.value == "FAIL"
        and code not in INDICATOR_CONDITIONS  # indicators FAIL → ORANGE, never RED
        and code not in SIGNAL_CONDITIONS     # signals never enter the semafor
    ]
    if non_structural_fail_red:
        raise RedOnlyStructuralError(
            f"{district_name}: RED influenced by non-structural FAIL in "
            f"{non_structural_fail_red} — only Š1/Š2/Š3 may drive RED."
        )


def _fetch_districts(municipality_id: str) -> list[dict]:
    rows = query_sql(f"""
        SELECT
            d.id, d.name, d.school_id, d.school_type, d.teaching_language,
            d.municipality_id, d.geometry_confidence, d.geometry_quality,
            s.name AS school_name,
            s.type AS school_type_check,
            s.student_count,
            s.teaching_language AS school_teaching_language
        FROM skolske_obvody.districts d
        LEFT JOIN skolske_obvody.schools s ON s.id = d.school_id
        WHERE d.municipality_id = '{municipality_id}'
        ORDER BY d.name
    """)
    return rows


def _write_verdict(v: Verdict) -> Optional[str]:
    """Upsert one verdict record, return its ID."""
    verdict_id = str(uuid.uuid4())
    rec = v.to_db_record()
    rec["id"] = verdict_id

    prov_tag = f"$_prov_{verdict_id[:8]}$"
    meth_tag = f"$_meth_{verdict_id[:8]}$"
    refs_tag = f"$_refs_{verdict_id[:8]}$"
    evid_tag = f"$_evid_{verdict_id[:8]}$"

    sql = f"""
INSERT INTO skolske_obvody.verdicts (
    id, district_id, condition_code, value,
    confidence, data_completeness,
    provenance, methodology,
    is_illustrative, is_proxy, is_mock,
    dataset_version, methodology_version, engine_version,
    computed_at, evidence_text, evidence_refs
) VALUES (
    '{rec["id"]}',
    '{rec["district_id"]}',
    '{rec["condition_code"]}',
    '{rec["value"]}',
    {rec["confidence"]},
    {rec["data_completeness"]},
    {prov_tag}{rec["provenance"]}{prov_tag}::jsonb,
    {meth_tag}{rec["methodology"]}{meth_tag}::jsonb,
    {'TRUE' if rec["is_illustrative"] else 'FALSE'},
    {'TRUE' if rec["is_proxy"] else 'FALSE'},
    {'TRUE' if rec["is_mock"] else 'FALSE'},
    '{rec["dataset_version"]}',
    '{rec["methodology_version"]}',
    '{rec["engine_version"]}',
    now(),
    {evid_tag}{rec["evidence_text"]}{evid_tag},
    {refs_tag}{rec["evidence_refs"]}{refs_tag}::jsonb
)
ON CONFLICT (district_id, condition_code, engine_version)
DO UPDATE SET
    value = EXCLUDED.value,
    confidence = EXCLUDED.confidence,
    data_completeness = EXCLUDED.data_completeness,
    provenance = EXCLUDED.provenance,
    methodology = EXCLUDED.methodology,
    is_illustrative = EXCLUDED.is_illustrative,
    is_proxy = EXCLUDED.is_proxy,
    is_mock = EXCLUDED.is_mock,
    computed_at = EXCLUDED.computed_at,
    evidence_text = EXCLUDED.evidence_text,
    evidence_refs = EXCLUDED.evidence_refs
RETURNING id
"""
    try:
        result = exec_sql(sql)
        if result.get("ok"):
            # On UPSERT-update the stored row keeps its original id (not the freshly
            # generated verdict_id), so re-fetch the canonical id to keep the
            # findings.verdict_id FK valid across re-runs.
            row = query_sql(
                f"SELECT id FROM skolske_obvody.verdicts "
                f"WHERE district_id = '{v.district_id}' "
                f"AND condition_code = '{v.condition_code}' "
                f"AND engine_version = '{v.engine_version}' LIMIT 1"
            )
            return row[0]["id"] if row else verdict_id
        else:
            print(f"  WARN: verdict write failed for {v.condition_code}/{v.district_id}: "
                  f"{result.get('message', '')[:120]}", file=sys.stderr)
    except Exception as ex:
        print(f"  ERROR writing verdict {v.condition_code}/{v.district_id}: {ex}", file=sys.stderr)
    return None


def _write_finding(
    verdict_id: str,
    district_id: str,
    municipality_id: str,
    condition_code: str,
    value: str,
    evidence_text: str,
    is_demo: bool = False,
    tag: Optional[str] = None,
) -> bool:
    """Write a finding for non-PASS / non-green verdicts. Returns True if written."""
    # Severity mapping — condition-group aware, so the register mirrors the same
    # discipline as the semafor: a legal FAIL (S1/S2/S3) outranks an indicator
    # FAIL/RISK (Pa-Pd), which in turn outranks an analytical SIGNAL (Pe/Pf) or
    # the non-§44 JAZYK podnet. Without this split every FAIL value (legal or
    # not) mapped to "critical", making an indicator finding look as severe as
    # a structural violation in the findings register.
    if condition_code in LEGAL_CONDITIONS:
        severity_map = {"FAIL": "critical", "INCOMPLETE": "medium"}
    elif condition_code in INDICATOR_CONDITIONS:
        severity_map = {"FAIL": "high", "RISK": "high", "INSUFFICIENT_DATA": "low"}
    elif condition_code in SIGNAL_CONDITIONS:
        severity_map = {"SIGNAL": "medium"}
    elif condition_code == "JAZYK":
        severity_map = {"SIGNAL": "low"}
    else:
        severity_map = {}
    severity = severity_map.get(value, "info")
    # Skip writing findings for clean / no-issue decisive states. The register
    # surfaces problems (FAIL/RISK/SIGNAL/…); PASS and NO_SIGNAL are "all good"
    # and must not clutter it.
    if value in ("PASS", "NO_SIGNAL"):
        return False

    finding_id = str(uuid.uuid4())
    evid_tag = f"$_fevid_{finding_id[:8]}$"
    tag_sql = f"'{tag}'" if tag else "NULL"
    # Strip inline [DEMO]/Ukážkové-dáta tags — the single top banner is the only
    # demo notice (item 7). is_demo column still carries the flag internally.
    evidence_text = strip_demo_tags(evidence_text)

    sql = f"""
INSERT INTO skolske_obvody.findings (
    id, verdict_id, district_id, municipality_id,
    condition_code, severity, status, evidence_text,
    engine_version, is_demo, tag, created_at
) VALUES (
    '{finding_id}',
    '{verdict_id}',
    '{district_id}',
    '{municipality_id}',
    '{condition_code}',
    '{severity}',
    'open',
    {evid_tag}{evidence_text[:500]}{evid_tag},
    '{ENGINE_VERSION}',
    {'TRUE' if is_demo else 'FALSE'},
    {tag_sql},
    now()
)
ON CONFLICT (district_id, condition_code, engine_version)
DO UPDATE SET
    severity = EXCLUDED.severity,
    evidence_text = EXCLUDED.evidence_text,
    is_demo = EXCLUDED.is_demo,
    tag = EXCLUDED.tag,
    created_at = EXCLUDED.created_at
"""
    try:
        result = exec_sql(sql)
        if not result.get("ok"):
            print(f"  WARN: finding write failed: {result.get('message', '')[:120]}", file=sys.stderr)
            return False
        return True
    except Exception as ex:
        print(f"  ERROR writing finding: {ex}", file=sys.stderr)
        return False


def _write_demo_s2_finding(
    verdict_id: str, district_id: str, municipality_id: str
) -> bool:
    """
    Emit a clearly-flagged DEMO S2 (topology) finding when this district is part
    of a demo overlap (district_overlaps.is_demo=TRUE). Real geometry stays PASS;
    this finding is purely illustrative and badged DEMO. Returns True if written.
    """
    rows = query_sql(f"""
        SELECT
            o.overlap_area_m2,
            CASE WHEN o.district_a_id = '{district_id}' THEN db.name ELSE da.name END AS partner_name
        FROM skolske_obvody.district_overlaps o
        LEFT JOIN skolske_obvody.districts da ON da.id = o.district_a_id
        LEFT JOIN skolske_obvody.districts db ON db.id = o.district_b_id
        WHERE o.is_demo = TRUE
          AND ('{district_id}' = o.district_a_id::text OR '{district_id}' = o.district_b_id::text)
    """)
    if not rows:
        return False

    area = sum(float(r["overlap_area_m2"] or 0) for r in rows)
    partners = sorted({r["partner_name"] for r in rows if r["partner_name"]})
    # Address-level wording (item 5): the violation is the SAME full address
    # (street + house number) claimed by two districts — not a shared boundary.
    evidence = (
        f"Prekryv obvodov s {', '.join(partners)}: tie isté adresy "
        f"(ulica + súpisné číslo) na ploche {round(area)} m² nárokujú dva obvody "
        "rovnakého typu naraz (§ 44 ods. 1 a 7). Jedna adresa musí patriť práve "
        "jednému obvodu."
    )
    _write_finding(
        verdict_id, district_id, municipality_id,
        "S2", "FAIL", evidence,
        is_demo=True, tag=f"demo:s2:{district_id[:8]}",
    )
    return True


def _cleanup_stale_findings(
    municipality_id: str,
    engine_version: str,
    keep_keys: set,
) -> int:
    """
    Delete findings for this engine_version + municipality that were NOT written
    in the current run (i.e. their condition flipped to PASS/NO_SIGNAL). Keeps the
    register/map consistent with the single current engine run. Returns delete count.
    """
    rows = query_sql(
        f"SELECT id, district_id, condition_code FROM skolske_obvody.findings "
        f"WHERE municipality_id = '{municipality_id}' "
        f"AND engine_version = '{engine_version}'"
    )
    stale_ids = [
        r["id"] for r in rows
        if (r["district_id"], r["condition_code"]) not in keep_keys
    ]
    if not stale_ids:
        return 0
    id_list = ", ".join(f"'{i}'" for i in stale_ids)
    result = exec_sql(
        f"DELETE FROM skolske_obvody.findings WHERE id IN ({id_list})"
    )
    if not result.get("ok"):
        print(f"  WARN: stale findings cleanup failed: {result.get('message','')[:120]}",
              file=sys.stderr)
        return 0
    return len(stale_ids)


def _purge_other_versions(municipality_id: str, keep_version: str) -> None:
    """
    Keep exactly ONE engine run in the DB. Delete verdicts + findings for this
    municipality whose engine_version != the current one, so a re-run after a code
    change (engine_version is the git short-hash) never leaves a stale parallel run
    that desyncs verdicts vs findings (the tag-unique index also blocks duplicate
    demo findings across versions).
    """
    dist_filter = (
        f"district_id IN (SELECT id FROM skolske_obvody.districts "
        f"WHERE municipality_id = '{municipality_id}')"
    )
    for table in ("findings", "verdicts"):
        res = exec_sql(
            f"DELETE FROM skolske_obvody.{table} "
            f"WHERE {dist_filter} AND engine_version <> '{keep_version}'"
        )
        if not res.get("ok"):
            print(f"  WARN: purge {table} failed: {res.get('message','')[:120]}",
                  file=sys.stderr)


def run(municipality_id: str = MUNICIPALITY_ID) -> list[dict]:
    """
    Run all checkers for all districts in the given municipality.
    Returns list of per-district result dicts (for report generation).
    """
    validate_config()
    from engine.demo_inputs import refresh_demo_mode
    refresh_demo_mode()
    # Findings reference verdicts via FK; purge findings first then verdicts.
    _purge_other_versions(municipality_id, ENGINE_VERSION)
    print(f"\n{'='*70}")
    print(f"§ 44 Compliance Engine  v{ENGINE_VERSION}")
    print(f"Municipality: {municipality_id}")
    print(f"{'='*70}\n")

    districts = _fetch_districts(municipality_id)
    print(f"Districts loaded: {len(districts)}\n")

    results = []
    verdicts_written = 0
    findings_written = 0
    written_finding_keys: set[tuple[str, str]] = set()

    for district in districts:
        district_id = district["id"]
        district_name = district.get("name", district_id)
        print(f"--- {district_name} ---")

        district_verdicts: dict[str, Verdict] = {}

        # Š1
        v_s1 = check_s1(district, districts, municipality_id)
        district_verdicts["S1"] = v_s1

        # Š2
        v_s2 = check_s2(district, districts, municipality_id)
        district_verdicts["S2"] = v_s2

        # Š3
        v_s3 = check_s3(district)
        district_verdicts["S3"] = v_s3

        # P-a
        v_pa = check_pa(district)
        district_verdicts["Pa"] = v_pa

        # P-b
        v_pb = check_pb(district)
        district_verdicts["Pb"] = v_pb
        print(f"  Pb: {v_pb.value} (dist={round(v_pb.provenance.get('median_distance_m', 0))}m)")

        # P-c (illustrative)
        v_pc = check_pc(district)
        district_verdicts["Pc"] = v_pc

        # P-d
        v_pd = check_pd(district)
        district_verdicts["Pd"] = v_pd

        # P-e (analytical signal)
        v_pe = check_pe(district, municipality_id)
        district_verdicts["Pe"] = v_pe

        # P-f (demografia / kapacita signal)
        v_pf = check_pf(district)
        district_verdicts["Pf"] = v_pf

        # JAZYK — podnet nad rámec § 44 (NEVER in semafor; compose_color ignores it).
        v_lang = check_lang(district)
        district_verdicts["JAZYK"] = v_lang

        # Compose semafor (JAZYK is not in any semafor group, so it is ignored)
        composition = compose_color(district_verdicts)
        color = composition["color"]

        # Hard guard: RED may only come from an Š1/Š2/Š3 FAIL. Errors loudly if a
        # mock/indicator/signal condition ever drives a district red.
        _assert_red_only_structural(district_name, color, district_verdicts)

        print(f"  Semafor: {color}")
        print(f"  S1={v_s1.value} S2={v_s2.value} S3={v_s3.value} "
              f"Pa={v_pa.value} Pb={v_pb.value} Pc={v_pc.value} "
              f"Pd={v_pd.value} | Pe={v_pe.value} Pf={v_pf.value}")

        # Write verdicts to DB (always — verdicts are the SSOT). Findings are
        # gated by EMIT_FINDINGS: step 1 ships zero findings (clean street map).
        for code, v in district_verdicts.items():
            vid = _write_verdict(v)
            if vid:
                verdicts_written += 1
                if not EMIT_FINDINGS:
                    continue
                # JAZYK only surfaces a finding when there is an actual podnet (SIGNAL);
                # the NOT_EVALUATED "no podnet" case must not clutter the register.
                if code == "JAZYK" and v.value != "SIGNAL":
                    continue
                demo_tag = f"demo:{code.lower()}:{district_id[:8]}" if v.is_mock else None
                if _write_finding(
                    vid, district_id, municipality_id,
                    code, v.value, v.evidence_text,
                    is_demo=v.is_mock,
                    tag=demo_tag,
                ):
                    written_finding_keys.add((district_id, code))
                    findings_written += 1

        results.append({
            "district_id": district_id,
            "district_name": district_name,
            "S1": v_s1.value,
            "S2": v_s2.value,
            "S3": v_s3.value,
            "Pa": v_pa.value,
            "Pb": v_pb.value,
            "Pb_median_m": v_pb.provenance.get("median_distance_m"),
            "Pc": v_pc.value,
            "Pd": v_pd.value,
            "Pe": v_pe.value,
            "Pf": v_pf.value,
            "color": color,
            "reason": composition["reason"],
        })

    # --- Stale-findings cleanup (idempotency) ---
    # A condition that flips to PASS/NO_SIGNAL on a re-run no longer emits a finding,
    # so its previous finding (same engine_version) would otherwise linger and
    # pollute the register/map. Delete every finding for this engine_version that
    # was NOT (re)written this run, scoped to this municipality.
    stale_deleted = _cleanup_stale_findings(
        municipality_id, ENGINE_VERSION, written_finding_keys
    )

    print(f"\n{'='*70}")
    print(f"Verdicts written: {verdicts_written}")
    print(f"Findings written: {findings_written}")
    print(f"Stale findings deleted: {stale_deleted}")
    print(f"{'='*70}\n")

    return results


if __name__ == "__main__":
    # Load .env.local if present
    import os
    env_path = ".env.local"
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    results = run()

    # Print summary table
    print("\n=== PER-DISTRICT SEMAFOR TABLE ===\n")
    header = (
        f"{'District':<52} {'Color':<8} "
        f"{'S1':<12} {'S2':<8} {'S3':<8} "
        f"{'Pa':<18} {'Pb':<10} {'Pb_m':<7} "
        f"{'Pc':<22} {'Pd':<18} "
        f"{'Pe':<14} {'Pf':<14}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        name = r["district_name"][:50]
        pb_m = str(int(r["Pb_median_m"])) + "m" if r["Pb_median_m"] else "N/A"
        print(
            f"{name:<52} {r['color']:<8} "
            f"{r['S1']:<12} {r['S2']:<8} {r['S3']:<8} "
            f"{r['Pa']:<18} {r['Pb']:<10} {pb_m:<7} "
            f"{r['Pc']:<22} {r['Pd']:<18} "
            f"{r['Pe']:<14} {r['Pf']:<14}"
        )
