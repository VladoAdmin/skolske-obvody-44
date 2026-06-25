Žiadne zostávajúce hard blockery k overovanej oprave.

- Regex pokrýva testované SK mobily, pevné linky aj `+421` / `00421`.
- Funkcia `sanitize_evidence` je v migrácii `0010` upravená.
- Integračný test `sanitize-evidence.test.ts` bol pridaný a podľa dôkazu prešiel proti prod Supabase.

VERDICT: APPROVE — fix SK tel sanitizácie je overený bez hard blockerov.
