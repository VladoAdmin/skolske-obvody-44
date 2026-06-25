V2 blockery sú v zásade vyriešené: slug fallback je už cez `name` + `UPDATE`, sanity check je mimo migrácie, staging `_test` konflikt odstránený, scope test pre `district_compositions` ide cez join/psql, fixture UUID sú deterministické a REST exposure check pribudol.

Zostávajú však **reálne zmeny pred implementáciou**, nie dôvod na ďalší BLOCK:

1. **Kontradikcia v `district_scorecard` kontrakte**
   - §2.4 správne hovorí, že view má mať `condition_label_sk` a `condition_order`.
   - Hneď pod tým ale plán tvrdí: „DB `district_scorecard` vystavuje len `condition_code`“ a §4.4 sortuje cez TS mapu s komentárom „SQL no longer returns it“.
   - Toto treba odstrániť. DB view musí vystavovať `condition_label_sk` + `condition_order`; frontend ich má len fallbackovo.

2. **Scope test pre `findings_public` je stále nejasný**
   - View kontrakt neuvádza `municipality_id`, test ho miestami očakáva.
   - Buď pridajte `municipality_id` do `findings_public`, alebo testujte cez `district_id -> districts` join cez psql, rovnako ako pri `district_compositions`.

3. **`host_in_allowlist()` ukážka nie je úplne robustná**
   - Regex/parsing má byť case-insensitive aj pre `HTTPS://...`; doplniť `lower(url)` pred parsovaním alebo regex flag.
   - Zároveň odporúčam explicitné zátvorky okolo `AND/OR`, aby nevznikla bezpečnostná nejednoznačnosť.

4. **Anon raw-table leak treba negatívne overiť**
   - Plán hovorí „no grants“, ale bezpečnejšie je v migrácii explicitne `REVOKE SELECT` na raw tabuľky od `anon` alebo aspoň REST test, že raw tabuľky vracajú 401/403.

Nie je tu už systémový blocker typu rozbitý staging flow alebo nemožná migrácia. Po oprave vyššie uvedených kontradikcií je plán implementovateľný.

VERDICT: APPROVE_WITH_CHANGES — opraviť najmä `district_scorecard` kontradikciu a scope/allowlist bezpečnostné detaily pred kódom.
