### Blocker

- **PII sanitizácia telefónov v `sanitize_evidence()` nespĺňa kontrakt.**  
  Aktuálny regex:

  ```sql
  '\+?\d{2,4}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2,3}'
  ```

  nepokryje bežné slovenské formáty typu:

  ```text
  0903 123 456
  0911-222-333
  02 1234 5678
  ```

  Tieto hodnoty môžu prejsť do verejných view `district_scorecard.evidence_public_text` a `findings_public.evidence_public_text`. Keďže PRD explicitne vyžaduje strip telefónov a ide o verejný read-layer, je to deploy blocker.

  Potrebné pred merge/deploy:
  - rozšíriť tel. regex na lokálne SK formáty aj `+421`,
  - doplniť minimálne SQL/unit test pre email + tel + RČ sanitizáciu.

VERDICT: BLOCK + verejné views môžu publikovať telefónne čísla napriek PII sanitization kontraktu.
