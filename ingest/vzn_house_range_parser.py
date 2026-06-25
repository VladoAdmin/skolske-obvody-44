"""
Sprint H — VZN House Range Parser.

Reads VZN raw_text (embedded) and extracts per-district house number ranges
into skolske_obvody.vzn_street_ranges.

Patterns handled:
  odd_all:   "Ulica (nepárne čísla)" → range_type='odd', numbers=[]
  odd_range: "Ulica (nepárne čísla od X – Y)" → range_type='odd', numbers=[X,Y]
  even_all:  "Ulica (párne čísla)" → range_type='even', numbers=[]
  even_range:"Ulica (párne čísla od X – Y)" / "Ulica (párne čísla X – Y)" → range_type='even', numbers=[X,Y]
  range:     "Ulica (X – Y)" or "Ulica (X-Y)" → range_type='range', numbers=[X..Y expanded]
  single:    "Ulica (číslo X)" / "Ulica (čísla X)" → range_type='single', numbers=[X]
  single+:   "Ulica (číslo X, číslo Y)" → multiple singles
  complex:   "Ulica (nepárne č. X – Y, A, párne č. M – N)" → multiple records
  all:       "Ulica" without qualifier → range_type='all', numbers=[]

Idempotent: DELETE district rows + reinsert per run.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(GOOGLE_API_KEY|SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/vzn_house_range_parser.py
"""

from __future__ import annotations

import json
import re
import sys
from typing import Optional

