# KBM CAMP Hotfix05 Evidence Note

Authority: `KBM-CAMP-FINAL-GATE-HOTFIX-05-AUTHORITY`

## Hotfix04 final evidence that triggered Hotfix05

Run `33360522052` reached the hard release gate with technical/audio/voice/rights/brand checks substantially healthy, but final visual-retention and editorial quality remained below CAMP floors.

Root causes confirmed from the Hotfix04 artifact and live source:

1. Search-query self-contamination in semantic relevance scoring.
2. Sparse provider metadata for relevance evaluation.
3. Insufficient globally unique external assets for the requested shot count.
4. Renderer modulo reuse of the external asset pool.
5. Repair pass state fixed at `1`, so pass 2 was not truly progressive.
6. Voice selection prioritized a small dynamics delta over a much better editorial duration fit.

## Hotfix05 changes

- Correct semantic scoring that never scores the injected query against itself.
- Preserve Pexels/Pixabay semantic metadata (`alt`, `tags`, source slug).
- Expand free-provider machine-sale diversity to at least seven requests when CAMP diversity is enabled.
- Enforce globally unique provider/source identities in asset routing before fallback.
- Use `CinematicAdMasterReelV4`, consuming unique external assets once with no modulo repeat.
- Make bounded repair passes truly progressive (`0 -> 1 -> 2`) and expose metric-targeted repair flags.
- Select voice takes by duration fit after the unchanged dynamics floor has been met.
- Keep every CAMP hard threshold unchanged.

## CI evidence

Hotfix05 dedicated CI run `33364481281` passed TypeScript typecheck, Python syntax checks and seven root-cause regression tests.

## E2E infrastructure note

The first Hotfix05 E2E attempt `33364542584` did **not** execute CAMP. It stopped at the source download step because the historical `pep-v41-critic-polish-rc6-evidence` Actions artifact had expired. This is an infrastructure/source-retention blocker, not a Hotfix05 quality-gate result.

The historical rc6 job is being re-run to regenerate the immutable source artifact before the Hotfix05 E2E is retried.
