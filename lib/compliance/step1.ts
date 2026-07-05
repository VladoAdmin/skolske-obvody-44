// Step-1 (streets pivot) display gate.
//
// Vlado's mandate puts ALL compliance/analysis in step 2. Step 1 ships a PURE
// clean street map: districts are identified ONLY by their per-school street
// colour, with NO compliance semafor surfaced anywhere (no RED/ORANGE/GREEN
// counts, no scorecard verdicts, no district verdict colouring, no popup
// PASS/FAIL counts).
//
// Verdicts stay COMPUTED internally — the engine is the SSOT and the runner
// still writes them (see engine/runner.py EMIT_FINDINGS). This flag only
// controls whether the compliance state is DISPLAYED. It NEVER alters data.
//
// Default: compliance display OFF (step 1). Set NEXT_PUBLIC_SO_SHOW_COMPLIANCE=1
// to re-enable in step 2. Parallel to the engine-side SO_EMIT_FINDINGS gate.
//
// Read via process.env at module load so the same constant works in both server
// and client components (Next inlines NEXT_PUBLIC_* at build time).
export const SHOW_COMPLIANCE = process.env.NEXT_PUBLIC_SO_SHOW_COMPLIANCE === '1'
