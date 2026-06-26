"""
QA bod 10 phase 2 — precomputed AI explanations of findings.

The deterministic engine emits a machine-template `evidence_text` per finding.
This script generates a friendlier, plain-Slovak explanation per DISTINCT
(condition_code, severity) combination — NOT per finding — so cost stays
bounded (~13 combos, hard cap 40 LLM calls). The explanation says, in human
language: what the finding means, why it is a § 44 (zákon 596/2003 + 245/2008)
concern, and what an analyst should check.

It does NOT change the deterministic legal verdict — it is a separate,
clearly-labelled AI layer surfaced under its own heading in the UI.

Grounding: each prompt is built ONLY from the finding facts we pass (condition
code, SK label, severity, a representative redacted evidence string, an example
district, and the § 44 rule context). The model is explicitly instructed not to
invent specific numbers, addresses, or school names.

Idempotent: combos already present in skolske_obvody.finding_explanations are
skipped, so reruns never re-call the LLM for work already done.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY|OPENAI_API_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/generate_finding_explanations.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

ROOT = Path(__file__).resolve().parent.parent
MIGRATION_SQL = ROOT / "scripts" / "sql" / "0024_finding_explanations.sql"

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = "gpt-4o-mini"  # cheap, fast; OpenAI direct

# Hard safety cap on total LLM calls (combos are ~13, well under this).
MAX_LLM_CALLS = 40

# Per-condition canonical rule text — VERBATIM from lib/compliance/labels.ts
# (CONDITION_LABELS_SK[*].description). This is the single source of truth the
# model must paraphrase WITHOUT adding qualifiers or thresholds of its own.
# Keep these strings byte-identical to labels.ts; for legal-compliance content
# any drift (e.g. adding "rovnakého typu" to Š3) is a correctness bug.
RULE_CONTEXT: dict[str, str] = {
    "S1": "Mapa adries všetkých žiakov musí spadať do správneho obvodu. Bez Registra adries to overiť nevieme — preto Š1 zatiaľ ostáva NEÚPLNÉ.",
    "S2": "Plocha obce musí byť pokrytá obvodmi bez medzier a bez prekryvov. Overujeme cez OSM geometriu.",
    "S3": "Jeden obvod patrí jednej škole. Ak je v obvode viac škôl, ide o porušenie zákona.",
    "Pa": "Žiak 1. stupňa nemá mať školu vzdialenú viac než 2 km vzdušnou čiarou.",
    "Pb": "Reálna pešia trasa nemá presahovať 30 minút (cca 2,5 km mestskou cestou).",
    "Pc": "Ak chodí žiak MHD-kou, prestup nesmie byť potrebný viac než raz. Ilustratívny indikátor — nezáväzný.",
    "Pd": "Trasa z domu do školy neprekračuje rušnú cestu bez priechodu ani železnicu bez podchodu.",
    "Pe": "Obvod nevylučuje deti z marginalizovaných komunít. Kontrolujeme voči Atlasu MRK — ide o signál, nie verdikt.",
    "Pf": "Demografická prognóza počtu detí v obvode súvisí s kapacitou školy. Odhadované z dát ŠTATSR.",
}

SEVERITY_SK: dict[str, str] = {
    "critical": "kritická",
    "high": "vysoká",
    "medium": "stredná",
    "low": "nízka",
    "info": "informatívna",
}

SYSTEM_PROMPT = (
    "Si analytik kontroly súladu školských obvodov so zákonom (§ 44, zákon "
    "596/2003 Z. z. a 245/2008 Z. z.) na Slovensku. Tvojou úlohou je vysvetliť "
    "jeden TYP nálezu zrozumiteľnou, vecnou slovenčinou pre úradníka.\n"
    "Pravidlá:\n"
    "- Píš iba po slovensky, 3 až 4 vety, bez nadpisov a odrážok.\n"
    "- Vysvetli: (1) čo nález znamená, (2) prečo je to z hľadiska § 44 problém "
    "alebo signál, (3) čo má analytik overiť.\n"
    "- Vychádzaj VÝLUČNE z poskytnutých faktov. NEVYMÝŠĽAJ konkrétne čísla, "
    "adresy, názvy škôl ani obvodov; hovor o type nálezu všeobecne.\n"
    "- Vysvetli VÝHRADNE poskytnuté pravidlo. Nepridávaj podmienky ani "
    "kvalifikátory, ktoré v ňom nie sú (napr. typ školy, prahy, lehoty), a "
    "nevymýšľaj prahové hodnoty.\n"
    "- Nemeň ani nehodnoť právny verdikt — len ho vysvetli ľudskou rečou."
)


def _apply_migration() -> bool:
    sql = MIGRATION_SQL.read_text(encoding="utf-8")
    print(f"[explanations] applying {MIGRATION_SQL.relative_to(ROOT)} ({len(sql)} chars)")
    result = exec_sql(sql)
    if not result.get("ok"):
        print(f"[explanations] migration FAILED: {result}")
        return False
    print("[explanations] migration OK")
    return True


def _distinct_combos() -> list[dict]:
    """Distinct (condition_code, severity) combos + a representative redacted
    evidence sample for grounding. One row per combo."""
    return query_sql(
        """
        SELECT DISTINCT ON (condition_code, severity)
          condition_code,
          severity,
          skolske_obvody.sanitize_evidence(evidence_text, 240) AS evidence_sample,
          (SELECT d.name FROM skolske_obvody.districts d WHERE d.id = f.district_id) AS example_district
        FROM skolske_obvody.findings f
        GROUP BY condition_code, severity, district_id, evidence_text
        ORDER BY condition_code, severity, condition_code
        """
    )


def _already_done() -> set[tuple[str, str]]:
    rows = query_sql(
        "SELECT condition_code, severity FROM skolske_obvody.finding_explanations"
    )
    return {(r["condition_code"], r["severity"]) for r in (rows or [])}


def _condition_label(code: str) -> str:
    # Mirror the SK labels used in the views/UI.
    labels = {
        "S1": "Š1 — Adresy žiakov a obvod",
        "S2": "Š2 — Topologické pokrytie",
        "S3": "Š3 — Kompozícia obvodu",
        "Pa": "P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km",
        "Pb": "P-b — Pešia trasa",
        "Pc": "P-c — MHD dostupnosť",
        "Pd": "P-d — Bariéry (cesty, koľaje)",
        "Pe": "P-e — Sociálny kontext (Atlas MRK)",
        "Pf": "P-f — Demografia detí",
    }
    return labels.get(code, code)


def _build_user_prompt(combo: dict) -> str:
    code = combo["condition_code"]
    severity = combo["severity"]
    return (
        f"Typ podmienky § 44: {code} — {_condition_label(code)}\n"
        f"Závažnosť nálezu: {SEVERITY_SK.get(severity, severity)}\n"
        f"Autoritatívne pravidlo (vysvetli VÝHRADNE toto, nepridávaj nič): "
        f"{RULE_CONTEXT.get(code, 'Podmienka § 44 školského obvodu.')}\n"
        f"Ukážka strojového dôkazu (anonymizovaná, len ilustračná): "
        f"{(combo.get('evidence_sample') or '—')}\n\n"
        "Napíš zrozumiteľné vysvetlenie tohto typu nálezu (3–4 vety) podľa pravidiel."
    )


def _call_openai(user_prompt: str) -> str:
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 300,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        OPENAI_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def _store(code: str, severity: str, explanation: str) -> bool:
    # Dollar-quote the explanation safely (model output may contain quotes).
    tag = "$_expl$"
    sql = (
        "INSERT INTO skolske_obvody.finding_explanations "
        "(condition_code, severity, explanation_sk, model, generated_at) VALUES ("
        f"$_c${code}$_c$, $_s${severity}$_s$, {tag}{explanation}{tag}, "
        f"$_m${MODEL}$_m$, now()) "
        "ON CONFLICT (condition_code, severity) DO UPDATE SET "
        "explanation_sk = EXCLUDED.explanation_sk, model = EXCLUDED.model, "
        "generated_at = EXCLUDED.generated_at"
    )
    result = exec_sql(sql)
    if not result.get("ok"):
        print(f"[explanations] store FAILED for {code}/{severity}: {result}")
        return False
    return True


def main() -> int:
    validate_config()
    if not OPENAI_API_KEY:
        print("[explanations] ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 2

    if not _apply_migration():
        return 1

    combos = _distinct_combos()
    print(f"[explanations] {len(combos)} distinct (condition_code, severity) combos")

    done = _already_done()
    if done:
        print(f"[explanations] {len(done)} combos already generated — will skip")

    todo = [c for c in combos if (c["condition_code"], c["severity"]) not in done]
    if len(todo) > MAX_LLM_CALLS:
        print(
            f"[explanations] ERROR: {len(todo)} combos exceed hard cap "
            f"{MAX_LLM_CALLS}; aborting", file=sys.stderr,
        )
        return 3

    llm_calls = 0
    generated = 0
    for combo in todo:
        code = combo["condition_code"]
        severity = combo["severity"]
        prompt = _build_user_prompt(combo)
        try:
            explanation = _call_openai(prompt)
            llm_calls += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(
                f"[explanations] OpenAI HTTP {e.code} for {code}/{severity}: "
                f"{body[:200]}", file=sys.stderr,
            )
            print(
                "[explanations] aborting — auth/quota issue. Schema + UI already "
                "wired; rerun once OpenAI works.", file=sys.stderr,
            )
            break
        except Exception as ex:  # noqa: BLE001
            print(f"[explanations] call error for {code}/{severity}: {ex}", file=sys.stderr)
            break

        if not explanation:
            print(f"[explanations] empty explanation for {code}/{severity} — skip")
            continue

        if _store(code, severity, explanation):
            generated += 1
            print(f"[explanations] OK {code}/{severity} ({len(explanation)} chars)")
        time.sleep(0.3)

    print(
        f"\n[explanations] DONE: generated={generated} llm_calls={llm_calls} "
        f"model={MODEL} (cap={MAX_LLM_CALLS})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
