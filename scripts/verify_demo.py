import os, sys
env_path = ".env.local"
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("="); os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, "."); sys.path.insert(0, "scripts")
from ingest.supabase_client import query_sql

NINE = "('S1','S2','S3','Pa','Pb','Pc','Pd','Pe','Pf')"
ev = query_sql("SELECT DISTINCT engine_version FROM skolske_obvody.verdicts")
print("engine_versions in DB:", [r["engine_version"] for r in ev])
ev = ev[0]["engine_version"]

bad = query_sql(f"""
  SELECT condition_code, value, count(*) n FROM skolske_obvody.verdicts
  WHERE engine_version='{ev}' AND condition_code IN {NINE}
    AND value IN ('INCOMPLETE','INSUFFICIENT_DATA','NOT_EVALUATED','NO_SIGNAL','ILUSTR_NO_DATA','ILUSTRATIVE_AVAILABLE')
  GROUP BY 1,2""")
print("NON-DECISIVE 44 rows:", bad if bad else "NONE OK")

low = query_sql(f"""
  SELECT condition_code, confidence, data_completeness FROM skolske_obvody.verdicts
  WHERE engine_version='{ev}' AND condition_code IN {NINE}
    AND (confidence < 0.90 OR data_completeness < 0.90)""")
print("LOW conf/compl 44 rows:", len(low))
for r in low[:20]:
    print("  ", r["condition_code"], r["confidence"], r["data_completeness"])

mock = query_sql(f"SELECT count(*) n FROM skolske_obvody.verdicts WHERE engine_version='{ev}' AND is_mock")[0]["n"]
total = query_sql(f"SELECT count(*) n FROM skolske_obvody.verdicts WHERE engine_version='{ev}'")[0]["n"]
print(f"is_mock verdicts: {mock} / {total}")

jz = query_sql(f"""SELECT d.name FROM skolske_obvody.verdicts v
  JOIN skolske_obvody.districts d ON d.id=v.district_id
  WHERE v.condition_code='JAZYK' AND v.value='SIGNAL' AND v.engine_version='{ev}'""")
print("JAZYK SIGNAL:", [r["name"] for r in jz])

# findings register: counts per condition
fr = query_sql(f"""SELECT condition_code, count(*) n, count(*) FILTER (WHERE is_demo) d
  FROM skolske_obvody.findings WHERE engine_version='{ev}' GROUP BY 1 ORDER BY 1""")
print("findings by condition (n, demo):")
for r in fr:
    print(f"  {r['condition_code']}: {r['n']} (demo {r['d']})")

# composition view consistency
comp = query_sql("""SELECT composition_color, count(*) n FROM skolske_obvody.district_compositions GROUP BY 1 ORDER BY 1""")
print("district_compositions colors:", {r["composition_color"]: r["n"] for r in comp})

ms = query_sql("SELECT red_districts_count, orange_districts_count, green_districts_count, open_findings_count FROM skolske_obvody.municipalities_summary")
print("municipalities_summary:", ms[0])
