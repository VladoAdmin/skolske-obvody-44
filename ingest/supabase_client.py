"""
Bridge-backed Supabase client for skolske_obvody schema.

ALL writes go through f2_exec_sql (SECURITY DEFINER, service_role only).
ALL reads go through f2_query_sql.

PostgREST does not expose the skolske_obvody schema, so direct REST
table calls to skolske_obvody.* are not used.

The public upsert() API is kept identical so loaders need no rewriting:
    result = upsert("regions", records, on_conflict="code")
    result = upsert("schools", records, on_conflict="eduid")

Geometry values: supply as "SRID=4326;WKT_STRING" — this client
will render them as ST_GeomFromEWKT($tag$...$tag$).

JSONB values: supply as a JSON string (already JSON-encoded) —
will be cast with ::jsonb.

Dollar-quoting strategy: each scalar value is wrapped in a unique
$$-style tag (col_N_M) to prevent injection even with embedded quotes,
dollar signs, or unicode.
"""

import json
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from ingest.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# Schema prefix for all table operations
_SCHEMA = "skolske_obvody"

# Columns that hold PostGIS geometry (EWKT values starting with "SRID=")
_GEOM_COLUMNS = frozenset({"geom"})

# Columns that hold JSONB (will be cast to ::jsonb)
_JSONB_COLUMNS = frozenset({"raw_properties", "streets_json", "street_qualifiers_json",
                             "shared_municipalities_json", "provenance", "methodology",
                             "evidence_refs", "metadata"})


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _rpc(function_name: str, params: dict, timeout: int = 60) -> dict:
    """Call a PostgREST RPC endpoint. Returns the parsed JSON response."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{function_name}"
    payload = json.dumps(params, ensure_ascii=False).encode("utf-8")
    headers = _headers()
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in (429, 503) and attempt < 4:
                wait = 2 ** attempt
                print(f"  RPC rate limit ({e.code}), retry in {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"RPC {function_name} HTTP {e.code}: {body[:300]}"
            ) from e
        except Exception as ex:
            if attempt < 4:
                wait = 2 ** attempt
                print(f"  RPC error ({ex}), retry in {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"RPC {function_name} failed after 5 attempts")


def exec_sql(sql: str) -> dict:
    """Execute a DDL/DML statement via f2_exec_sql. Returns {ok, ...}."""
    return _rpc("f2_exec_sql", {"query": sql})


def query_sql(sql: str) -> list[dict]:
    """Execute a query via f2_query_sql. Returns list of row dicts."""
    result = _rpc("f2_query_sql", {"query": sql})
    if not result.get("ok"):
        raise RuntimeError(
            f"query_sql failed: [{result.get('sqlstate')}] {result.get('message')}"
        )
    return result.get("rows", [])


def count(table: str) -> int:
    """Return total row count for a table in skolske_obvody schema."""
    rows = query_sql(f"SELECT COUNT(*) AS n FROM {_SCHEMA}.{table}")
    if rows:
        return int(rows[0].get("n", 0))
    return -1


def _dollar_tag(col: str, row_idx: int, col_idx: int) -> str:
    """Generate a unique dollar-quote tag that cannot appear in column values."""
    return f"$_c{col_idx}r{row_idx}$"


def _escape_value(
    col: str,
    val: Any,
    row_idx: int,
    col_idx: int,
) -> str:
    """
    Render a Python value as a SQL literal.

    - None        → NULL
    - geom cols   → ST_GeomFromEWKT($tag$...$tag$)
    - JSONB cols  → $tag$...$tag$::jsonb
    - bool        → TRUE / FALSE
    - int/float   → bare number
    - str         → $tag$...$tag$ (dollar-quoted)
    - other       → $tag$str(val)$tag$
    """
    if val is None:
        return "NULL"

    tag = _dollar_tag(col, row_idx, col_idx)

    if col in _GEOM_COLUMNS and isinstance(val, str):
        # PostGIS is in the 'public' schema; must be schema-qualified since
        # search_path inside f2_exec_sql / f2_query_sql does not include public.
        if val.upper().startswith("SRID="):
            return f"public.ST_GeomFromEWKT({tag}{val}{tag})"
        # Fallback: treat as WKT with assumed SRID 4326
        return f"public.ST_SetSRID(public.ST_GeomFromText({tag}{val}{tag}), 4326)"

    if col in _JSONB_COLUMNS and isinstance(val, str):
        return f"{tag}{val}{tag}::jsonb"

    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"

    if isinstance(val, (int, float)):
        return str(val)

    if isinstance(val, str):
        return f"{tag}{val}{tag}"

    # Fallback: JSON-encode then dollar-quote
    return f"{tag}{json.dumps(val, ensure_ascii=False)}{tag}"


def _build_upsert_sql(
    table: str,
    records: list[dict],
    on_conflict: str,
    geom_columns: Optional[frozenset] = None,
) -> str:
    """
    Build a single INSERT … ON CONFLICT … DO UPDATE SET … statement
    for a batch of records.

    All values are dollar-quoted; geometry columns use ST_GeomFromEWKT.
    """
    if not records:
        raise ValueError("records must not be empty")

    # Collect union of all keys across records (all records must share same schema)
    all_keys: set[str] = set()
    for r in records:
        all_keys.update(r.keys())
    # Use insertion order from first record, then append any extra keys
    seen: set[str] = set()
    cols: list[str] = []
    for k in records[0].keys():
        cols.append(k)
        seen.add(k)
    for k in all_keys:
        if k not in seen:
            cols.append(k)

    quoted_cols = ", ".join(cols)

    # Build VALUES clause
    value_rows = []
    for row_idx, rec in enumerate(records):
        parts = []
        for col_idx, col in enumerate(cols):
            val = rec.get(col)
            parts.append(_escape_value(col, val, row_idx, col_idx))
        value_rows.append(f"({', '.join(parts)})")
    values_clause = ",\n  ".join(value_rows)

    # Build ON CONFLICT … DO UPDATE SET for non-key columns
    conflict_cols = [c.strip() for c in on_conflict.split(",")]
    update_cols = [c for c in cols if c not in conflict_cols]

    if update_cols:
        updates = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in update_cols
        )
        conflict_clause = (
            f"ON CONFLICT ({on_conflict}) DO UPDATE SET {updates}"
        )
    else:
        conflict_clause = f"ON CONFLICT ({on_conflict}) DO NOTHING"

    return (
        f"INSERT INTO {_SCHEMA}.{table} ({quoted_cols})\n"
        f"VALUES\n  {values_clause}\n"
        f"{conflict_clause}"
    )


def upsert(
    table: str,
    records: list[dict],
    on_conflict: str = "id",
    returning: str = "minimal",   # kept for API compatibility, not used
    batch_size: int = 200,
) -> dict:
    """
    Upsert a list of records into skolske_obvody.<table> via f2_exec_sql.

    Returns {"inserted": N, "errors": [...]}

    batch_size: number of rows per SQL statement (keeps statements manageable).
    """
    if not records:
        return {"inserted": 0, "errors": []}

    inserted = 0
    errors = []

    for start in range(0, len(records), batch_size):
        batch = records[start: start + batch_size]
        try:
            sql = _build_upsert_sql(table, batch, on_conflict)
        except Exception as ex:
            errors.append({
                "table": table,
                "batch_start": start,
                "error": f"SQL build failed: {ex}",
            })
            continue

        try:
            result = exec_sql(sql)
            if result.get("ok"):
                inserted += len(batch)
            else:
                errors.append({
                    "table": table,
                    "batch_start": start,
                    "sqlstate": result.get("sqlstate"),
                    "message": result.get("message", "")[:400],
                })
        except Exception as ex:
            errors.append({
                "table": table,
                "batch_start": start,
                "error": str(ex)[:400],
            })

    return {"inserted": inserted, "errors": errors}


def select(
    table: str,
    params: Optional[dict] = None,
    limit: int = 1000,
) -> list[dict]:
    """
    Select rows via f2_query_sql.
    params: simple equality filters {column: value}.
    """
    where_parts = []
    if params:
        for col, val in params.items():
            if val is None:
                where_parts.append(f"{col} IS NULL")
            elif isinstance(val, str):
                tag = f"$_sel_{col}$"
                where_parts.append(f"{col} = {tag}{val}{tag}")
            else:
                where_parts.append(f"{col} = {val}")

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    sql = f"SELECT * FROM {_SCHEMA}.{table} {where_clause} LIMIT {limit}"
    return query_sql(sql)


def call_rpc(function_name: str, params: dict) -> Any:
    """Call a PostgREST RPC function in the public schema."""
    return _rpc(function_name, params)
