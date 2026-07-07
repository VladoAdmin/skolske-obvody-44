"""
VLA-19 gate — legal citations must be audited, never invented.

WHY this matters:
  The client's defect report (2026-07-06, defects 5/6/8) found user-facing
  finding texts citing § 44 provisions that say something else entirely
  (Pa cited písm. a) = capacity for a distance check; Pd cited písm. d) =
  language right for an invented "barrier" ground). The fix established
  docs/legal-audit-44.md as the audited allowlist derived from the verbatim
  law text (docs/legal/zakon-321-2025-par-44.md). These tests fail CI when:
    * any § 44 citation appears in user-facing sources without being in the
      audit allowlist (an unaudited/invented citation),
    * a checker's law_ref drifts from the audited per-checker mapping,
    * forbidden regressions return (wrong law number 596/2003 in UI,
      "nesprávny obvod" vocabulary in Š1, Pd claiming a legal ground).
"""

from __future__ import annotations

import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..")

AUDIT_PATH = os.path.join(ROOT, "docs", "legal-audit-44.md")

# Every file that carries user-facing legal text (labels, evidence templates,
# view label CASEs, app copy).
USER_FACING_GLOBS = [
    "lib/compliance/*.ts",
    "app/**/*.tsx",
    "app/**/*.ts",
    "components/**/*.tsx",
    "engine/c_*.py",
    "engine/coverage_gaps.py",
    "engine/runner.py",
    "scripts/sql/0044_legal_audit_labels.sql",
]

# A citation is "specific" when it names an odsek (and optionally písmeno).
# Bare "§ 44" (title-level references) needs no allowlist entry.
CITATION_RE = re.compile(
    r"§\s*44\s+ods\.\s*\d+(?:\s+a\s+\d+)?(?:\s+písm\.\s*[a-f]\))?"
)

# A bare "§ 44" next to a number-with-unit is how an invented limit sneaks
# past the allowlist ("Podľa § 44 je limit 2 km" names no odsek, so
# CITATION_RE never sees it). § 44 sets NO numeric limits, so any such
# pairing must carry the demo-parameter labelling this branch established.
LIMIT_RE = re.compile(r"\d[\d\s.,]*(?:km|min\w*|metrov|m|žiak\w*|%)(?!\w)")
DEMO_MARKER_RE = re.compile(
    r"metodick\w+\s+parame"        # metodický parameter / metodické parametre
    r"|parametr?\w*\s+dema"        # parameter dema / parametre dema
    r"|limit\w*\s+neurčuje"        # zákon limit(y) neurčuje
    r"|neurčuje\s+(?:\w+\s+){0,3}limit"  # zákon (pri nich) neurčuje ... limity
    r"|bez\s+číselného\s+limitu",
    re.IGNORECASE,
)


def _norm(citation: str) -> str:
    return re.sub(r"\s+", " ", citation).strip()


def _allowlist() -> set[str]:
    with open(AUDIT_PATH, encoding="utf-8") as fh:
        audit = fh.read()
    section = audit.split("## Povolené citácie", 1)[1]
    allowed = {
        _norm(m) for m in re.findall(r"\|\s*`(§ 44[^`]+)`\s*\|", section)
    }
    assert allowed, "allowlist table missing in docs/legal-audit-44.md"
    return allowed


def _user_facing_files() -> list[str]:
    files: list[str] = []
    for pattern in USER_FACING_GLOBS:
        files.extend(glob.glob(os.path.join(ROOT, pattern), recursive=True))
    assert files, "user-facing glob matched nothing — paths moved?"
    return sorted(set(files))


def test_every_specific_citation_is_in_the_audited_allowlist():
    allowed = _allowlist()
    violations = []
    for path in _user_facing_files():
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        for match in CITATION_RE.findall(source):
            citation = _norm(match)
            if citation not in allowed:
                violations.append(f"{os.path.relpath(path, ROOT)}: '{citation}'")
    assert not violations, (
        "unaudited § 44 citation(s) — add ONLY if literally supported by "
        "docs/legal/zakon-321-2025-par-44.md and record them in "
        "docs/legal-audit-44.md:\n" + "\n".join(violations)
    )


def _strip_dev_comments(path: str, source: str) -> str:
    """This gate targets user-facing strings. Whole-line dev comments
    (//, --, #) and Python module docstrings discuss thresholds vs. the law
    freely (often in English), and are never shown to users — drop them."""
    if path.endswith(".py"):
        parts = source.split('"""', 2)
        if len(parts) == 3:
            source = parts[2]
        marker = "#"
    elif path.endswith(".sql"):
        marker = "--"
    else:
        marker = "//"
    return "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith(marker)
    )


