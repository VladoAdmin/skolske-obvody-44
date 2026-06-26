"""
Sprint I — Validate existing house_geocodes + detect real street range ends.

Steps:
  (A) For each house_geocode row:
      - Extract house number from formatted_address
      - If no number found (Google returned only street name) → valid=false, reason='no_house_in_formatted_address'
      - If extracted number != queried house_number → valid=false, reason='house_number_mismatch'
      - If partial_match AND no number found → valid=false, reason='partial_match_off_target'
      - Otherwise → valid=true

  (B) For each (district_id, street) pair with range_type in ('odd','even','range','single'):
      - Compute detected_min, detected_max from valid house_geocodes for that pair
      - UPDATE vzn_street_ranges SET detected_min, detected_max, detection_method

  (C) Print per-district and per-street validation report.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(GOOGLE_API_KEY|SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/validate_house_geocodes.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from typing import Optional

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_house_number_from_fa(formatted_address: Optional[str]) -> Optional[str]:
    """
    Extract the house number from a Google formatted_address string.

    Handles:
      'Bajkalská 199, 080 01 Prešov, Slovakia'           → '199'
      'Bajkalská 4862/17, 080 01 Prešov, Slovakia'       → '17'
      'Federátov 6499/2, Sekčov, 080 01 Prešov, Slovakia' → '2'
      'Bajkalská, 080 01 Prešov, Slovakia'               → None  (no number)
    """
    if not formatted_address:
        return None

    # Step 1: strip postal code + city + country suffix
    fa_clean = re.sub(r',?\s*\d{3}\s*\d{2}\s+.*$', '', formatted_address).strip()
    # Step 2: strip any district name suffix (e.g. ', Sekčov')
    fa_clean = re.sub(r',.*$', '', fa_clean).strip()
    # Step 3: extract NUMBER or PREF/NUMBER at end of string
    m = re.search(r'[/ ](\d+)\s*$', fa_clean)
    if m:
        return m.group(1)
    return None


def _dq(tag: str, val: str) -> str:
    """Dollar-quote a string value."""
    return f"$__{tag}__${val}$__{tag}__$"


# ---------------------------------------------------------------------------
# Step (A) — ADD validation columns if missing + validate all rows
# ---------------------------------------------------------------------------

def _ensure_validation_columns() -> None:
    """Add valid/validation_reason/validated_at columns if not present."""
    sql = """
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'skolske_obvody'
      AND table_name = 'house_geocodes'
      AND column_name = 'valid'
  ) THEN
    ALTER TABLE skolske_obvody.house_geocodes
      ADD COLUMN valid BOOLEAN,
      ADD COLUMN validation_reason TEXT,
      ADD COLUMN validated_at TIMESTAMPTZ;
  END IF;
END $$
"""
    result = exec_sql(sql)
    if not result.get("ok"):
        print(f"  WARN: Could not add validation columns: {result.get('message', '?')}")


def _ensure_detection_columns() -> None:
    """Add detected_min/detected_max/detection_method to vzn_street_ranges if not present."""
    sql = """
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'skolske_obvody'
      AND table_name = 'vzn_street_ranges'
      AND column_name = 'detected_min'
  ) THEN
    ALTER TABLE skolske_obvody.vzn_street_ranges
      ADD COLUMN detected_min INT,
      ADD COLUMN detected_max INT,
      ADD COLUMN detection_method TEXT;
  END IF;
