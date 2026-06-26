"""
Sprint register-geocode-confidence — PART A (BUDGETED Google geocoding).

Attach REAL coordinates to a prioritized subset of AUTHORITATIVE addresses from
the Prešov address register (skolske_obvody.register_adries, habitable rows
only). Results are cached in skolske_obvody.register_geocode keyed on `adresa`,
so reruns NEVER re-call the paid API.

HARD BUDGET (non-negotiable — Vlado capped the demo at €10):
  MAX_GEOCODE = 2000 total Google requests. The run STOPS when reached.
  Google Geocoding bills ~$5 / 1000 requests, so 2000 calls ~= $10.
  We count + log the exact number of API calls and the estimated cost.

PRIORITIZATION (within the cap):
  Tier 1 'street_anchor'  — one representative habitable address per register
                            street (lowest orientačné číslo). ~400 calls; gives
                            every street an authoritative anchor point.
  Tier 2 'border_house'   — every habitable house on streets whose VZN ranges
                            span >1 district (where precise per-house assignment
                            matters most). ~355 calls.
  Already-cached addresses are skipped (do not consume budget).

Reuses the EXACT Google Geocoding call pattern + key loading from
ingest/google_geocode_houses.py.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY|GOOGLE_API_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/geocode_register_addresses.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY", ""))

RATE_SLEEP = 0.05       # 50 RPS limit (same as google_geocode_houses.py)
MAX_RETRIES = 3
MAX_GEOCODE = 2000      # HARD CAP — total Google requests this run. Never exceed.
COST_PER_1000 = 5.0     # USD, Google Geocoding pricing

PRESOV = "(SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')"

# Same normalisation family as compute_district_address_stats.py.
NORM = lambda col: f"""
  btrim(regexp_replace(
    regexp_replace(
      regexp_replace(
        lower(unaccent(
          replace(replace({col}, 'Arm. gen.', 'Armádneho generála'), 'č.', '')
        )),
        '^ulica\\s+|\\s+ulica$', '', 'g'),
      '[.]', ' ', 'g'),
    '\\s+', ' ', 'g'))
"""


def _check_blockers() -> None:
    validate_config()
    if not GOOGLE_API_KEY:
        print("BLOCKER: GOOGLE_API_KEY not set — geocoding nothing.", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# Google Geocoding — EXACT pattern from google_geocode_houses.py
# ---------------------------------------------------------------------------

def _geocode(adresa: str) -> dict:
    """Call Google Geocoding API for "<adresa>, Prešov, Slovakia"."""
    query = f"{adresa}, Prešov, Slovakia"
    params = urllib.parse.urlencode({
        "address": query,
        "region": "sk",
        "components": "country:SK|locality:Prešov",
        "key": GOOGLE_API_KEY,
    })
    url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"status": "REQUEST_DENIED", "raw": {"http_error": e.code}, "query_used": query}
        except Exception as ex:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"status": "INVALID_REQUEST", "raw": {"error": str(ex)}, "query_used": query}

        api_status = data.get("status", "UNKNOWN")
        if api_status == "OVER_QUERY_LIMIT" and attempt < MAX_RETRIES:
            print(f"    OVER_QUERY_LIMIT, retry ...")
            time.sleep(2 ** (attempt + 2))
            continue

        result: dict = {"status": api_status, "raw": data, "query_used": query}
        if api_status == "OK" and data.get("results"):
            r0 = data["results"][0]
            loc = r0["geometry"]["location"]
            result["lat"] = loc["lat"]
            result["lon"] = loc["lng"]
            result["formatted_address"] = r0.get("formatted_address")
            result["partial_match"] = r0.get("partial_match", False)
        return result

    return {"status": "OVER_QUERY_LIMIT", "raw": {}, "query_used": query}


# ---------------------------------------------------------------------------
# DB upsert (keyed on adresa)
# ---------------------------------------------------------------------------

def _dq(tag: str, val: str) -> str:
    return f"$__{tag}__${val}$__{tag}__$"


def _cache_result(rec: dict, geo: dict) -> None:
    status = geo.get("status", "UNKNOWN")
    lat, lon = geo.get("lat"), geo.get("lon")
    fa = geo.get("formatted_address")
    pm = geo.get("partial_match", False)
    raw = geo.get("raw", {})
    query_used = geo.get("query_used", "")

    geom_expr = (
        f"public.ST_SetSRID(public.ST_MakePoint({lon}, {lat}), 4326)"
        if lat is not None and lon is not None else "NULL"
    )
    lat_sql = str(lat) if lat is not None else "NULL"
    lon_sql = str(lon) if lon is not None else "NULL"
    fa_sql = _dq("fa", fa) if fa else "NULL"
    oc_sql = _dq("oc", rec["orientacne_cislo"]) if rec.get("orientacne_cislo") else "NULL"

    sql = f"""
