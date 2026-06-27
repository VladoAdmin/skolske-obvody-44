# AI-driven UAT report — Školské obvody § 44

- Spustené: `2026-06-27T04:55:27.978090+00:00`
- Cieľ (BASE_URL): `https://skolske-obvody-44.vercel.app`
- AI sudca: OpenAI `gpt-4o-mini` (≤ 1 volanie / flow)
- Prehliadač: system Chrome (`/usr/bin/google-chrome-stable`), iPhone + desktop viewport

## Súhrn: 10/10 PASS, 0 FAIL

### Verdikt: **DEMO-READY** — všetky flow prešli.

---

## [PASS ✅] Domov / Prehľad + navigácia — _iphone_

**Overené fakty:**

- OK: stránka má titulok: 'Kontrola § 44 — Školské obvody'
- OK: obsah o školských obvodoch / § 44 je prítomný
- OK: nav odkaz 'Mapa PSK' (/map) je v DOM
- OK: nav odkaz 'Register nálezov' (/findings) je v DOM
- OK: navigácia na /map funguje

**Chyby v konzole prehliadača:**

- `Failed to fetch RSC payload for https://skolske-obvody-44.vercel.app/districts/022b88de-8f54-43fd-9a37-b165102db9f8. Falling back to browser navigation. TypeError: Failed to fetch
    at f (https://skolske-obvody-44.vercel.app/_next/static/chunks/117-34552b37c8527ac6.js:1:45433)
    at https://skols`

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka pre úradníka samosprávy obsahuje základné informácie a navigačné odkazy, ktoré sú prítomné a funkčné. Avšak, výskyt chyby v konzole prehliadača, konkrétne "Failed to fetch RSC payload", naznačuje, že niektoré funkcie nemusia fungovať správne, čo môže ovplyvniť použiteľnosť. Odporúčam túto chybu opraviť, aby sa zabezpečila plná funkčnosť a bezproblémová navigácia.

_Screenshot: `tools/ai-uat/screenshots/home-iphone.png` (gitignored)._

---

## [PASS ✅] Mapa PSK — vykreslenie + vrstvy + declutter — _iphone_

**Overené fakty:**

- OK: preklik z prehľadu SR do PSK (Prešov) zobrazil obvody
- OK: obvody vykreslené (24 SVG polygónov)
- OK: ovládač vrstiev (layer control) je prítomný
- OK: default ZAPNUTÉ: Obvody + Školy (čistý high-level pohľad)
- OK: MRK vrstva je v ovládači a je VYPNUTÁ (declutter)
- OK: expert vrstvy sú v ovládači a VYPNUTÉ (declutter)

_Žiadne chyby v konzole._

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka s mapou PSK je pre úradníka samosprávy plne použiteľná, keďže všetky overené funkcie fungujú správne a bez chýb. Preklik z prehľadu SR do PSK zobrazuje obvody, ovládač vrstiev je prítomný a predvolené nastavenia sú vhodné pre prehľad. Navyše, absencia chýb v konzole prehliadača potvrdzuje stabilitu aplikácie. Všetko je v poriadku.

_Screenshot: `tools/ai-uat/screenshots/map-iphone.png` (gitignored)._

---

## [PASS ✅] Register nálezov — filtre (SK) + klik na riadok — _iphone_

**Overené fakty:**

- OK: filter má slovenský popis 'Závažnosť'
- OK: filter má slovenský popis 'Stav'
- OK: filter má slovenský popis 'Podmienka'
- OK: filter závažnosti je prítomný
- OK: po výbere ostáva trigger slovenský: 'Vysoká'
- OK: výber filtra sa premietol do URL (severity=high)
- OK: v registri sú viditeľné nálezy na kliknutie
- OK: klik na celý riadok naviguje na detail obvodu (6f4bee27…)

_Žiadne chyby v konzole._

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka Register nálezov pre úradníka samosprávy je plne funkčná a použiteľná. Všetky filtre sú správne označené v slovenčine a ich funkčnosť je potvrdená. Navigácia na detail obvodu po kliknutí na riadok funguje bez problémov. Nezaznamenali sme žiadne chyby v konzole prehliadača, čo potvrdzuje stabilitu aplikácie.

_Screenshot: `tools/ai-uat/screenshots/findings-iphone.png` (gitignored)._

---

## [PASS ✅] Detail obvodu — mapa+text, register adries, indikátory, AI, DEMO — _iphone_

**Overené fakty:**

