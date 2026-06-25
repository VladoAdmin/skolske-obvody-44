// Condition code → SK label + sort order + tooltip description
// Mirrors SQL CASE in district_scorecard view. Used as fallback/TS safety net when view column is unavailable.

export const CONDITION_LABELS_SK: Record<string, { label: string; order: number; description: string }> = {
  S1: { label: 'Š1 — Adresy žiakov a obvod', order: 1, description: 'Mapa adries všetkých žiakov musí spadať do správneho obvodu. Bez Registra adries to overiť nevieme — preto Š1 zatiaľ ostáva NEÚPLNÉ.' },
  S2: { label: 'Š2 — Topologické pokrytie', order: 2, description: 'Plocha obce musí byť pokrytá obvodmi bez medzier a bez prekryvov. Overujeme cez OSM geometriu.' },
  S3: { label: 'Š3 — Kompozícia obvodu', order: 3, description: 'Jeden obvod patrí jednej škole. Ak je v obvode viac škôl, ide o porušenie zákona.' },
  Pa: { label: 'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km', order: 4, description: 'Žiak 1. stupňa nemá mať školu vzdialenú viac než 2 km vzdušnou čiarou.' },
  Pb: { label: 'P-b — Pešia trasa', order: 5, description: 'Reálna pešia trasa nemá presahovať 30 minút (cca 2,5 km mestskou cestou).' },
  Pc: { label: 'P-c — MHD dostupnosť', order: 6, description: 'Ak chodí žiak MHD-kou, prestup nesmie byť potrebný viac než raz. Ilustratívny indikátor — nezáväzný.' },
  Pd: { label: 'P-d — Bariéry (cesty, koľaje)', order: 7, description: 'Trasa z domu do školy neprekračuje rušnú cestu bez priechodu ani železnicu bez podchodu.' },
  Pe: { label: 'P-e — Sociálny kontext (Atlas MRK)', order: 8, description: 'Obvod nevylučuje deti z marginalizovaných komunít. Kontrolujeme voči Atlasu MRK — ide o signál, nie verdikt.' },
  Pf: { label: 'P-f — Demografia detí', order: 9, description: 'Demografická prognóza počtu detí v obvode súvisí s kapacitou školy. Odhadované z dát ŠTATSR.' },
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