def test_bare_44_next_to_a_numeric_limit_carries_the_demo_marker():
    """§ 44 prescribes no numeric limits (docs/legal/zakon-321-2025-par-44.md).

    Any user-facing text that puts "§ 44" within reach of a number-with-unit
    (m/km/min/%/žiakov) is presenting an invented legal limit unless it also
    carries the demo-parameter labelling ("metodický parameter" /
    "parameter dema" / "zákon limit neurčuje") in the same neighbourhood.
    """
    violations = []
    for path in _user_facing_files():
        with open(path, encoding="utf-8") as fh:
            source = _strip_dev_comments(path, fh.read())
        source = re.sub(r"\s+", " ", source)
        for match in re.finditer(r"§\s*44", source):
            window = source[max(0, match.start() - 250) : match.end() + 250]
            if LIMIT_RE.search(window) and not DEMO_MARKER_RE.search(window):
                violations.append(
                    f"{os.path.relpath(path, ROOT)}: …{window.strip()}…"
                )
    assert not violations, (
        "§ 44 appears next to a numeric limit without demo-parameter "
        "labelling — § 44 sets no numeric limits; label the threshold as a "
        "metodický parameter dema or drop the citation:\n"
        + "\n\n".join(violations)
    )


def test_checker_law_refs_match_the_audit_mapping():
    """The per-checker law_ref mapping is the audited one (docs/legal-audit-44.md).

    Pa must NOT cite písm. a) (capacity), Pf must NOT cite písm. f)
    (inclusive education) — those were the invented citations of defect 5.
    """
    from engine import c_lang, c_pa, c_pb, c_pc, c_pe, c_pf, c_s1, c_s2, c_s3

    expected = {
        c_s1: "§ 44 ods. 1",
        c_s2: "§ 44 ods. 1 a 7",
        c_s3: "§ 44 ods. 1",
        c_pa: "§ 44 ods. 8 písm. b)",
        c_pb: "§ 44 ods. 8 písm. b)",
        c_pc: "§ 44 ods. 8 písm. c)",
        c_pe: "§ 44 ods. 8 písm. e)",
        c_pf: "§ 44 ods. 8 písm. a)",
        c_lang: "§ 44 ods. 8 písm. d)",
    }
    for module, law_ref in expected.items():
        actual = module._METHODOLOGY["law_ref"]
        assert actual == law_ref, (
            f"{module.__name__}: law_ref '{actual}' != audited '{law_ref}'"
        )


def test_pd_carries_no_legal_citation():
    """§ 44 does not mention route barriers (defect 6): Pd is a non-legal
    indicator — its law_ref must not name any provision, and its evidence
    templates must not cite one."""
    from engine import c_pd

    law_ref = c_pd._METHODOLOGY["law_ref"]
    assert CITATION_RE.search(law_ref) is None, (
        f"Pd law_ref cites a provision: '{law_ref}'"
    )
    assert "bez priamej opory" in law_ref

    with open(os.path.join(ROOT, "engine", "c_pd.py"), encoding="utf-8") as fh:
        source = fh.read()
    # The docstring may explain WHY písm. d) is wrong; evidence strings may not
    # cite anything. Strip the module docstring before scanning.
    body = source.split('"""', 2)[2]
    assert CITATION_RE.search(body) is None, (
        "engine/c_pd.py evidence/methodology text cites a § 44 provision — "
        "barriers have no legal basis in § 44"
    )


def test_forbidden_regressions():
    """Wrong-law and defect-8 vocabulary must not come back."""
    # § 44 belongs to zákon č. 321/2025 Z. z.; 596/2003 is the predecessor law.
    for pattern in ["app/**/*.tsx", "components/**/*.tsx", "lib/**/*.ts"]:
        for path in glob.glob(os.path.join(ROOT, pattern), recursive=True):
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            assert "596/2003" not in source, (
                f"{os.path.relpath(path, ROOT)}: cites zákon 596/2003 — "
                "§ 44 (verejný školský obvod) is in zákon č. 321/2025 Z. z."
            )

    # Š1 vocabulary: overlap / coverage-gap only, never "nesprávny obvod".
    # (The module docstring quotes the forbidden word to explain the rule —
    # scan only the code body.)
    with open(os.path.join(ROOT, "engine", "c_s1.py"), encoding="utf-8") as fh:
        s1_source = fh.read().split('"""', 2)[2].lower()
    assert "nesprávn" not in s1_source, (
        "engine/c_s1.py uses 'nesprávny obvod' vocabulary — client defect 8: "
        "use prekryv priradenia / medzera v pokrytí instead"
    )
