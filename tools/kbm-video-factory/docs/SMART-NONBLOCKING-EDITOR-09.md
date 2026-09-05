# KBM Video Factory Package 09 — Smart Non-Blocking Editor

Version: `0.9.0`

Authority package: `KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09`

## Goal

Package 09 keeps Package 08 as the free Android-first execution backbone and adds a fault-tolerant editing orchestrator. The only intended hard failures are unusable video input, normalization/decode failure, unwritable output, or failure of both renderers.

## Pipeline

`raw -> normalize -> rough-cut? -> visual-ranking? -> creative-director -> timeline -> shot-composer -> effect-router -> voice -> creative-audio -> mix -> captions -> render-router -> QC`

`?` stages are soft. If they fail, the pipeline records `FALLBACK` or `WARNING` and continues.

## Renderer fallback

1. Remotion renderer remains the preferred branded renderer.
2. FFmpeg native H.264/yuv420p is the emergency renderer.
3. If both fail, the job is failed.

## Compatibility

- Existing `real_footage.py` remains untouched as the legacy rollback path.
- `release_runner.py` is switched to `orchestrator_v2.py` only on the Package 09 branch.
- No WordPress, PHP, theme, plugin, database, R2, paid Worker, or Cloudflare Container changes are included.

## Android free path

Package 08 transfer/control architecture remains unchanged: Worker Free + private GitHub Draft Release + GitHub Actions.
