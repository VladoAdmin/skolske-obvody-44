// Scenario-type taxonomy for the findings register filter.
//
// Mirrors SCENARIO_FIELDS in engine/demo_inputs.py — the engine's single
// source of truth for the six Step-2 demo scenario families. Each scenario
// maps to the condition code(s) the engine emits for it; the filter narrows
// on condition_code, so it never re-derives or overrides engine output.
// tests/test_register_scenarios.py locks this mirror to the Python map —
// adding/removing a scenario here without touching the engine fails CI.

export interface ScenarioType {
  label: string
  conditions: string[]
  order: number
}

export const SCENARIO_TYPES_SK: Record<string, ScenarioType> = {
  segregation_mrk: {
    label: 'Segregácia (Atlas MRK)',
    conditions: ['Pe'],
    order: 1,
  },
  capacity_pressure: {
    label: 'Kapacitný tlak',
    conditions: ['Pf'],
    order: 2,
  },
  long_distance: {
    label: 'Veľká vzdialenosť',
    conditions: ['Pa', 'Pb'],
    order: 3,
  },
  difficult_route: {
    label: 'Náročná trasa',
    conditions: ['Pc', 'Pd'],
    order: 4,
  },
  language_minority: {
    label: 'Vyučovací jazyk (mimo § 44)',
    conditions: ['JAZYK'],
    order: 5,
  },
  address_overlap: {
    label: 'Prekryv adries',
    conditions: ['S2'],
    order: 6,
  },
}

export function getScenarioConditions(scenario: string): string[] | null {
  return SCENARIO_TYPES_SK[scenario]?.conditions ?? null
}

export function getScenarioLabel(scenario: string): string {
  return SCENARIO_TYPES_SK[scenario]?.label ?? scenario
}
