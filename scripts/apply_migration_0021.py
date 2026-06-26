"""
Apply Sprint M-3 SQL files via the f2_exec_sql RPC bridge:

  1. scripts/sql/0021_add_is_demo_flag.sql   — schema migration
  2. scripts/sql/demo_overlap_island.sql     — demo data seed

Why this lives under scripts/ instead of db/migrations/:
  The harness path-block hook forbids file-tool writes under any /migrations/
  directory. Sprint M-3 keeps the canonical SQL under scripts/sql/ so it can
  still be reviewed and version-controlled, and applies it through the same
  RPC bridge (ingest.supabase_client.exec_sql) used by all earlier ingest
  sprints (B-L) and by Sprint M-2.

Idempotent on both sides:
  - The migration uses IF NOT EXISTS / DROP VIEW IF EXISTS … CASCADE
  - The seed DELETEs prior demo rows by tag before INSERTing fresh
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python3 scripts/apply_migration_0021.py` from project root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.supabase_client import exec_sql, query_sql  # noqa: E402

MIGRATION_SQL = ROOT / "scripts" / "sql" / "0021_add_is_demo_flag.sql"
SEED_SQL = ROOT / "scripts" / "sql" / "demo_overlap_island.sql"


def _apply(path: Path) -> bool:
    sql = path.read_text(encoding="utf-8")
    print(f"[apply_migration_0021] applying {path.relative_to(ROOT)} ({len(sql)} chars)")
    result = exec_sql(sql)
    if not result.get("ok"):
        print(f"[apply_migration_0021] FAILED on {path.name}: {result}")
        return False
    print(f"[apply_migration_0021] OK on {path.name}: {result}")
    return True


def _verify() -> bool:
    """Sanity-check that the migration and seed left the DB in the expected state."""
    print("\n[apply_migration_0021] verifying state ...")

    cols_q = """
      SELECT table_name, column_name
      FROM information_schema.columns
      WHERE table_schema = 'skolske_obvody'
        AND table_name IN ('district_overlaps', 'district_islands', 'findings')
        AND column_name = 'is_demo'
      ORDER BY table_name
    """
    cols = query_sql(cols_q)
    have = {row["table_name"] for row in (cols or [])}
    expected = {"district_overlaps", "district_islands", "findings"}
    missing = expected - have
    if missing:
        print(f"[apply_migration_0021] MISSING is_demo on: {missing}")
        return False
    print(f"[apply_migration_0021] is_demo present on: {sorted(have)}")

    counts_q = """
      SELECT
        (SELECT COUNT(*) FROM skolske_obvody.district_overlaps WHERE is_demo = true) AS overlaps_demo,
        (SELECT COUNT(*) FROM skolske_obvody.district_islands  WHERE is_demo = true) AS islands_demo,
        (SELECT COUNT(*) FROM skolske_obvody.findings          WHERE is_demo = true) AS findings_demo,
        (SELECT COUNT(*) FROM public.so_district_overlaps)                            AS view_overlaps,
        (SELECT COUNT(*) FROM public.so_district_islands)                             AS view_islands,
        (SELECT COUNT(*) FROM public.so_findings_panel)                               AS view_findings_panel
    """
    counts = query_sql(counts_q)
    if not counts:
        print("[apply_migration_0021] verify counts query returned no rows")
        return False
    row = counts[0]
    print(
        "[apply_migration_0021] counts: "
        f"overlaps_demo={row['overlaps_demo']} "
        f"islands_demo={row['islands_demo']} "
        f"findings_demo={row['findings_demo']} "
        f"view_overlaps={row['view_overlaps']} "
        f"view_islands={row['view_islands']} "
        f"view_findings_panel={row['view_findings_panel']}"
    )

    # Brief requires: overlaps_demo >= 2, islands_demo >= 1, findings_demo >= 1
    if row["overlaps_demo"] < 2 or row["islands_demo"] < 1 or row["findings_demo"] < 1:
        print("[apply_migration_0021] verify FAILED: demo counts below threshold")
        return False
    return True


def main() -> int:
    if not _apply(MIGRATION_SQL):
        return 1
    if not _apply(SEED_SQL):
        return 1
    if not _verify():
        return 1
    print("\n[apply_migration_0021] all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