INSERT INTO skolske_obvody.register_geocode
  (adresa, ulica, orientacne_cislo, query_used, status, lat, lon,
   formatted_address, partial_match, geocode_tier, geom, raw)
VALUES (
  {_dq("ad", rec["adresa"])},
  {_dq("ul", rec["ulica"])},
  {oc_sql},
  {_dq("qu", query_used)},
  {_dq("st", status)},
  {lat_sql}, {lon_sql},
  {fa_sql},
  {"TRUE" if pm else "FALSE"},
  {_dq("ti", rec["tier"])},
  {geom_expr},
  {_dq("raw", json.dumps(raw, ensure_ascii=False))}::jsonb
)
ON CONFLICT (adresa) DO UPDATE SET
  ulica            = EXCLUDED.ulica,
  orientacne_cislo = EXCLUDED.orientacne_cislo,
  query_used       = EXCLUDED.query_used,
  status           = EXCLUDED.status,
  lat              = EXCLUDED.lat,
  lon              = EXCLUDED.lon,
  formatted_address= EXCLUDED.formatted_address,
  partial_match    = EXCLUDED.partial_match,
  geocode_tier     = EXCLUDED.geocode_tier,
  geom             = EXCLUDED.geom,
  raw              = EXCLUDED.raw,
  geocoded_at      = now()
