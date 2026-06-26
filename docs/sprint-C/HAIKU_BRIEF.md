# Brief pre Haiku tester (Stage 6 cc-pipeline-v2)

**Spúšťa F2 po dokončení Sonnet CODE stage.** Pracuješ v `projects/skolske-obvody-44/` na branchi `feat/sprint-c-frontend`.

## Tvoja rola
Napíš a spusti unit + integration + E2E testy podľa **PLAN.md §5**. Neimplementuj kód — Sonnet má ho hotový. Iba testuj a verifikuj, že kód spĺňa PRD/PLAN kontrakt. Pri zlyhaní testu → 3× retry s lokálnym fixom; pri 4. zlyhaní → BLOCKER do `docs/sprint-C/BLOCKERS.md`.

## Povinné čítanie pred testami
1. `docs/sprint-C/PRD.md` v3
2. `docs/sprint-C/PLAN.md` v3 (najmä §5.1 + 5.2 + 5.3)
3. Sonnet final report z predchádzajúceho stage (file: `docs/sprint-C/SONNET_REPORT.md` ak vytvorený, inak `git log feat/sprint-1-ingest..feat/sprint-c-frontend`)
4. `tests/fixtures/composition.json` + `tests/fixtures/seed_sprint_c.sql`

## Krok 1: build + lint
```bash
cd projects/skolske-obvody-44
npm run lint
npm run build
```
Obe MUSIA prejsť. Ak nie → 3× pokus o fix → BLOCKER + STOP.

## Krok 2: staging DB setup (ak je k dispozícii)
```bash
if [ -n "$STAGING_DATABASE_URL" ]; then
  psql "$STAGING_DATABASE_URL" -f db/migrations/0001_init.sql
  psql "$STAGING_DATABASE_URL" -f db/migrations/0010_sprint_c_read_views.sql
  psql "$STAGING_DATABASE_URL" -f tests/fixtures/seed_sprint_c.sql
fi
```
Ak `$STAGING_DATABASE_URL` chýba → integration testy a E2E sa preskočia so značkou `SKIPPED:no-staging-db`; čisté unit testy (5–8 podľa PLAN §5.2) bežia vždy.

## Krok 3: REST exposure check (PLAN §12)
```bash
curl -fsS \
  -H "apikey: $STAGING_ANON_KEY" \
  -H "Accept-Profile: skolske_obvody" \
  "$STAGING_SUPABASE_URL/rest/v1/engine_metadata?select=last_engine_run_at" \
  || echo BLOCKER
```

## Krok 4: Negative test — raw tables NOT readable (PLAN §2.5)
```bash
# expect HTTP 401/403 or 200 with empty body — NOT a successful row dump
HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "apikey: $STAGING_ANON_KEY" -H "Accept-Profile: skolske_obvody" \
  "$STAGING_SUPABASE_URL/rest/v1/verdicts?select=*")
[ "$HTTP" = "401" ] || [ "$HTTP" = "403" ] || fail "verdicts raw table is readable (HTTP $HTTP)"
```
Rovnaké pre `districts`, `schools`, `findings`, `municipalities`.

## Krok 5: Unit + integration testy (Vitest)
Implementuj a spusti 8 testov per PLAN §5.2. Skip integration ak no-staging-db.

## Krok 6: E2E (Playwright)
4 scenáre per PLAN §5.3. Skip ak no-staging-db.

## Krok 7: Screenshoty
```bash
mkdir -p tests/screenshots
# Po štarte dev servera ALEBO po deploy preview (toto stage ešte nedeploy)
# Tu len skontroluj, že Playwright vie spraviť screenshot lokálne:
npx playwright screenshot http://localhost:3000/map tests/screenshots/map.png --viewport-size=1280,720
npx playwright screenshot "http://localhost:3000/districts/<seed_uuid_z_fixture>" tests/screenshots/district.png --viewport-size=1280,720
```

## Krok 8: Commit a report
Commit: `test(sprint-c): unit + integration + e2e tests for scope, sanitization, allowlist, parity`

Final report obsahuje:
- Test counts (passed / failed / skipped)
- Skipped tests dôvod (vždy explicitne, nie ticho)
- BLOCKERS.md obsah (ak vznikol)
- Screenshoty (paths)
- Build/lint status
- Branch + commit SHA

## Pravidlá
- Nikdy nemodifikuj Sonnet code okrem prípadu, že test odhalil bug — vtedy fixni a opíš v reporte.
- Žiadne nové scope features.
- Žiadny merge, žiadny push.
