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
from engine.verdict import Verdict
from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql


MUNICIPALITY_ID = PRESOV_MUN_ID


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
) -> None:
    """Write a finding for non-PASS / non-green verdicts."""
    # Severity mapping
    severity_map = {
        "FAIL": "critical",
        "INCOMPLETE": "medium",
        "RISK": "high",
        "INSUFFICIENT_DATA": "low",
        "SIGNAL": "medium",
        "NO_SIGNAL": "info",
        "NOT_EVALUATED": "info",
        "ILUSTR_NO_DATA": "info",
        "ILUSTRATIVE_AVAILABLE": "info",
        "PASS": "info",
    }
    severity = severity_map.get(value, "info")
    # Skip writing findings for PASS and pure info conditions
    if value == "PASS":
        return
    if value in ("NOT_EVALUATED", "ILUSTRATIVE_AVAILABLE") and condition_code in ("Pf", "Pc"):
        severity = "info"

    finding_id = str(uuid.uuid4())
    evid_tag = f"$_fevid_{finding_id[:8]}$"
    tag_sql = f"'{tag}'" if tag else "NULL"

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
    except Exception as ex:
        print(f"  ERROR writing finding: {ex}", file=sys.stderr)


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
    evidence = (
        f"DEMO topológia: ukážkový prekryv obvodov s {', '.join(partners)} "
        f"({round(area)} m²). Reálna geometria Prešova prekryvy NEMÁ (S2 = PASS); "
        "toto je len demonštračná vrstva. Reálna geometria ani priradenie adries "
        "sa nemenia, semafor sa nezhoršuje."
    )
    _write_finding(
        verdict_id, district_id, municipality_id,
        "S2", "FAIL", evidence,
        is_demo=True, tag=f"demo:s2:{district_id[:8]}",
    )
    return True


def run(municipality_id: str = MUNICIPALITY_ID) -> list[dict]:
    """
    Run all checkers for all districts in the given municipality.
    Returns list of per-district result dicts (for report generation).
    """
    validate_config()
    print(f"\n{'='*70}")
    print(f"§ 44 Compliance Engine  v{ENGINE_VERSION}")
    print(f"Municipality: {municipality_id}")
    print(f"{'='*70}\n")

    districts = _fetch_districts(municipality_id)
    print(f"Districts loaded: {len(districts)}\n")

    results = []
    verdicts_written = 0
    findings_written = 0

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

        print(f"  Semafor: {color}")
        print(f"  S1={v_s1.value} S2={v_s2.value} S3={v_s3.value} "
              f"Pa={v_pa.value} Pb={v_pb.value} Pc={v_pc.value} "
              f"Pd={v_pd.value} | Pe={v_pe.value} Pf={v_pf.value}")

        # Write verdicts to DB
        s2_verdict_id = None
        for code, v in district_verdicts.items():
            vid = _write_verdict(v)
            if vid:
                verdicts_written += 1
                if code == "S2":
                    s2_verdict_id = vid
                # JAZYK only surfaces a finding when there is an actual podnet (SIGNAL);
                # the NOT_EVALUATED "no podnet" case must not clutter the register.
                if code == "JAZYK" and v.value != "SIGNAL":
                    continue
                demo_tag = f"demo:{code.lower()}:{district_id[:8]}" if v.is_mock else None
                _write_finding(
                    vid, district_id, municipality_id,
                    code, v.value, v.evidence_text,
                    is_demo=v.is_mock,
                    tag=demo_tag,
                )
                findings_written += 1

        # S2 DEMO topology finding: real geometry is PASS, but if a clearly-flagged
        # demo overlap layer exists for this district, surface it as a DEMO finding
        # (register + map) WITHOUT degrading the real S2 verdict or the semafor.
        if s2_verdict_id and _write_demo_s2_finding(
            s2_verdict_id, district_id, municipality_id
        ):
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

    print(f"\n{'='*70}")
    print(f"Verdicts written: {verdicts_written}")
    print(f"Findings written: {findings_written}")
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
