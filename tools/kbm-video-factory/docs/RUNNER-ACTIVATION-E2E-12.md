# KBM Video Factory Package 12 — Runner Activation + End-to-End Acceptance

Version: `0.12.0`

Authority: `KBM-VIDEO-FACTORY-RUNNER-ACTIVATION-E2E-12`

## Purpose
Package 12 connects the existing free GitHub Actions release runner to either Package 09 (`orchestrator_v2.py`) or Package 11 (`orchestrator_v3.py`) through one fail-closed feature flag.

## Safe default
`KBM_PIPELINE_MODE` defaults to `v2` when the repository variable is unset or empty. Only `v2` and `v3` are accepted. Any other value is rejected.

Merging Package 12 does **not** activate Package 11 automatically.

## Activation
After Package 12 CI, review, merge, and separate operator approval, set the GitHub repository variable:

`KBM_PIPELINE_MODE=v3`

The next private render job will select `orchestrator_v3.py`. Package 12 does not enable or materialize Pexels/Pixabay B-roll in the free runner.

## Final QC
Before uploading `final-<job-id>.mp4`, the release runner validates:
- H.264 video;
- project-authority 8-bit 4:2:0 pixel format (`yuv420p` or the FFmpeg full-range alias `yuvj420p`);
- 1080x1920 geometry;
- approximately 30 fps;
- AAC audio;
- positive duration not exceeding `MAX_SECONDS + 0.25s`;
- non-empty output file.

The actual detected pixel format is recorded in the QC report. A failing output is never uploaded as a successful final artifact.

For V3, the Package 11 editorial report is also mandatory and must pass with score `>= 85`.

## Observability
Non-sensitive log events include `pipeline_selected`, `render_started`, `technical_qc_pass`, `editorial_qc_pass`, `release_uploaded`, `job_ready`, and `job_failed`. Secret values remain environment-only and are not added to command arguments or failure reports.

## End-to-end acceptance
Production acceptance is a separate post-merge gate:

`Android/Worker -> private draft release -> GitHub workflow -> v3 -> AvalAI -> Package 11 -> Remotion -> final QC -> private release asset -> mobile download`

Acceptance must use one bounded real job before general v3 activation is considered complete.

## Rollback
Immediate rollback requires no code revert:

`KBM_PIPELINE_MODE=v2`

The next job returns to Package 09. If Package 12 itself must be removed, revert the Package 12 merge commit.

## Scope
No WordPress, theme, plugin, database, Cloudflare Worker source, secret value, billing setting, or production deployment is changed by the implementation branch.
