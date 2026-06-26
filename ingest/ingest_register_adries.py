"""
Ingest the authoritative City-of-Prešov "Register adries a stavieb".

Source: ingest/data/register_adries_presov.json (16307 records, 401 streets).
This is the real address register Vlado wants used in place of imprecise
Google street geocoding. It has NO coordinates — this sprint does NOT geocode
(geocoding is a separate budgeted step). Zero external-API cost.

What it does:
  1. Loads the JSON.
  2. TRIMS whitespace on every string field (the Súp._č. / Orient._č. fields
     carry leading/trailing spaces that MUST be stripped).
  3. Maps the Áno/Nie text fields to booleans (Obývateľná -> obyvatelna,
     Vyrad. -> vyradena).
  4. Clean full reload into skolske_obvody.register_adries: TRUNCATE then
     batched INSERTs via f2_exec_sql (the register has no stable unique key —
     Index_domu has 11 duplicates + 5 blanks — so an upsert conflict key is
     not available; a deterministic full reload is the correct idempotency).

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/ingest_register_adries.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql
from ingest.supabase_client import _escape_value  # reuse the canonical SQL-literal renderer

DATA_PATH = Path(__file__).parent / "data" / "register_adries_presov.json"
TABLE = "skolske_obvody.register_adries"
SCHEMA_SQL = Path(__file__).parent.parent / "scripts" / "sql" / "0022_register_adries.sql"

# Ordered column list (matches the table). raw is JSONB -> handled by _escape_value
# because "raw" is NOT in the client's _JSONB_COLUMNS set; we cast it ourselves.
COLS = [
    "mesto", "cast_mesta", "ulica", "supisne_cislo", "orientacne_cislo",
    "adresa", "psc", "obyvatelna", "vyradena", "mestska_oblast",
    "popis", "index_domu", "raw",
]

BATCH_SIZE = 300


def _s(rec: dict, key: str) -> str | None:
    """Trim a string field; empty -> None."""
    v = rec.get(key)
    if v is None:
        return None
    v = str(v).strip()
    return v if v != "" else None


def _ano_nie(rec: dict, key: str) -> bool | None:
    """Map Áno/Nie -> True/False; anything else -> None."""
    v = (rec.get(key) or "").strip().lower()
    if v == "áno":
        return True
    if v == "nie":
        return False
    return None


def to_record(rec: dict) -> dict:
    return {
        "mesto": _s(rec, "Mesto"),
        "cast_mesta": _s(rec, "Časť_mesta"),
        "ulica": _s(rec, "Ulica"),
        "supisne_cislo": _s(rec, "Súp._č."),
        "orientacne_cislo": _s(rec, "Orient._č."),
        "adresa": _s(rec, "Adresa"),
        "psc": _s(rec, "PSČ"),
        "obyvatelna": _ano_nie(rec, "Obývateľná"),
        "vyradena": _ano_nie(rec, "Vyrad."),
        "mestska_oblast": _s(rec, "Mestská_oblasť"),
        "popis": _s(rec, "Popis"),
        "index_domu": _s(rec, "Index_domu"),
        # full original record, whitespace preserved, for provenance / future use
        "raw": json.dumps(rec, ensure_ascii=False),
    }


def _render_row(rec: dict, row_idx: int) -> str:
    parts = []
    for col_idx, col in enumerate(COLS):
        val = rec.get(col)
        if col == "raw" and isinstance(val, str):
            # JSONB cast (raw is not in the client's _JSONB_COLUMNS set)
            tag = f"$_raw{row_idx}$"
            parts.append(f"{tag}{val}{tag}::jsonb")
        else:
            parts.append(_escape_value(col, val, row_idx, col_idx))
    return f"({', '.join(parts)})"


def apply_schema() -> None:
    print(f"[schema] Applying {SCHEMA_SQL.name} ...")
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"schema apply failed: {r.get('message')}")
    print("  schema OK (table + public.so_register_adries view)")


def reload_rows(records: list[dict]) -> int:
    print(f"[load] TRUNCATE {TABLE} + insert {len(records)} rows "
          f"(batch={BATCH_SIZE}) ...")
    r = exec_sql(f"TRUNCATE {TABLE} RESTART IDENTITY")
    if not r.get("ok"):
        raise RuntimeError(f"truncate failed: {r.get('message')}")

    cols_clause = ", ".join(COLS)
    inserted = 0
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]
        values = ",\n  ".join(_render_row(rec, i) for i, rec in enumerate(batch))
        sql = f"INSERT INTO {TABLE} ({cols_clause})\nVALUES\n  {values}"
        res = exec_sql(sql)
        if not res.get("ok"):
            raise RuntimeError(
                f"insert batch @{start} failed: "
                f"[{res.get('sqlstate')}] {res.get('message', '')[:300]}"
            )
        inserted += len(batch)
        print(f"  inserted {inserted}/{len(records)}")
    return inserted


def main() -> None:
    validate_config()
    print("=" * 70)
    print("Ingest Register adries a stavieb (Prešov) — authoritative addresses")
    print("=" * 70)

    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    print(f"[read] {len(raw)} source records from {DATA_PATH.name}")

    records = [to_record(r) for r in raw]
    habitable = sum(1 for r in records if r["obyvatelna"] is True)
    streets = len({r["ulica"] for r in records if r["ulica"]})
    print(f"[map]  habitable={habitable}  distinct streets={streets}")

    apply_schema()
    inserted = reload_rows(records)

    db_count = int(query_sql(f"SELECT COUNT(*) AS n FROM {TABLE}")[0]["n"])
    print("\n" + "=" * 70)
    print(f"rows inserted: {inserted}")
    print(f"DB row count:  {db_count}")
    print("=" * 70)
    if db_count != len(raw):
        print(f"WARNING: DB count {db_count} != source {len(raw)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
