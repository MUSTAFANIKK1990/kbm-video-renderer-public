# KBM Video Factory Package 04

Package: `KBM-VIDEO-FACTORY-VISUAL-QUALITY-SCENE-RANKING-SMART-CUT-04`

## Purpose

Package 04 adds deterministic visual-quality analysis and ranked smart cutting after the Package 03 silence/dead-space rough cut and before optional music/SFX, normalization, WhisperX and Remotion rendering.

It exists for footage where audio-based dead-space removal is insufficient. A continuous handheld machine video can contain weak framing, darkness, blur, static or high-motion sections even when there is no removable silence.

## Authority

`pipeline/visual_quality.py`

The module performs:

1. FFmpeg grayscale frame sampling;
2. hard-scene detection as structural boundaries;
3. fixed micro-scene subdivision for continuous camera footage;
4. deterministic per-window quality scoring;
5. candidate ranking;
6. target-duration selection;
7. chronological keep-segment merge;
8. physical H.264/AAC smart-cut render using the existing Package 03 trim/atrim authority.

`pipeline/real_footage.py` remains the end-to-end production authority.

## Metrics

The Package 04 score combines:

- sharpness / edge energy: 27%;
- exposure: 20%;
- contrast: 15%;
- stability: 13%;
- visual activity: 10%;
- center-detail concentration: 10%;
- highlight/shadow clipping resistance: 5%.

All metrics are calculated from decoded sample frames. No cloud model or external AI API is required.

## Defaults

```text
sample fps = 2.0
candidate window = 2.5 s
visual scene threshold = 0.22
target ratio = 0.65
minimum score = 0.35
minimum clip = 1.2 s
```

For footage longer than the short-video floor, the default target is approximately 65% of source duration, bounded by an 8-second minimum and 45-second maximum. For very short footage, Package 04 preserves the full duration.

## Quality flags

Candidates can be tagged with deterministic warnings:

```text
dark
overexposed
low-contrast
soft-or-blurry
near-static
high-motion
heavy-clipping
```

These flags are diagnostic metadata. Selection is driven by the weighted score and target-duration policy.

## Smart-cut safety

Package 04 does not claim semantic understanding of excavator parts, brands, people, machine models or work activity.

It ranks visual quality only. Therefore:

- a technically sharp but unimportant shot can still score well;
- a semantically critical but visually weak shot can score poorly;
- object/subject understanding belongs in a later semantic package.

The report explicitly records this limitation.

## Package order

```text
Raw footage
  -> Package 03 silence/dead-space rough cut + dialogue cleanup
  -> Package 04 visual quality ranking + smart cut
  -> optional music/SFX lanes
  -> 1080x1920 normalization
  -> WhisperX Persian captions
  -> Remotion brand render
```

This order avoids ranking obvious audio dead-space, preserves Package 03 cleaned dialogue through the visual cut, and adds music/SFX only after the edit timing is stable.

## Standalone command

```bash
python pipeline/visual_quality.py \
  --input /path/to/footage.mp4 \
  --output /tmp/visual-smart-cut.mp4 \
  --report /tmp/visual-smart-cut-report.json
```

Useful overrides:

```text
--sample-fps 3
--window 2.0
--scene-threshold 0.18
--target-ratio 0.55
--target-seconds 15
--min-score 0.42
--min-clip 1.0
--analysis-only
```

## End-to-end controls

The same controls are exposed through `pipeline/real_footage.py` with the `visual-` prefix:

```text
--skip-visual-smart-cut
--visual-sample-fps
--visual-window
--visual-scene-threshold
--visual-target-ratio
--visual-target-seconds
--visual-min-score
--visual-min-clip
```

## Report contract

`visual-smart-cut-report.json` records:

- source duration;
- decoded sample-frame count;
- scene timestamps;
- candidate windows;
- quality score and rank for every candidate;
- per-candidate metrics and flags;
- selected vs rejected state;
- average selected and rejected scores;
- final keep segments;
- selected duration;
- removed duration;
- rendered smart-cut metadata.

## Repository policy

- No customer/reference raw videos are committed.
- No OpenCV, NumPy or model runtime is required for Package 04.
- FFmpeg plus Python standard library are sufficient for visual scoring.
- WordPress runtime remains untouched.

## Rollback

Package 04 is isolated to the video factory tooling and dedicated CI. Revert the Package 04 branch/PR to restore Package 03 behavior. No WordPress/database rollback is required.