END $$
"""
    result = exec_sql(sql)
    if not result.get("ok"):
        print(f"  WARN: Could not add detection columns: {result.get('message', '?')}")


def validate_all_geocodes() -> dict:
    """
    Load all house_geocodes, validate each, batch-UPDATE the DB.

    Returns stats dict.
    """
    print("\n[A] Loading house_geocodes...")
    rows = query_sql("""
        SELECT id, district_id, street, house_number,
               formatted_address, partial_match, status
        FROM skolske_obvody.house_geocodes
        ORDER BY street, CASE WHEN house_number ~ '^[0-9]+$' THEN house_number::int ELSE 0 END
    """)
    print(f"  Loaded {len(rows)} rows")

    valid_ids: list[str] = []
    invalid_rows: list[dict] = []

    for r in rows:
        hid = r['id']
        queried_hn = r['house_number']
        fa = r.get('formatted_address')
        pm = r.get('partial_match', False)
        status = r.get('status', '')

        # Non-OK status → invalid regardless
        if status != 'OK':
            invalid_rows.append({'id': hid, 'reason': f'status_{status.lower()}'})
            continue

        extracted = _extract_house_number_from_fa(fa)

        if extracted is None:
            # Google returned only street name (no house number at all)
            if pm:
                reason = 'partial_match_off_target'
            else:
                reason = 'no_house_in_formatted_address'
            invalid_rows.append({'id': hid, 'reason': reason})
        elif extracted != queried_hn:
            # Google returned a different house number
            invalid_rows.append({'id': hid, 'reason': 'house_number_mismatch'})
        else:
            valid_ids.append(hid)

    print(f"  Valid: {len(valid_ids)}, Invalid: {len(invalid_rows)}")

    # Batch-update valid rows
    _batch_update_valid(valid_ids)
    # Batch-update invalid rows
    _batch_update_invalid(invalid_rows)

    # Compute stats
    reason_counts: dict[str, int] = {}
    for r in invalid_rows:
        reason_counts[r['reason']] = reason_counts.get(r['reason'], 0) + 1

    return {
        'total': len(rows),
        'valid': len(valid_ids),
        'invalid': len(invalid_rows),
        'reasons': reason_counts,
    }


def _batch_update_valid(ids: list[str]) -> None:
    """Mark a list of house geocode IDs as valid."""
    if not ids:
        return

    now_ts = datetime.now(timezone.utc).isoformat()
    BATCH = 200
    for start in range(0, len(ids), BATCH):
        batch = ids[start:start + BATCH]
        id_list = ", ".join(f"'{hid}'" for hid in batch)
        sql = f"""
UPDATE skolske_obvody.house_geocodes
SET valid = TRUE,
    validation_reason = NULL,
    validated_at = '{now_ts}'::timestamptz
WHERE id IN ({id_list})
"""
        result = exec_sql(sql)
        if not result.get("ok"):
            print(f"  WARN batch update valid [{start}..]: {result.get('message', '?')}")


def _batch_update_invalid(rows: list[dict]) -> None:
    """Mark a list of house geocodes as invalid with reason."""
    if not rows:
        return

    now_ts = datetime.now(timezone.utc).isoformat()
    BATCH = 200
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        # Build case statement
        id_reason_pairs = ", ".join(
            "('" + r["id"] + "', '" + r["reason"] + "')"
            for r in batch
        )
        id_list = ", ".join("'" + r["id"] + "'" for r in batch)
        sql = f"""
UPDATE skolske_obvody.house_geocodes AS hg
SET valid = FALSE,
    validation_reason = v.reason,
    validated_at = '{now_ts}'::timestamptz
FROM (VALUES {id_reason_pairs}) AS v(id, reason)
WHERE hg.id = v.id::uuid
"""
        result = exec_sql(sql)
        if not result.get("ok"):
            print(f"  WARN batch update invalid [{start}..]: {result.get('message', '?')}")


# ---------------------------------------------------------------------------
# Step (B) — Detect real range ends
# ---------------------------------------------------------------------------

def detect_range_ends() -> dict:
    """
    For each vzn_street_ranges row with range_type != 'all':
    - Find min/max of VALID house_geocode house_numbers for same (district_id, street)
    - UPDATE detected_min, detected_max, detection_method
    """
    print("\n[B] Detecting real range ends from validated geocodes...")

    # Load non-all ranges
    ranges = query_sql("""
        SELECT id, district_id, street, range_type, numbers
        FROM skolske_obvody.vzn_street_ranges
        WHERE range_type != 'all'
    """)
    print(f"  Non-all ranges: {len(ranges)}")

    # Load valid house geocodes (only valid=TRUE after step A)
    valid_houses = query_sql("""
        SELECT district_id, street, house_number
        FROM skolske_obvody.house_geocodes
        WHERE valid = TRUE
          AND house_number ~ '^[0-9]+$'
    """)
    print(f"  Valid house geocodes: {len(valid_houses)}")

    # Build lookup: (district_id, street) → list of valid house_numbers
    valid_by_key: dict[tuple[str, str], list[int]] = {}
    for h in valid_houses:
        key = (h['district_id'], h['street'])
        valid_by_key.setdefault(key, []).append(int(h['house_number']))

    # For each range row, compute detected_min/max
    updated = 0
    no_valid_points = 0

    for r in ranges:
        key = (r['district_id'], r['street'])
        nums = valid_by_key.get(key, [])

        if not nums:
            no_valid_points += 1
            continue

        detected_min = min(nums)
        detected_max = max(nums)
        method = 'formatted_address_validation'

        sql = f"""
UPDATE skolske_obvody.vzn_street_ranges
SET detected_min = {detected_min},
    detected_max = {detected_max},
    detection_method = {_dq('method', method)}
