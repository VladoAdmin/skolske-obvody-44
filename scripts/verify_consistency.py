import os, sys
[os.environ.setdefault(*l.strip().split("=",1)) for l in open(".env.local") if l.strip() and not l.startswith("#") and "=" in l]
sys.path.insert(0, "."); sys.path.insert(0, "scripts")
from ingest.supabase_client import query_sql

print("=== FINDINGS (register) — district x condition x value ===")
rows = query_sql("""
  SELECT d.name, f.condition_code, f.severity, f.is_demo
  FROM skolske_obvody.findings_public f
  JOIN skolske_obvody.districts d ON d.id = f.district_id
  ORDER BY d.name, f.condition_code""")
for r in rows:
    print(f"  {r['name'][:38]:38} {r['condition_code']:6} sev={r['severity']:8} demo={r['is_demo']}")

print("\n=== MAP FEATURES — district -> composition_color ===")
mf = query_sql("SELECT name, composition_color FROM skolske_obvody.district_map_features ORDER BY composition_color, name")
for r in mf:
    print(f"  {r['composition_color']:7} {r['name'][:50]}")

print("\n=== SCORECARD spot-check: Bajkalská (RED) full row ===")
sc = query_sql("""
  SELECT condition_code, value, confidence, data_completeness, is_mock
  FROM skolske_obvody.district_scorecard
  WHERE district_name = 'Základná škola, Bajkalská č. 29'
  ORDER BY (CASE condition_code WHEN 'S1' THEN 1 WHEN 'S2' THEN 2 WHEN 'S3' THEN 3
    WHEN 'Pa' THEN 4 WHEN 'Pb' THEN 5 WHEN 'Pc' THEN 6 WHEN 'Pd' THEN 7
    WHEN 'Pe' THEN 8 WHEN 'Pf' THEN 9 ELSE 10 END)""")
for r in sc:
    print(f"  {r['condition_code']:6} {r['value']:8} conf={r['confidence']} compl={r['data_completeness']} mock={r['is_mock']}")
