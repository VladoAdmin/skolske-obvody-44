# VZN ↔ Register adries validation report

_Generated: 2026-06-26T19:15:33.037994+00:00_

Cross-check of every VZN-assigned Prešov street (`skolske_obvody.vzn_street_ranges`, joined to Prešov districts) against the authoritative City-of-Prešov **Register adries a stavieb** (`skolske_obvody.register_adries`, 16307 records). Diagnosis only — no district or geometry data was changed.

## Headline

- VZN streets (Prešov, distinct): **409**
- Register streets (distinct): **401**
- Matched (EXACT + NORMALIZED): **391** (95.6%)
- NOT FOUND (likely artifacts): **13**
- FUZZY near-matches (need a human look): **5**

## Counts per class

| Class | Count | Meaning |
|---|---:|---|
| EXACT | 368 | byte-identical to a register street |
| NORMALIZED | 23 | matches after case/diacritics/whitespace/`ulica`/`č.` folding |
| FUZZY | 5 | no exact/normalized match; closest register street ≥ 0.8 |
| NOT FOUND | 13 | no match, closest < 0.8 — trust problem |
| **TOTAL** | **409** | |

## NOT FOUND — VZN streets absent from the register

These are the streets a downstream consumer cannot anchor to an authoritative address. Each is a candidate scrape/geocode artifact or a register gap to resolve before geocoding.

| VZN street | Closest register street | Score |
|---|---|---:|
| Dlhá | Dúhová | 0.6 |
| Gorazdova | Kotrádova | 0.778 |
| Koceľova | Chmeľová | 0.75 |
| Ku Škáre | Ku vykládke | 0.632 |
| Liesková | Slivková | 0.75 |
| Pražská | Popradská | 0.75 |
| Priemyselná | Pri Delni | 0.6 |
| Rastislavova | Bratislavská | 0.75 |
| Račia | Srnčia | 0.727 |
| Riečna | Hraničná | 0.714 |
| Rybníčky | Banícka | 0.667 |
| Tulipánová | Lipová | 0.75 |
| Ulica Jána Lazoríka | Jána Nováka | 0.667 |

## FUZZY — near-matches to verify

Likely the same street under a spelling/variant difference. A human should confirm each before treating it as matched.

| VZN street | Closest register street | Score |
|---|---|---:|
| Gerlachovská | Terchovská | 0.818 |
| Pribinova | Rubínová ulica | 0.824 |
| L. Novomestského | L. Novomeského | 0.929 |
| Jaboňová | Jabloňová | 0.941 |
| Herľanská | Herlianska | 0.947 |

## NORMALIZED — matched only after folding

Matched, but the raw spellings differ (diacritics, `ulica`/`č.`, whitespace). Safe, listed for transparency.

| VZN street | Register street |
|---|---|
| Bezrúčova | Bezručova |
| Brezova | Brezová |
| Jelšova | Jelšová |
| K Starej Tehelni | K Starej tehelni |
| Mätová ulica | Mätová |
| Pod Dubom | Pod dubom |
| Poľovnícka ulica | Poľovnícka |
| Pőschlova | Pöschlova |
| Rezbárska ulica | Rezbárska |
| Slánska | Slanská |
| Sovia ulica | Sovia |
| Tehelná. | Tehelná |
| Ulica Štefana Náhalku. | Štefana Náhalku |
| Važecká. | Važecká |
| Veselá. | Veselá |
| Veterná. | Veterná |
| Višňova. | Višňová |
| Weberova. | Weberova |
| Zajačia. | Zajačia |
| Zimná. | Zimná |
| Zlatnícka. | Zlatnícka |
| Zlatobanská. | Zlatobanská |
| Západná. | Západná |