"""
    r = exec_sql(sql)
    if not r.get("ok"):
        print(f"    CACHE ERROR {rec['adresa']}: {r.get('message', '?')}")


# ---------------------------------------------------------------------------
# Build the prioritized work list
# ---------------------------------------------------------------------------

def _load_worklist() -> list[dict]:
    """Tier 1 street anchors (lowest orientačné číslo per street) then Tier 2
    border-street habitable houses. orientačné číslo sorted numerically where
    possible. Returns ordered list of {adresa, ulica, orientacne_cislo, tier}."""
    # Tier 1: one anchor per habitable register street.
    anchors = query_sql("""
        WITH ranked AS (
          SELECT ulica, orientacne_cislo, adresa,
                 row_number() OVER (
                   PARTITION BY ulica
                   ORDER BY NULLIF(regexp_replace(orientacne_cislo, '\\D', '', 'g'), '')::int
                            NULLS LAST,
                            orientacne_cislo
                 ) AS rn
          FROM skolske_obvody.register_adries
          WHERE obyvatelna = true AND adresa IS NOT NULL
        )
        SELECT ulica, orientacne_cislo, adresa
        FROM ranked WHERE rn = 1
        ORDER BY ulica
    """)
    work: list[dict] = [
        {"adresa": a["adresa"], "ulica": a["ulica"],
         "orientacne_cislo": a.get("orientacne_cislo"), "tier": "street_anchor"}
        for a in anchors
    ]
    anchor_addr = {a["adresa"] for a in work}

    # Tier 2: every habitable house on VZN border streets (>1 district), minus
    # any address already queued as a street anchor.
    border = query_sql(f"""
        WITH border AS (
          SELECT {NORM('vr.street')} AS nname
          FROM skolske_obvody.vzn_street_ranges vr
          JOIN skolske_obvody.districts d ON d.id = vr.district_id
          WHERE d.municipality_id = {PRESOV}
          GROUP BY 1
          HAVING count(DISTINCT vr.district_id) > 1
        )
        SELECT ra.ulica, ra.orientacne_cislo, ra.adresa
        FROM skolske_obvody.register_adries ra
        WHERE ra.obyvatelna = true AND ra.adresa IS NOT NULL
          AND {NORM('ra.ulica')} IN (SELECT nname FROM border)
        ORDER BY ra.ulica,
                 NULLIF(regexp_replace(ra.orientacne_cislo, '\\D', '', 'g'), '')::int NULLS LAST
    """)
    for b in border:
        if b["adresa"] in anchor_addr:
            continue
        work.append({"adresa": b["adresa"], "ulica": b["ulica"],
                     "orientacne_cislo": b.get("orientacne_cislo"), "tier": "border_house"})

    # De-dup on adresa (keep first / higher-priority tier).
    seen: set[str] = set()
    deduped: list[dict] = []
    for w in work:
        if w["adresa"] in seen:
            continue
        seen.add(w["adresa"])
        deduped.append(w)
    return deduped


def main() -> None:
    _check_blockers()
    print("=" * 72)
    print("PART A — budgeted Google geocoding of authoritative register addresses")
    print(f"Started: {datetime.now().isoformat()}  MAX_GEOCODE={MAX_GEOCODE}")
    print("=" * 72)

    # Ensure cache table exists (idempotent; full DDL lives in the SQL file).
    exec_sql("""
        CREATE TABLE IF NOT EXISTS skolske_obvody.register_geocode (
          adresa TEXT PRIMARY KEY, ulica TEXT, orientacne_cislo TEXT,
          query_used TEXT, status TEXT, lat DOUBLE PRECISION, lon DOUBLE PRECISION,
          formatted_address TEXT, partial_match BOOLEAN DEFAULT FALSE,
          geocode_tier TEXT, geom public.geometry(Point, 4326), raw JSONB,
          geocoded_at TIMESTAMPTZ DEFAULT now())
    """)

    work = _load_worklist()
    n_anchor = sum(1 for w in work if w["tier"] == "street_anchor")
    n_border = sum(1 for w in work if w["tier"] == "border_house")
    print(f"\n[plan] work items: {len(work)} "
          f"(street_anchor={n_anchor}, border_house={n_border})")

    # Skip already-cached addresses (idempotent; they don't cost budget).
    cached = {r["adresa"] for r in query_sql(
        "SELECT adresa FROM skolske_obvody.register_geocode")}
    pending = [w for w in work if w["adresa"] not in cached]
    print(f"[plan] already cached: {len(cached)}  pending: {len(pending)}")

    if len(pending) > MAX_GEOCODE:
        print(f"[budget] pending {len(pending)} > cap {MAX_GEOCODE} — "
              f"geocoding only the first {MAX_GEOCODE} (anchors first), "
              f"leaving {len(pending) - MAX_GEOCODE} ungeocoded (correct, not a failure)")
        pending = pending[:MAX_GEOCODE]

    est = len(pending) * COST_PER_1000 / 1000
    print(f"[budget] will make at most {len(pending)} calls "
          f"(~${est:.2f} USD / ~€{est * 0.92:.2f})")

    stats = {"calls": 0, "ok": 0, "zero": 0, "partial": 0, "error": 0}
    for i, w in enumerate(pending, 1):
        # HARD STOP — never exceed the budget, whatever the worklist says.
        if stats["calls"] >= MAX_GEOCODE:
            print(f"  BUDGET CAP {MAX_GEOCODE} reached — stopping.")
            break

        geo = _geocode(w["adresa"])
        stats["calls"] += 1
        st = geo.get("status", "UNKNOWN")
        if st == "OK":
            stats["ok"] += 1
            if geo.get("partial_match"):
                stats["partial"] += 1
        elif st == "ZERO_RESULTS":
            stats["zero"] += 1
        else:
            stats["error"] += 1

        _cache_result(w, geo)

        if i % 50 == 0:
            cost = stats["calls"] * COST_PER_1000 / 1000
            print(f"  {i}/{len(pending)} — OK:{stats['ok']} ZERO:{stats['zero']} "
                  f"ERR:{stats['error']} calls:{stats['calls']} ${cost:.2f}")
        time.sleep(RATE_SLEEP)

    # Final totals from the cache.
    total_geocoded = int(query_sql(
        "SELECT count(*) n FROM skolske_obvody.register_geocode WHERE lat IS NOT NULL")[0]["n"])
    cost = stats["calls"] * COST_PER_1000 / 1000

    print("\n" + "=" * 72)
    print("GEOCODER SUMMARY (PART A)")
    print("=" * 72)
    print(f"Google calls this run : {stats['calls']}  (cap {MAX_GEOCODE})")
    print(f"  OK={stats['ok']} ZERO={stats['zero']} partial={stats['partial']} error={stats['error']}")
    print(f"Est cost this run     : ${cost:.2f} USD  (~€{cost * 0.92:.2f})")
    print(f"Total cached w/ coords: {total_geocoded}")
    print(f"Finished: {datetime.now().isoformat()}")

    # Emit a machine-readable line for the orchestrator status file.
    print(f"RESULT geocoded={total_geocoded} google_calls={stats['calls']} "
          f"est_cost_usd={cost:.2f}")


if __name__ == "__main__":
    main()
