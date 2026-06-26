"""
Cross-check every VZN-assigned Prešov street against the authoritative
City-of-Prešov "Register adries a stavieb" (QA bod 10 — data-cleaning core).

VZN source of truth for street->district assignment:
    skolske_obvody.vzn_street_ranges  (street, district_id)
  joined to districts/municipalities filtered to slug='presov'.

Authoritative register: skolske_obvody.register_adries.ulica (401 distinct).

For each distinct VZN street we classify:
  EXACT       — byte-identical to a register street.
  NORMALIZED  — matches after case/diacritics/whitespace/"ulica"/"č." folding
                (same normalisation the geometry build uses), but not EXACT.
  FUZZY       — no normalised match; report the closest register street + score.
  NOT FOUND   — no normalised match and best fuzzy score below threshold
                (likely a scrape/geocode artifact — a trust problem).

This script ONLY diagnoses. It does NOT mutate district or geometry data.
Output: docs/vzn-register-validation-report.md

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/validate_vzn_against_register.py
"""

from __future__ import annotations

import re
import sys
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import query_sql

REPORT_PATH = Path(__file__).parent.parent / "docs" / "vzn-register-validation-report.md"

# Streets whose best fuzzy ratio is >= this are reported as FUZZY (a likely
# spelling/variant of a real register street); below it -> NOT FOUND.
FUZZY_THRESHOLD = 0.80


