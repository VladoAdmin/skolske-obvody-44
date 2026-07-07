// Condition code → SK label + sort order + tooltip description
// Mirrors SQL CASE in district_scorecard view. Used as fallback/TS safety net when view column is unavailable.

// Legal citations in these texts are audited against the verbatim law text —
// see docs/legal-audit-44.md (allowlist) and tests/test_legal_citations.py.
// Thresholds (2 km, 30 min, prestupy) are demo methodological parameters,
// never legal limits: § 44 ods. 8 lists factors without numbers.
export const CONDITION_LABELS_SK: Record<string, { label: string; order: number; description: string }> = {
  S1: { label: 'Š1 — Adresy žiakov a obvod', order: 1, description: 'Každá adresa má byť pokrytá práve jedným obvodom podľa uličného zoznamu VZN (§ 44 ods. 1). Meriame dve veci: adresy ležiace v geometrii iného obvodu, než im určuje VZN (prekryv priradenia), a adresy bez akéhokoľvek obvodu (medzera v pokrytí).' },
  S2: { label: 'Š2 — Neprekrývanie obvodov', order: 2, description: 'Tá istá adresa (ulica + číslo) nesmie byť priradená dvom obvodom rovnakého druhu školy — obvody sa nesmú prekrývať (§ 44 ods. 1 a 7). Zdieľané hraničné ulice nie sú nález; nález je len duplicitná plná adresa.' },
  S3: { label: 'Š3 — Kompozícia obvodu', order: 3, description: 'V každom obvode sa určuje práve jedna škola (§ 44 ods. 1). Ak je v jednom obvode viac verejných škôl rovnakého druhu, zákon je porušený.' },
  Pa: { label: 'P-a — Vzdialenosť (vzdušná čiara)', order: 4, description: 'Vzdialenosť adresy k pridelenej škole meraná vzdušnou čiarou — aproximácia, reálna pešia trasa (P-b) je spravidla dlhšia. Zákon číselný limit neurčuje; vzdialenosť je jedno z hľadísk (§ 44 ods. 8 písm. b)). Prah 2 km je metodický parameter dema.' },
  Pb: { label: 'P-b — Pešia trasa', order: 5, description: 'Skutočná pešia trasa do školy. Prahy 30 minút / 2 km / 4 km sú metodické parametre dema — zákon limit neurčuje, vzdialenosť je hľadisko podľa § 44 ods. 8 písm. b).' },
  Pc: { label: 'P-c — MHD dostupnosť', order: 6, description: 'Dostupnosť školy mestskou dopravou — dopravná infraštruktúra obce je hľadisko podľa § 44 ods. 8 písm. c). Prah „viac ako jeden prestup“ je metodický parameter dema, nie zákonná požiadavka.' },
  Pd: { label: 'P-d — Bariéry (cesty, koľaje)', order: 7, description: 'Metodický indikátor bezpečnosti trasy (rušná cesta bez priechodu, železnica bez podchodu) BEZ priamej opory v § 44 — zákon bariéry nespomína. Nález P-d nikdy nie je porušením zákona.' },
  Pe: { label: 'P-e — Sociálny kontext (Atlas MRK)', order: 8, description: 'Pri určovaní obvodov sa zohľadňuje dodržiavanie zákazu segregácie (§ 44 ods. 8 písm. e)). Porovnávame obvod s Atlasom MRK. Je to upozornenie, nie verdikt.' },
  Pf: { label: 'P-f — Demografia detí', order: 9, description: 'Počet zapísaných žiakov voči kapacite školy — kapacita budov je hľadisko podľa § 44 ods. 8 písm. a). Ak zápis prekročí kapacitu, ide o analytický signál preťaženia, nie zákonný verdikt.' },
  JAZYK: { label: 'Jazykový podnet (mimo semaforu)', order: 10, description: 'Právo na vzdelávanie v štátnom jazyku alebo jazyku menšiny je hľadiskom pri určovaní obvodov (§ 44 ods. 8 písm. d)). Ak pridelená škola vyučuje len v menšinovom jazyku, žiaci so slovenčinou musia dochádzať inam. V tomto nástroji je jazyk samostatný podnet a NEVSTUPUJE do semaforu.' },
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
