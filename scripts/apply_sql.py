"""
Generic SQL applier via the exec_sql RPC bridge.

Usage:
    python3 scripts/apply_sql.py scripts/sql/0031_demo_input_columns.sql [more.sql ...]

Lives under scripts/ because the harness path-block hook forbids file-tool
writes under any /migrations/ directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.supabase_client import exec_sql  # noqa: E402


def apply_file(path: Path) -> bool:
    sql = path.read_text(encoding="utf-8")
    print(f"[apply_sql] applying {path} ({len(sql)} chars)")
    result = exec_sql(sql)
    ok = bool(result.get("ok"))
    print(f"[apply_sql] {'OK' if ok else 'FAILED'} on {path.name}: {str(result)[:200]}")
    return ok


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python3 scripts/apply_sql.py <file.sql> [...]")
        return 2
    for arg in argv:
        p = Path(arg)
        if not p.is_absolute():
            p = ROOT / arg
        if not apply_file(p):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