- OK: mapa je nad textom (scorecard pod mapou)
- OK: riadok 'Autoritatívny register adries … mesta Prešov' sa vykreslil
- OK: indikátor '⚠ Geometrický nesúlad' sa vykreslil
- OK: blok '✦ Vysvetlenie (generované AI)' sa vykreslil pri náleze
- OK: DEMO odznaky sú prítomné pri sekundárnych indikátoroch (6)
- OK: semafor (RED/ORANGE/GREEN) je vykreslený (9 buniek)
- OK: verdiktové bunky (PASS/FAIL) sú samostatné, nie DEMO
- OK: semafor + verdikt sú REAL (DEMO len pri sekundárnych P-* indikátoroch)

_Žiadne chyby v konzole._

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka pre úradníka samosprávy je plne funkčná a použiteľná. Všetky overené prvky sa správne vykreslili a neboli zistené žiadne chyby v konzole prehliadača. Používateľské rozhranie je prehľadné a informácie sú jasne prezentované.

_Screenshot: `tools/ai-uat/screenshots/district-iphone.png` (gitignored)._

---

## [PASS ✅] Klik na nález kreslí na mape (highlight/route) — _iphone_

**Overené fakty:**

- OK: preklik do PSK pred klikaním na nálezy
- OK: panel nálezov má klikateľné položky (225)
- OK: klik na nález #0 prekreslil mapu: trasa (route polyline) (routes 0->1, total 27->28)
- OK: klik na nález nakreslil niečo na mape (highlight alebo trasa)

_Žiadne chyby v konzole._

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka pre úradníka samosprávy je použiteľná a funkčná, keďže všetky overené fakty sú v poriadku. Preklik do PSK a klikateľné položky na paneli nálezov fungujú správne, a interakcia s nálezmi na mape je bezchybne zobrazená. Chýbajúce chyby v konzole prehliadača potvrdzujú, že aplikácia je stabilná.

_Screenshot: `tools/ai-uat/screenshots/findingclick-iphone.png` (gitignored)._

---

## [PASS ✅] Domov / Prehľad + navigácia — _desktop_

**Overené fakty:**

- OK: stránka má titulok: 'Kontrola § 44 — Školské obvody'
- OK: obsah o školských obvodoch / § 44 je prítomný
- OK: nav odkaz 'Mapa PSK' (/map) je v DOM
- OK: nav odkaz 'Register nálezov' (/findings) je v DOM
- OK: navigácia na /map funguje

**Chyby v konzole prehliadača:**

- `Failed to fetch RSC payload for https://skolske-obvody-44.vercel.app/districts/45b113f3-3614-46ed-b9bf-67289a306670. Falling back to browser navigation. TypeError: Failed to fetch
    at f (https://skolske-obvody-44.vercel.app/_next/static/chunks/117-34552b37c8527ac6.js:1:45433)
    at https://skols`
- `Failed to fetch RSC payload for https://skolske-obvody-44.vercel.app/districts/022b88de-8f54-43fd-9a37-b165102db9f8. Falling back to browser navigation. TypeError: Failed to fetch
    at f (https://skolske-obvody-44.vercel.app/_next/static/chunks/117-34552b37c8527ac6.js:1:45433)
    at https://skols`
- `Failed to fetch RSC payload for https://skolske-obvody-44.vercel.app/districts/61724cfb-2093-4f19-a47e-92b0b7e12429. Falling back to browser navigation. TypeError: Failed to fetch
    at f (https://skolske-obvody-44.vercel.app/_next/static/chunks/117-34552b37c8527ac6.js:1:45433)
    at https://skols`

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka pre úradníka samosprávy má niekoľko pozitívnych aspektov, ako je správny titulok a prítomnosť obsahu o školských obvodoch. Avšak, výskyt chýb v konzole prehliadača, konkrétne problémy s načítaním RSC payloadov, naznačuje, že niektoré funkcie nemusia fungovať správne. Tieto chyby môžu viesť k zhoršenej použiteľnosti a frustrácii pri navigácii. Odporúča sa opraviť tieto technické problémy, aby bola obrazovka plne funkčná a užívateľsky prívetivá.

_Screenshot: `tools/ai-uat/screenshots/home-desktop.png` (gitignored)._

---

## [PASS ✅] Mapa PSK — vykreslenie + vrstvy + declutter — _desktop_

**Overené fakty:**

