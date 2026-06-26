## Overenie v2 blockerov

### BLOCKER 1 — Public views hard-scope na Prešov  
**Vyriešené.** PRD v3 explicitne zavádza hard rule: všetky public views sú SQL-scoped na Prešov a frontend filter už nie je považovaný za bezpečnostnú hranicu. Query patterns volajú views bez `.eq('municipality_slug', ...)`, čo je správne.

**Nutná úprava pred implementáciou:** AC 1b musí testovať všetky anon-grantnuté dátové views, teda doplniť minimálne:
- `district_compositions`
- `engine_metadata`

Inak je scope pravidlo správne definované, ale test coverage nie je úplná.

---

### BLOCKER 2 — Public evidence/provenance sanitizácia  
**V podstate vyriešené.** PRD v3 nahrádza raw `evidence_text` za `evidence_public_text`, zavádza DB sanitizáciu, truncation, regex redakciu email/tel/RČ a SQL allowlist pre `provenance_source`. `district_scorecard` už nemá publikovať raw evidence. To odstraňuje hlavný leak z v2.

**Nutné opravy pred implementáciou:**
1. V §3.5 je stále text: `evidence_text (truncated 200, plný v tooltipe)` — toto je nebezpečne nejednoznačné. Musí byť zmenené na `evidence_public_text`, bez „plného“ raw tooltipu.
2. AC 1c testuje sanitizáciu iba pre `findings_public`; treba doplniť rovnaký test aj pre `district_scorecard`.
3. AC 1d testuje allowlist iba cez `district_scorecard`; treba doplniť aj `findings_public`, keďže §5.5 hovorí, že `provenance_source` sa sanitizuje v oboch.

---

## Zostávajúce reálne blokery

Nevidím nový fundamentálny blocker architektúry ani bezpečnostného modelu. Zostávajú však malé konzistenčné zmeny v PRD/AC, ktoré treba spraviť pred implementáciou, aby sa nevrátili pôvodné v2 chyby cez nejednoznačný text alebo netestovaný view.

VERDICT: APPROVE_WITH_CHANGES — V2 blokery sú architektonicky vyriešené, ale treba doplniť scope/sanitization test coverage a odstrániť zmienku o raw `evidence_text`/„plnom“ tooltipe.
