// Condition code → SK label + sort order + tooltip description
// Mirrors SQL CASE in district_scorecard view. Used as fallback/TS safety net when view column is unavailable.

export const CONDITION_LABELS_SK: Record<string, { label: string; order: number; description: string }> = {
  S1: { label: 'Š1 — Adresy žiakov a obvod', order: 1, description: 'Adresy všetkých žiakov musia patriť do správneho obvodu. Kým nemáme Register adries, nevieme to overiť, preto Š1 zatiaľ ostáva NEÚPLNÉ.' },
  S2: { label: 'Š2 — Topologické pokrytie', order: 2, description: 'Obvody musia pokryť celé územie obce bez medzier a bez prekryvov. Overujeme to na geometrii z OpenStreetMap.' },
  S3: { label: 'Š3 — Kompozícia obvodu', order: 3, description: 'Každý obvod patrí jednej škole. Ak je v jednom obvode viac škôl, zákon je porušený.' },
  Pa: { label: 'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km', order: 4, description: 'Žiak prvého stupňa by nemal mať školu vzdialenú viac ako 2 km vzdušnou čiarou.' },
  Pb: { label: 'P-b — Pešia trasa', order: 5, description: 'Skutočná pešia trasa by nemala trvať viac ako 30 minút, čo je v meste asi 2,5 km.' },
  Pc: { label: 'P-c — MHD dostupnosť', order: 6, description: 'Ak žiak chodí mestskou dopravou, nemal by potrebovať viac ako jeden prestup. Tento ukazovateľ je len ilustratívny a nezáväzný.' },
  Pd: { label: 'P-d — Bariéry (cesty, koľaje)', order: 7, description: 'Cesta z domu do školy by nemala prechádzať cez rušnú cestu bez priechodu ani cez železnicu bez podchodu.' },
  Pe: { label: 'P-e — Sociálny kontext (Atlas MRK)', order: 8, description: 'Obvod by nemal vyčleňovať deti z marginalizovaných komunít. Porovnávame ho s Atlasom MRK. Je to upozornenie, nie verdikt.' },
  Pf: { label: 'P-f — Demografia detí', order: 9, description: 'Počet detí v obvode súvisí s kapacitou školy. Ak zapísaných žiakov prekročí kapacitu školy, ide o signál preťaženia.' },
  JAZYK: { label: 'Podnet nad rámec § 44 (jazyk)', order: 10, description: 'Vyučovací jazyk menšiny NIE je podmienkou § 44. Ak pridelená škola vyučuje len v menšinovom jazyku, žiaci so slovenčinou musia dochádzať inam. Tento podnet je mimo § 44 a NEVSTUPUJE do semaforu.' },
}

export function getConditionLabel(code: string): string {
  return CONDITION_LABELS_SK[code]?.label ?? code
}

export function getConditionOrder(code: string): number {
  return CONDITION_LABELS_SK[code]?.order ?? 99
}

export function getConditionDescription(code: string): string {
  return CONDITION_LABELS_SK[code]?.description ?? ''
}
