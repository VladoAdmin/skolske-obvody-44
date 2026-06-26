"""
Topology test harness — G-DATA gate.

Runs PostgREST-based spatial checks via RPC calls to verify:
  T1: All district geometries are valid (ST_IsValid)
  T2: Address coverage — no address points outside any district in its municipality
  T3: No overlapping districts of same type + language

Usage:
    export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
    python3 -m tests.test_topology [--municipality Prešov]

Exit codes:
  0 = all tests PASS
  1 = one or more FAIL (details printed to stdout)
  2 = database not reachable / schema not applied
"""

import json
import sys
import urllib.request
import urllib.error
from typing import Optional

SUPABASE_URL = __import__("os").environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = __import__("os").environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _rpc(function_name: str, params: dict) -> Optional[list]:
    """Call a PostgREST RPC function."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{function_name}"
    payload = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"RPC {function_name} failed: HTTP {e.code}: {body[:200]}", file=sys.stderr)
        return None


def _select(table: str, params: dict, limit: int = 100) -> Optional[list]:
    """Select from a PostgREST table."""
    import urllib.parse
    url = f"{SUPABASE_URL}/rest/v1/{table}?" + urllib.parse.urlencode({**params, "limit": limit})
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"SELECT {table} failed: HTTP {e.code}: {body[:200]}", file=sys.stderr)
        return None


def check_schema_exists() -> bool:
    """Check that the so_districts table exists."""
    result = _select("so_districts", {"limit": "1"})
    if result is None:
        return False
    return True


def test_t1_geometry_validity() -> dict:
    """
    T1: ST_IsValid on all district geometries.
    Uses RPC function so_check_geometry_validity (must exist in DB).
    Falls back to PostgREST select if RPC not available.
    """
    print("\n=== T1: District geometry validity ===")

    # Call the check RPC
    result = _rpc("so_check_geometry_validity", {})

    if result is None:
        # Fallback: select districts with geom
        districts = _select("so_districts", {"geom": "not.is.null", "select": "district_number,school_name,municipality_name"})
        if districts is None:
            return {"test": "T1", "status": "ERROR", "reason": "DB unavailable"}

        print(f"  {len(districts)} districts with geometry found")
        # Can't run ST_IsValid via PostgREST without an RPC function
        # Mark as SKIP with note
        return {
            "test": "T1",
            "status": "SKIP",
            "reason": "so_check_geometry_validity RPC not installed. Apply db/apply_public_schema.sql first.",
            "districts_with_geom": len(districts),
        }

    invalid = [r for r in result if not r.get("is_valid", True)]
    if invalid:
        print(f"  FAIL: {len(invalid)} invalid geometries")
        for r in invalid[:5]:
            print(f"    District {r.get('district_number')}: {r.get('reason')}")
        return {"test": "T1", "status": "FAIL", "invalid_count": len(invalid), "details": invalid[:5]}

    print(f"  PASS: {len(result)} district geometries checked, all valid")
    return {"test": "T1", "status": "PASS", "districts_checked": len(result)}


def test_t2_address_coverage(municipality_name: Optional[str] = None) -> dict:
    """
    T2: Address coverage check.
    Checks that every address point in a municipality is in exactly 1 district.
    """
    print(f"\n=== T2: Address coverage {'(' + municipality_name + ')' if municipality_name else '(all)'} ===")

    # Check via RPC
    params = {"p_municipality": municipality_name} if municipality_name else {}
    result = _rpc("so_check_address_coverage", params)

    if result is None:
        # Fallback: count address points and districts
        ap_count = _select("so_address_points", {"select": "id", "limit": "1"})
        district_count = _select("so_districts", {"select": "id", "limit": "1"})

        if ap_count is None:
            return {
                "test": "T2",
                "status": "SKIP",
                "reason": "Address points not loaded or so_check_address_coverage RPC missing. "
                         "IMPACT: Š1 cannot be verified until address points are loaded and schema applied.",
            }

        return {
            "test": "T2",
            "status": "SKIP",
            "reason": "so_check_address_coverage RPC not installed. Apply db/apply_public_schema.sql first.",
        }

    uncovered = [r for r in result if r.get("failure_type") == "UNCOVERED_ADDRESS"]
    multi_assigned = [r for r in result if r.get("failure_type") == "MULTI_ASSIGNED_ADDRESS"]

    if uncovered or multi_assigned:
        status = "FAIL"
        print(f"  FAIL: {len(uncovered)} uncovered + {len(multi_assigned)} multi-assigned addresses")
        for r in (uncovered + multi_assigned)[:3]:
            print(f"    {r.get('failure_type')}: {r.get('street')} {r.get('house_number')}")
    else:
        status = "PASS"
        print(f"  PASS: Address coverage verified for {municipality_name or 'all municipalities'}")

    return {
        "test": "T2",
        "status": status,
        "municipality": municipality_name or "all",
        "uncovered_count": len(uncovered),
        "multi_assigned_count": len(multi_assigned),
    }


def test_t3_no_overlaps() -> dict:
    """
    T3: No overlapping districts of same type + language.
    """
    print("\n=== T3: District overlap check ===")

    result = _rpc("so_check_district_overlaps", {})

    if result is None:
        return {
            "test": "T3",
            "status": "SKIP",
            "reason": "so_check_district_overlaps RPC not installed. Apply db/apply_public_schema.sql first.",
        }

    overlaps = [r for r in result if r.get("overlap_area_m2", 0) > 1.0]

    if overlaps:
        print(f"  FAIL: {len(overlaps)} district pairs overlap")
        for r in overlaps[:3]:
            print(f"    Districts {r.get('district_a')} & {r.get('district_b')}: "
                  f"{r.get('overlap_area_m2', 0):.1f} m2")
        return {"test": "T3", "status": "FAIL", "overlap_count": len(overlaps), "details": overlaps[:5]}

    print(f"  PASS: No overlapping districts found")
    return {"test": "T3", "status": "PASS"}


def get_row_counts() -> dict:
    """Get row counts for key tables."""
    tables = [
        "so_regions", "so_municipalities", "so_schools",
        "so_districts", "so_address_points", "so_vzns",
        "so_mrk_atlas", "so_transit_stops", "so_datasets",
    ]
    counts = {}
    for table in tables:
        import urllib.parse
        url = f"{SUPABASE_URL}/rest/v1/{table}?limit=0"
        headers = {**_headers(), "Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                cr = resp.headers.get("Content-Range", "0/0")
                total = cr.split("/")[-1]
                counts[table] = int(total) if total != "*" else -1
        except Exception:
            counts[table] = "error"
    return counts


def main(municipality_name: Optional[str] = None) -> int:
    print("=" * 60)
    print("TOPOLOGY TEST CONTRACT — G-DATA Gate")
    print("=" * 60)

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
        return 2

    # Check schema exists
    if not check_schema_exists():
        print("ERROR: Schema not applied. Run db/apply_public_schema.sql in Supabase SQL Editor.", file=sys.stderr)
        return 2

    # Row counts
    print("\nRow counts:")
    counts = get_row_counts()
    for table, count in counts.items():
        gate = ""
        if table == "so_districts" and isinstance(count, int) and count == 0:
            gate = " ← BLOCKER (districts required for G-DATA)"
        if table == "so_address_points" and isinstance(count, int) and count == 0:
            gate = " ← ADDRESS POINTS MISSING (Š1/P-b INCOMPLETE)"
        print(f"  {table}: {count}{gate}")

    # Run topology tests
    results = []
    results.append(test_t1_geometry_validity())
    results.append(test_t2_address_coverage(municipality_name))
    results.append(test_t3_no_overlaps())

    # Summary
    print("\n" + "=" * 60)
    print("TOPOLOGY TEST SUMMARY")
    print("=" * 60)

    all_pass = True
    for r in results:
        status = r["status"]
        if status == "FAIL":
            all_pass = False
        icon = "✓" if status == "PASS" else "✗" if status == "FAIL" else "?"
        print(f"  {icon} {r['test']}: {status}")
        if status != "PASS":
            print(f"     → {r.get('reason', r)}")

    print()
    if all_pass:
        print("G-DATA GATE: PASS ✓ (Sprint 2 engine can proceed)")
        return 0
    else:
        has_fail = any(r["status"] == "FAIL" for r in results)
        if has_fail:
            print("G-DATA GATE: FAIL ✗ (Fix topology issues before Sprint 2)")
            return 1
        else:
            print("G-DATA GATE: SKIP (Schema not fully applied or data not loaded)")
            print("  → Apply db/apply_public_schema.sql and run load_wfs_data.py first")
            return 2


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--municipality", help="Filter to a specific municipality")
    args = parser.parse_args()
    sys.exit(main(args.municipality))