def normalise(s: str) -> str:
    """Case/diacritics/whitespace-insensitive fold.

    Mirrors the geometry build's NORM(): strip diacritics, lowercase, expand the
    one common abbreviation, drop 'č.' and a leading/trailing 'ulica', drop dots,
    collapse whitespace.
    """
    if not s:
        return ""
    t = s.replace("Arm. gen.", "Armádneho generála")
    t = t.replace("č.", "")
    # strip diacritics
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.lower()
    t = re.sub(r"^ulica\s+|\s+ulica$", "", t)
    t = t.replace(".", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def fetch_vzn_streets() -> list[str]:
    rows = query_sql("""
        SELECT DISTINCT vsr.street AS street
        FROM skolske_obvody.vzn_street_ranges vsr
        JOIN skolske_obvody.districts d ON d.id = vsr.district_id
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov'
        ORDER BY vsr.street
    """)
    return [r["street"] for r in rows]


def fetch_register_streets() -> list[str]:
    rows = query_sql("""
        SELECT DISTINCT ulica
        FROM skolske_obvody.register_adries
        WHERE ulica IS NOT NULL
        ORDER BY ulica
    """)
    return [r["ulica"] for r in rows]


def classify(vzn_streets: list[str], reg_streets: list[str]) -> dict:
    reg_exact = set(reg_streets)
    # normalised register -> one representative original spelling
    reg_norm: dict[str, str] = {}
    for r in reg_streets:
        reg_norm.setdefault(normalise(r), r)

    buckets = {"EXACT": [], "NORMALIZED": [], "FUZZY": [], "NOT_FOUND": []}

    for v in vzn_streets:
        if v in reg_exact:
            buckets["EXACT"].append(v)
            continue
        nv = normalise(v)
        if nv in reg_norm:
            buckets["NORMALIZED"].append((v, reg_norm[nv]))
            continue
        # fuzzy: best register match by normalised SequenceMatcher ratio
        best_reg, best_score = None, 0.0
        for r in reg_streets:
            score = SequenceMatcher(None, nv, normalise(r)).ratio()
            if score > best_score:
                best_reg, best_score = r, score
        if best_score >= FUZZY_THRESHOLD:
            buckets["FUZZY"].append((v, best_reg, round(best_score, 3)))
        else:
            buckets["NOT_FOUND"].append((v, best_reg, round(best_score, 3)))

    return buckets


def write_report(vzn_streets, reg_streets, buckets) -> None:
    total = len(vzn_streets)
    n_exact = len(buckets["EXACT"])
    n_norm = len(buckets["NORMALIZED"])
    n_fuzzy = len(buckets["FUZZY"])
    n_nf = len(buckets["NOT_FOUND"])
    matched = n_exact + n_norm

    lines = []
    lines.append("# VZN ↔ Register adries validation report")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append(
        "Cross-check of every VZN-assigned Prešov street "
        "(`skolske_obvody.vzn_street_ranges`, joined to Prešov districts) against "
        "the authoritative City-of-Prešov **Register adries a stavieb** "
        "(`skolske_obvody.register_adries`, 16307 records). "
        "Diagnosis only — no district or geometry data was changed."
    )
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- VZN streets (Prešov, distinct): **{total}**")
    lines.append(f"- Register streets (distinct): **{len(reg_streets)}**")
    lines.append(f"- Matched (EXACT + NORMALIZED): **{matched}** "
                 f"({100*matched/total:.1f}%)")
    lines.append(f"- NOT FOUND (likely artifacts): **{n_nf}**")
    lines.append(f"- FUZZY near-matches (need a human look): **{n_fuzzy}**")
    lines.append("")
    lines.append("## Counts per class")
    lines.append("")
    lines.append("| Class | Count | Meaning |")
    lines.append("|---|---:|---|")
    lines.append(f"| EXACT | {n_exact} | byte-identical to a register street |")
    lines.append(f"| NORMALIZED | {n_norm} | matches after case/diacritics/whitespace/`ulica`/`č.` folding |")
    lines.append(f"| FUZZY | {n_fuzzy} | no exact/normalized match; closest register street ≥ {FUZZY_THRESHOLD} |")
    lines.append(f"| NOT FOUND | {n_nf} | no match, closest < {FUZZY_THRESHOLD} — trust problem |")
    lines.append(f"| **TOTAL** | **{total}** | |")
    lines.append("")

    lines.append("## NOT FOUND — VZN streets absent from the register")
    lines.append("")
    lines.append("These are the streets a downstream consumer cannot anchor to "
                 "an authoritative address. Each is a candidate scrape/geocode "
                 "artifact or a register gap to resolve before geocoding.")
    lines.append("")
    if buckets["NOT_FOUND"]:
        lines.append("| VZN street | Closest register street | Score |")
        lines.append("|---|---|---:|")
        for v, best, score in sorted(buckets["NOT_FOUND"]):
            lines.append(f"| {v} | {best or '—'} | {score} |")
    else:
        lines.append("_None._")
    lines.append("")

    lines.append("## FUZZY — near-matches to verify")
    lines.append("")
    lines.append("Likely the same street under a spelling/variant difference. "
                 "A human should confirm each before treating it as matched.")
    lines.append("")
    if buckets["FUZZY"]:
        lines.append("| VZN street | Closest register street | Score |")
        lines.append("|---|---|---:|")
        for v, best, score in sorted(buckets["FUZZY"], key=lambda x: x[2]):
            lines.append(f"| {v} | {best or '—'} | {score} |")
    else:
        lines.append("_None._")
    lines.append("")

    lines.append("## NORMALIZED — matched only after folding")
    lines.append("")
    lines.append("Matched, but the raw spellings differ (diacritics, `ulica`/`č.`, "
                 "whitespace). Safe, listed for transparency.")
    lines.append("")
    if buckets["NORMALIZED"]:
        lines.append("| VZN street | Register street |")
        lines.append("|---|---|")
        for v, reg in sorted(buckets["NORMALIZED"]):
            lines.append(f"| {v} | {reg} |")
    else:
        lines.append("_None._")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[report] written {REPORT_PATH}")
    return {"total": total, "matched": matched, "not_found": n_nf, "fuzzy": n_fuzzy,
            "exact": n_exact, "normalized": n_norm}


def main() -> dict:
    validate_config()
    print("=" * 70)
    print("VZN ↔ Register adries validation (diagnosis only)")
    print("=" * 70)

    vzn = fetch_vzn_streets()
    reg = fetch_register_streets()
    print(f"VZN streets: {len(vzn)}   Register streets: {len(reg)}")

    buckets = classify(vzn, reg)
    stats = write_report(vzn, reg, buckets)

    print("\nSUMMARY")
    print(f"  total      = {stats['total']}")
    print(f"  exact      = {stats['exact']}")
    print(f"  normalized = {stats['normalized']}")
    print(f"  fuzzy      = {stats['fuzzy']}")
    print(f"  not_found  = {stats['not_found']}")
    return stats


if __name__ == "__main__":
    main()