from ingest.config import validate_config
from ingest.vzn_parser import VZN_FULL_TEXT
from ingest.supabase_client import exec_sql, query_sql

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expand_range_list(raw_spec: str) -> list[int]:
    """
    Expand comma/semicolon separated ranges like "X – Y, A – B, C" into
    a flat sorted list of integers.

    e.g. "93 – 101, 105 – 117, 119" → [93,95,97,99,101,105,107,...,117,119]
    Wait — the task says expand for range/single, NOT for odd/even (step handled separately).
    Here we just return the boundary numbers [lo, hi] for ranges, [n] for singles.
    Caller decides the step.
    """
    numbers: list[int] = []
    # Normalise dashes / en-dashes
    raw_spec = raw_spec.replace('–', '-').replace('—', '-')
    # Split by comma
    parts = [p.strip() for p in raw_spec.split(',') if p.strip()]
    for part in parts:
        m = re.match(r'^(\d+)\s*-\s*(\d+)$', part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            # Store as [lo, hi] pair — caller expands
            numbers.extend([lo, hi])
        else:
            m2 = re.match(r'^(\d+)$', part)
            if m2:
                numbers.append(int(m2.group(1)))
    return numbers


def _int_list_to_sql(nums: list[int]) -> str:
    """Render list of ints as Postgres int array literal."""
    if not nums:
        return "ARRAY[]::integer[]"
    return "ARRAY[" + ",".join(str(n) for n in nums) + "]::integer[]"


# ---------------------------------------------------------------------------
# Core parser — returns list of range records per district
# ---------------------------------------------------------------------------

class RangeRecord:
    __slots__ = ('street', 'range_type', 'numbers', 'raw_text')

    def __init__(self, street: str, range_type: str, numbers: list[int], raw_text: str):
        self.street = street
        self.range_type = range_type
        self.numbers = numbers
        self.raw_text = raw_text


def _parse_qualifier(street: str, qualifier: str) -> list[RangeRecord]:
    """
    Given a street name and its raw qualifier (text inside parens),
    return one or more RangeRecord objects.

    Examples:
      "nepárne čísla"               → odd, []
      "nepárne čísla od X – Y"      → odd, [X, Y]
      "párne čísla od X – Y"        → even, [X, Y]
      "párne čísla X – Y"           → even, [X, Y]
      "číslo X"                     → single, [X]
      "čísla X – Y"                 → range, expanded
      "X – Y"                       → range, expanded
      "nepárne č. X – Y, A – B, párne č. M – N"  → multiple records
    """
    q = qualifier.strip()
    records: list[RangeRecord] = []

    # ── Complex: mixed "nepárne č. ... párne č. ..." ──────────────────────
    # e.g. "nepárne č. 93 – 101, 105 – 117, 119, párne č. 62 – 72"
    # or   "nepárne čísla 23 – 91, párne čísla 36 – 60"
    if ('nepárne' in q and 'párne' in q):
        # Split at the "párne" boundary
        # Everything before first "párne" (but after "nepárne") is odd part,
        # everything after is even part.
        # Handle multi-segment odd specs too.

        # Normalise: remove "č." / "čísla" annotations
        q_norm = re.sub(r'čísla?\s*', '', q)  # remove "číslo"/"čísla"/"č."
        q_norm = re.sub(r'č\.\s*', '', q_norm)

        odd_match = re.search(r'nepárne\s+(.+?)(?=párne|$)', q_norm, re.IGNORECASE)
        even_match = re.search(r'párne\s+(.+)', q_norm, re.IGNORECASE)

        if odd_match:
            odd_spec = odd_match.group(1).strip().rstrip(',')
            nums = _expand_range_list(odd_spec)
            records.append(RangeRecord(street, 'odd', nums, qualifier))

        if even_match:
            even_spec = even_match.group(1).strip()
            nums = _expand_range_list(even_spec)
            records.append(RangeRecord(street, 'even', nums, qualifier))

        if records:
            return records

    # ── nepárne only ───────────────────────────────────────────────────────
    m = re.match(r'nepárne\s+(?:čísla?\s*|č\.\s*)?(?:od\s+)?(.+)', q, re.IGNORECASE)
    if m:
        spec = m.group(1).strip()
        nums = _expand_range_list(spec) if spec else []
        return [RangeRecord(street, 'odd', nums, qualifier)]

    # ── párne only ─────────────────────────────────────────────────────────
    m = re.match(r'párne\s+(?:čísla?\s*|č\.\s*)?(?:od\s+)?(.+)', q, re.IGNORECASE)
    if m:
        spec = m.group(1).strip()
        nums = _expand_range_list(spec) if spec else []
        return [RangeRecord(street, 'even', nums, qualifier)]

    # ── číslo X, číslo Y (multiple singles via ", číslo") ─────────────────
    if re.search(r'číslo', q, re.IGNORECASE):
        found = re.findall(r'číslo\s+(\d+)', q, re.IGNORECASE)
        if found:
            records = [RangeRecord(street, 'single', [int(n)], qualifier) for n in found]
            return records

    # ── čísla X – Y (range with that keyword) ─────────────────────────────
    m = re.match(r'čísla?\s+(.+)', q, re.IGNORECASE)
    if m:
        spec = m.group(1).strip()
        nums = _expand_range_list(spec)
        return [RangeRecord(street, 'range', nums, qualifier)]

    # ── bare range "X – Y" or "X - Y" ─────────────────────────────────────
    m = re.match(r'^(\d+)\s*[–\-]\s*(\d+)$', q.strip())
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return [RangeRecord(street, 'range', [lo, hi], qualifier)]

    # ── bare number "X" ────────────────────────────────────────────────────
    m = re.match(r'^(\d+)$', q.strip())
    if m:
        return [RangeRecord(street, 'single', [int(m.group(1))], qualifier)]

    # ── Fallback: store as 'range' with raw ────────────────────────────────
    nums = _expand_range_list(q)
    if nums:
        return [RangeRecord(street, 'range', nums, qualifier)]

    return [RangeRecord(street, 'all', [], qualifier)]


def parse_vzn_ranges(text: str) -> dict[int, list[RangeRecord]]:
    """
    Parse all 12 districts from VZN_FULL_TEXT.
    Returns {district_number: [RangeRecord, ...]}
    """
    from ingest.vzn_parser import _parse_street_list

    # Match each numbered district block
    district_pattern = re.compile(
        r"(\d+)\.\s+(Základná škola[^:]+):\s*\n(.*?)(?=\n\d+\.\s+Základná|$)",
        re.DOTALL,
    )

    result: dict[int, list[RangeRecord]] = {}

    for match in district_pattern.finditer(text):
        num = int(match.group(1))
        content = match.group(3).strip()

        # Split at "Obec:"
        obec_split = re.split(r"\nObec:\s*", content, maxsplit=1)
        streets_text = obec_split[0].strip()

        streets, qualifiers = _parse_street_list(streets_text)

        records: list[RangeRecord] = []
        for street in streets:
            qual = qualifiers.get(street)
            if qual:
                parsed = _parse_qualifier(street, qual)
                records.extend(parsed)
            else:
                records.append(RangeRecord(street, 'all', [], ''))

        result[num] = records

    return result


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------

def _load_district_ids() -> dict[int, str]:
    """Return {district_number: uuid} for Prešov districts."""
    rows = query_sql("""
        SELECT d.id, d.metadata->>'district_number' AS dn
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
        ORDER BY (d.metadata->>'district_number')::int
    """)
    mapping: dict[int, str] = {}
    for row in rows:
        dn_raw = row.get('dn')
        if dn_raw is not None:
            try:
                mapping[int(dn_raw)] = row['id']
            except (ValueError, TypeError):
                pass
    return mapping


def _run_migration() -> None:
    """Create tables if they don't exist yet (idempotent DDL)."""
    print("[Migration] Creating house_geocodes and vzn_street_ranges tables...")

    sql = """
CREATE TABLE IF NOT EXISTS skolske_obvody.house_geocodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  district_id UUID NOT NULL REFERENCES skolske_obvody.districts(id),
  street TEXT NOT NULL,
  house_number TEXT NOT NULL,
  query_used TEXT NOT NULL,
  status TEXT NOT NULL,
  lat NUMERIC(9,6),
  lon NUMERIC(9,6),
  formatted_address TEXT,
  partial_match BOOLEAN,
  place_type TEXT[],
  raw JSONB,
  geom public.geometry(Point, 4326),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(district_id, street, house_number)
);

CREATE INDEX IF NOT EXISTS house_geocodes_district_idx ON skolske_obvody.house_geocodes(district_id);
CREATE INDEX IF NOT EXISTS house_geocodes_street_idx ON skolske_obvody.house_geocodes(street);
CREATE INDEX IF NOT EXISTS house_geocodes_geom_idx ON skolske_obvody.house_geocodes USING gist(geom);

CREATE TABLE IF NOT EXISTS skolske_obvody.vzn_street_ranges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  district_id UUID NOT NULL REFERENCES skolske_obvody.districts(id),
  street TEXT NOT NULL,
  range_type TEXT NOT NULL CHECK (range_type IN ('odd','even','range','single','all')),
  numbers INTEGER[],
  raw_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS vzn_ranges_district_idx ON skolske_obvody.vzn_street_ranges(district_id);
"""
    result = exec_sql(sql)
    if result.get('ok'):
        print("  Tables created / already exist OK")
    else:
        msg = result.get('message', 'unknown')
        print(f"  Migration ERROR: {msg}", file=sys.stderr)
        sys.exit(1)


def _create_public_view() -> None:
    """Create public.so_house_points view."""
    print("[View] Creating public.so_house_points...")
    sql = """
CREATE OR REPLACE VIEW public.so_house_points AS
WITH presov AS (SELECT id FROM skolske_obvody.municipalities WHERE slug='presov')
SELECT
  hg.district_id,
  hg.street,
  hg.house_number,
  hg.lat,
  hg.lon,
  hg.status,
  hg.partial_match,
  hg.formatted_address,
  public.ST_AsGeoJSON(hg.geom)::jsonb AS point_geojson
FROM skolske_obvody.house_geocodes hg
JOIN skolske_obvody.districts d ON d.id = hg.district_id
WHERE d.municipality_id = (SELECT id FROM presov)
  AND hg.lat IS NOT NULL;

GRANT SELECT ON public.so_house_points TO anon;
"""
    result = exec_sql(sql)
    if result.get('ok'):
        print("  View created OK")
    else:
        print(f"  View ERROR: {result.get('message', '?')}")


def _insert_ranges(district_id: str, district_num: int, records: list[RangeRecord]) -> None:
    """Delete old rows for this district and insert new ones."""
    # Delete existing
    del_sql = f"""
DELETE FROM skolske_obvody.vzn_street_ranges
WHERE district_id = $_did_${district_id}$_did_$::uuid
"""
    result = exec_sql(del_sql)
    if not result.get('ok'):
        print(f"  DELETE ERROR district {district_num}: {result.get('message', '?')}", file=sys.stderr)
        return

    if not records:
        return

    # Insert in batches of 100
    batch_size = 100
    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        value_parts = []
        for i, r in enumerate(batch):
            st_tag = f"$_s{i}_${r.street}$_s{i}_$"
            rt_tag = f"$_rt{i}_${r.range_type}$_rt{i}_$"
            raw_tag = f"$_raw{i}_${r.raw_text}$_raw{i}_$"
            nums_sql = _int_list_to_sql(r.numbers)
            value_parts.append(
                f"($_did_${district_id}$_did_$::uuid, {st_tag}, {rt_tag}, {nums_sql}, {raw_tag})"
            )

        values_clause = ",\n  ".join(value_parts)
        ins_sql = f"""
INSERT INTO skolske_obvody.vzn_street_ranges
  (district_id, street, range_type, numbers, raw_text)
VALUES
  {values_clause}
"""
        result = exec_sql(ins_sql)
        if not result.get('ok'):
            print(f"  INSERT batch ERROR district {district_num}: {result.get('message', '?')}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    validate_config()

    print("=" * 64)
    print("Sprint H — VZN House Range Parser")
    print("=" * 64)

    # Step 1: migration
    _run_migration()
    _create_public_view()

    # Step 2: load district IDs
    district_ids = _load_district_ids()
    if not district_ids:
        print("ERROR: no Prešov districts found in DB", file=sys.stderr)
        sys.exit(1)
    print(f"\nDistricts in DB: {len(district_ids)}")

    # Step 3: parse VZN
    print("\n[Parsing] Extracting ranges from VZN text...")
    parsed = parse_vzn_ranges(VZN_FULL_TEXT)
    print(f"  Parsed {len(parsed)} districts from VZN text")

    # Step 4: insert to DB + report
    grand_total = {'odd': 0, 'even': 0, 'range': 0, 'single': 0, 'all': 0}

    for district_num in sorted(parsed.keys()):
        records = parsed[district_num]
        district_id = district_ids.get(district_num)

        if not district_id:
            print(f"  WARNING: no DB row for district {district_num} — skipping")
            continue

        # Count per type
        type_counts: dict[str, int] = {'odd': 0, 'even': 0, 'range': 0, 'single': 0, 'all': 0}
        for r in records:
            type_counts[r.range_type] = type_counts.get(r.range_type, 0) + 1
            grand_total[r.range_type] = grand_total.get(r.range_type, 0) + 1

        _insert_ranges(district_id, district_num, records)

        # Format per-district summary
        summary_parts = []
        for t in ('odd', 'even', 'range', 'single', 'all'):
            if type_counts.get(t, 0) > 0:
                summary_parts.append(f"{t}={type_counts[t]}")
        print(f"  District {district_num:2d}: {len(records):3d} ranges  [{', '.join(summary_parts)}]")

    print("\n" + "=" * 64)
    print("PARSER SUMMARY")
    print("=" * 64)
    total = sum(grand_total.values())
    print(f"Total ranges inserted: {total}")
    for t in ('odd', 'even', 'range', 'single', 'all'):
        print(f"  {t:8s}: {grand_total[t]}")

    # Verify count in DB
    count_rows = query_sql("SELECT COUNT(*) AS n FROM skolske_obvody.vzn_street_ranges")
    db_count = int(count_rows[0]['n']) if count_rows else '?'
    print(f"\nDB row count after insert: {db_count}")
    print("Done.")


if __name__ == "__main__":
    main()