WHERE id = '{r['id']}'
"""
        result = exec_sql(sql)
        if result.get("ok"):
            updated += 1
        else:
            print(f"  WARN update range {r['street']}: {result.get('message', '?')}")

    print(f"  Updated: {updated}, No valid points: {no_valid_points}")
    return {'ranges_total': len(ranges), 'updated': updated, 'no_valid_points': no_valid_points}


# ---------------------------------------------------------------------------
# Step (C) — Report
# ---------------------------------------------------------------------------

def print_report(validation_stats: dict, detection_stats: dict) -> None:
    """Print per-street validation report."""
    print("\n[C] Per-street validation report...")

    rows = query_sql("""
        SELECT hg.street,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE hg.valid = TRUE) AS valid_cnt,
               COUNT(*) FILTER (WHERE hg.valid = FALSE) AS invalid_cnt,
               MIN(CASE WHEN hg.valid = TRUE AND hg.house_number ~ '^[0-9]+$' THEN hg.house_number::int END) AS valid_min,
               MAX(CASE WHEN hg.valid = TRUE AND hg.house_number ~ '^[0-9]+$' THEN hg.house_number::int END) AS valid_max
        FROM skolske_obvody.house_geocodes hg
        GROUP BY hg.street
        ORDER BY hg.street
    """)

    print(f"  {'Street':<25} {'Total':>5} {'Valid':>5} {'Invalid':>7} {'ValidRange':>15}")
    print("  " + "-" * 62)
    for r in rows:
        valid_range = f"{r['valid_min']}-{r['valid_max']}" if r['valid_min'] is not None else "—"
        print(f"  {r['street']:<25} {r['total']:>5} {r['valid_cnt']:>5} {r['invalid_cnt']:>7} {valid_range:>15}")

    # Per-district report
    dist_rows = query_sql("""
        SELECT d.name AS district_name,
               COUNT(hg.id) AS total,
               COUNT(hg.id) FILTER (WHERE hg.valid = TRUE) AS valid_cnt,
               COUNT(hg.id) FILTER (WHERE hg.valid = FALSE) AS invalid_cnt
        FROM skolske_obvody.house_geocodes hg
        JOIN skolske_obvody.districts d ON d.id = hg.district_id
        GROUP BY d.name
        ORDER BY d.name
    """)

    print(f"\n  Per-district:")
    print(f"  {'District':<55} {'Total':>5} {'Valid':>5} {'Invalid':>7}")
    print("  " + "-" * 75)
    for r in dist_rows:
        name = r['district_name'][:54] if r['district_name'] else '?'
        print(f"  {name:<55} {r['total']:>5} {r['valid_cnt']:>5} {r['invalid_cnt']:>7}")

    # Detected ranges
    det_rows = query_sql("""
        SELECT vr.street, vr.range_type, vr.numbers,
               vr.detected_min, vr.detected_max, vr.detection_method,
               d.name AS district_name
        FROM skolske_obvody.vzn_street_ranges vr
        JOIN skolske_obvody.districts d ON d.id = vr.district_id
        WHERE vr.range_type != 'all' AND vr.detected_min IS NOT NULL
        ORDER BY vr.street
    """)
    print(f"\n  Detected ranges ({len(det_rows)}):")
    for r in det_rows:
        orig = r.get('numbers') or []
        print(f"  {r['street']:<25} {r['range_type']:<6} orig={orig} → detected={r['detected_min']}-{r['detected_max']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    validate_config()

    print("=" * 64)
    print("Sprint I — Validate House Geocodes + Detect Range Ends")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 64)

    # Ensure columns exist
    print("\n[Setup] Adding validation columns...")
    _ensure_validation_columns()
    _ensure_detection_columns()
    print("  Columns ready.")

    # A) Validate
    validation_stats = validate_all_geocodes()

    # B) Detect ranges
    detection_stats = detect_range_ends()

    # C) Report
    print_report(validation_stats, detection_stats)

    print("\n" + "=" * 64)
    print("VALIDATION SUMMARY")
    print("=" * 64)
    print(f"Total geocodes:  {validation_stats['total']}")
    print(f"Valid:           {validation_stats['valid']}")
    print(f"Invalid:         {validation_stats['invalid']}")
    for reason, cnt in sorted(validation_stats['reasons'].items()):
        print(f"  {reason}: {cnt}")
    print(f"\nRange detection: {detection_stats['updated']} ranges updated of {detection_stats['ranges_total']}")
    print(f"\nFinished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
