"""
Thin PostgREST wrapper for the Supabase project.

Tables are in the 'public' schema with 'so_' prefix.
Uses the service-role key (bypasses RLS) for batch ingestion.

Retry strategy: exponential backoff on 429/503, max 5 attempts.
On persistent failure: logs error and returns structured error — caller
decides whether to skip or abort.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from ingest.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TABLE_PREFIX


def _headers(extra: Optional[dict] = None) -> dict:
    h = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _table_url(table_name: str) -> str:
    """Construct URL for a table (adding so_ prefix if not already present)."""
    if not table_name.startswith(TABLE_PREFIX):
        table_name = TABLE_PREFIX + table_name
    return f"{SUPABASE_URL}/rest/v1/{table_name}"


def upsert(
    table: str,
    records: list[dict],
    on_conflict: str = "id",
    returning: str = "minimal",
    batch_size: int = 500,
) -> dict:
    """
    Upsert a list of records into the given table.
    Returns {"inserted": N, "errors": [...]}
    """
    if not records:
        return {"inserted": 0, "errors": []}

    url = _table_url(table)
    headers = _headers({
        "Prefer": f"resolution=merge-duplicates,return={returning}",
    })

    inserted = 0
    errors = []

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        payload = json.dumps(batch, ensure_ascii=False, default=str).encode("utf-8")

        for attempt in range(5):
            try:
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    inserted += len(batch)
                    break
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code in (429, 503) and attempt < 4:
                    wait = 2 ** attempt
                    print(f"  Rate limit / server error ({e.code}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                errors.append({
                    "table": table,
                    "batch_start": start,
                    "status": e.code,
                    "body": body[:500],
                })
                break
            except Exception as ex:
                errors.append({
                    "table": table,
                    "batch_start": start,
                    "error": str(ex),
                })
                break

    return {"inserted": inserted, "errors": errors}


def select(
    table: str,
    params: Optional[dict] = None,
    limit: int = 1000,
) -> list[dict]:
    """
    Select rows from table. Returns list of records.
    params: dict of PostgREST filter params, e.g. {"code": "eq.PSK"}
    """
    url = _table_url(table)
    qs: dict = {"limit": limit}
    if params:
        qs.update(params)
    full_url = url + "?" + urllib.parse.urlencode(qs)
    headers = _headers({"Accept": "application/json"})

    req = urllib.request.Request(full_url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def count(table: str) -> int:
    """Return total row count for a table."""
    url = _table_url(table)
    headers = _headers({
        "Accept": "application/json",
        "Prefer": "count=exact",
        "Range-Unit": "items",
        "Range": "0-0",
    })
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            cr = resp.headers.get("Content-Range", "0/0")
            total = cr.split("/")[-1]
            return int(total) if total != "*" else -1
    except Exception:
        return -1


def call_rpc(function_name: str, params: dict) -> Any:
    """Call a PostgREST RPC function in the public schema."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{function_name}"
    headers = _headers()
    payload = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))
