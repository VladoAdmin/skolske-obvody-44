# Deploy runbook — Sprint C (Stage 8 cc-pipeline-v2)

Spúšťa F2 po Haiku testy GREEN + GPT-5.5 verify ≥ APPROVE_WITH_CHANGES.

## Pred-flight

```bash
cd projects/skolske-obvody-44
git status --short            # musí byť clean
git log --oneline -5          # over Sonnet + Haiku commits
git rev-parse HEAD            # commit ktorý ide na preview
```

## Vercel preview deploy

```bash
# 1. potvrď env
vercel env ls 2>/dev/null | grep -qE "NEXT_PUBLIC_SUPABASE_URL.*Production" || {
  echo "Need to add Vercel env vars"
  vercel env add NEXT_PUBLIC_SUPABASE_URL preview < <(echo "$NEXT_PUBLIC_SUPABASE_URL")
  vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY preview < <(echo "$NEXT_PUBLIC_SUPABASE_ANON_KEY")
}

# 2. deploy
vercel deploy --yes --no-clipboard 2>&1 | tee /tmp/sprint-c-deploy.log
PREVIEW_URL=$(grep -Eo 'https://[a-z0-9.-]+\.vercel\.app' /tmp/sprint-c-deploy.log | tail -1)
echo "$PREVIEW_URL" > /tmp/sprint-c-preview.url
```

## Post-deploy smoke

```bash
for path in / /map /findings /municipalities /o-metodike; do
  curl -fsS -o /dev/null -w "%{http_code} $path\n" "$PREVIEW_URL$path"
done
# All MUST be 200
```

## Screenshoty pre Vlada

```bash
mkdir -p /tmp/sprint-c-shots
npx playwright screenshot "$PREVIEW_URL/map" /tmp/sprint-c-shots/map.png --viewport-size=1280,720 --full-page=false
# pick first district id from a known seeded/real district
DID=$(curl -fsS -H "apikey: $NEXT_PUBLIC_SUPABASE_ANON_KEY" -H "Accept-Profile: skolske_obvody" "$NEXT_PUBLIC_SUPABASE_URL/rest/v1/district_map_features?select=id&limit=1" | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
npx playwright screenshot "$PREVIEW_URL/districts/$DID" /tmp/sprint-c-shots/district.png --viewport-size=1280,720
npx playwright screenshot "$PREVIEW_URL/findings" /tmp/sprint-c-shots/findings.png --viewport-size=1280,720
```

## Vlado deliverables (Telegram)

V správe zahrnúť:
- Preview URL
- 3 screenshoty (`/map`, `/districts/...`, `/findings`)
- Branch + last commit SHA
- Známe limity (z PRD §8, PLAN §10)
- Známe BLOCKERS (z `docs/sprint-C/BLOCKERS.md`)
- Skipped tests reason (z Haiku reportu)

## Ak deploy zlyhá

1. Skontroluj `vercel.json` v repo + env vars.
2. Skontroluj build log v Vercel dashboarde.
3. Ak chýba env var → vytvor cez `vercel env add`.
4. Retry max 2×.
5. Pri pretrvávajúcom failei → BLOCKER do `docs/sprint-C/BLOCKERS.md` + F2 alert Vladovi s root cause.

## Žiadny merge

Sprint C končí preview URL-om. Merge na `main` robí Vlado po manuálnom QA.