- OK: preklik z prehľadu SR do PSK (Prešov) zobrazil obvody
- OK: obvody vykreslené (24 SVG polygónov)
- OK: ovládač vrstiev (layer control) je prítomný
- OK: default ZAPNUTÉ: Obvody + Školy (čistý high-level pohľad)
- OK: MRK vrstva je v ovládači a je VYPNUTÁ (declutter)
- OK: expert vrstvy sú v ovládači a VYPNUTÉ (declutter)

_Žiadne chyby v konzole._

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka pre úradníka samosprávy je plne funkčná a použiteľná. Všetky overené faktory sú v poriadku, vrátane správneho vykreslenia obvodov a prítomnosti ovládača vrstiev. Neexistujú žiadne chyby v konzole prehliadača, čo potvrdzuje stabilitu aplikácie. Celkovo je použiteľnosť tejto obrazovky na vysokej úrovni.

_Screenshot: `tools/ai-uat/screenshots/map-desktop.png` (gitignored)._

---

## [PASS ✅] Register nálezov — filtre (SK) + klik na riadok — _desktop_

**Overené fakty:**

- OK: filter má slovenský popis 'Závažnosť'
- OK: filter má slovenský popis 'Stav'
- OK: filter má slovenský popis 'Podmienka'
- OK: filter závažnosti je prítomný
- OK: po výbere ostáva trigger slovenský: 'Vysoká'
- OK: výber filtra sa premietol do URL (severity=high)
- OK: v registri sú viditeľné nálezy na kliknutie
- OK: klik na celý riadok naviguje na detail obvodu (6f4bee27…)

_Žiadne chyby v konzole._

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka "Register nálezov" je pre úradníka samosprávy použiteľná a funkčná. Všetky filtre sú správne označené v slovenčine a ich funkčnosť je potvrdená. Navigácia na detail obvodu po kliknutí na riadok funguje bez problémov. Nezaznamenali sme žiadne chyby v konzole prehliadača, čo potvrdzuje stabilitu aplikácie.

_Screenshot: `tools/ai-uat/screenshots/findings-desktop.png` (gitignored)._

---

## [PASS ✅] Detail obvodu — mapa+text, register adries, indikátory, AI, DEMO — _desktop_

**Overené fakty:**

- OK: mapa je nad textom (scorecard pod mapou)
- OK: riadok 'Autoritatívny register adries … mesta Prešov' sa vykreslil
- OK: indikátor '⚠ Geometrický nesúlad' sa vykreslil
- OK: blok '✦ Vysvetlenie (generované AI)' sa vykreslil pri náleze
- OK: DEMO odznaky sú prítomné pri sekundárnych indikátoroch (6)
- OK: semafor (RED/ORANGE/GREEN) je vykreslený (9 buniek)
- OK: verdiktové bunky (PASS/FAIL) sú samostatné, nie DEMO
- OK: semafor + verdikt sú REAL (DEMO len pri sekundárnych P-* indikátoroch)

_Žiadne chyby v konzole._

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka pre detail obvodu je plne funkčná a všetky overené prvky sa vykreslili správne. Mapa je umiestnená nad textom, čo zlepšuje prehľadnosť, a všetky indikátory a vysvetlenia sú zobrazené bez problémov. Nezaznamenali sa žiadne chyby v konzole prehliadača, čo potvrdzuje stabilitu aplikácie. Celkovo je použiteľnosť tejto obrazovky pre úradníka samosprávy na vysokej úrovni.

_Screenshot: `tools/ai-uat/screenshots/district-desktop.png` (gitignored)._

---

## [PASS ✅] Klik na nález kreslí na mape (highlight/route) — _desktop_

**Overené fakty:**

- OK: preklik do PSK pred klikaním na nálezy
- OK: panel nálezov má klikateľné položky (225)
- OK: klik na nález #0 prekreslil mapu: trasa (route polyline) (routes 0->1, total 27->28)
- OK: klik na nález nakreslil niečo na mape (highlight alebo trasa)

_Žiadne chyby v konzole._

**AI hodnotenie použiteľnosti (po slovensky):**

> Obrazovka pre úradníka samosprávy je plne funkčná a použiteľná. Všetky overené faktory sú v poriadku, vrátane prekliku do PSK a správneho zobrazenia nálezov na mape. Nezaznamenali sa žiadne chyby v konzole prehliadača, čo potvrdzuje stabilitu aplikácie. Celkovo je použiteľnosť tejto obrazovky na vysokej úrovni.

_Screenshot: `tools/ai-uat/screenshots/findingclick-desktop.png` (gitignored)._

---
