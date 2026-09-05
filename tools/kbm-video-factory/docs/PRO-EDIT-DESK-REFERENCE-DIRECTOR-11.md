# KBM Video Factory Package 11 — Pro Edit Desk + Reference Director

Version: `0.11.0`

Authority: `KBM-VIDEO-FACTORY-PRO-EDIT-DESK-REFERENCE-DIRECTOR-11`

## Purpose
Package 11 adds a reference-driven editorial decision layer above Package 09/10. It does not replace the free GitHub Actions backbone, the Package 09 non-blocking policy, or the Package 10 cinematic renderer.

Pipeline:
`Package09 prepare -> reference analysis? -> style DNA -> storyboard -> b-roll scout? -> asset routing? -> professional Persian captions -> sound-design plan -> Package10 renderer -> editorial critic`

All `?` stages are soft. Missing API keys, provider errors, optional dependencies, OpenTimelineIO, or network assets must never block the render.

## Reference Director
`reference_analyzer.py` extracts media geometry, scene-change cadence and visual-reset statistics without claiming the exact editor or AI product used by a reference. `style_dna_compiler.py` blends measured cadence with clean-room profiles. Reference binaries are never committed.

## B-roll and rights
Pexels and Pixabay adapters are optional. External downloads are disabled unless explicitly requested. Materialized external assets require rights metadata in `rights-manifest.json`. Fallback order is `external B-roll -> base user footage -> procedural motion card`.

## Persian captions
Package 11 uses one caption lane. Default industrial profile targets 78px text, up to two lines, up to five words per chunk, dark outline and yellow active-word emphasis. Motion-scene copy is separate from subtitle copy.

## Renderer integration
`ProEditDeskReel.tsx` wraps the approved Package 10 polished renderer. External B-roll, when materialized, is rendered muted as visual-only media so narration remains authoritative.

## Rollback
`orchestrator_v3.py --disable-pro-desk` delegates to Package 09 behavior. The existing GitHub release runner is intentionally not switched in this implementation branch; activation on the free runner requires a separate acceptance/approval step.
