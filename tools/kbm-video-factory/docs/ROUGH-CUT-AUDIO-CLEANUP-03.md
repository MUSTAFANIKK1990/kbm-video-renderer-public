# KBM Video Factory Package 03

Package: `KBM-VIDEO-FACTORY-SCENE-DETECT-ROUGH-CUT-AUDIO-CLEANUP-03`

## Purpose

Package 03 adds a deterministic pre-render editing stage between raw footage and the Package 02 9:16/WhisperX/Remotion pipeline.

It covers:

1. visual scene-change detection;
2. silence/dead-space detection;
3. keep-segment planning and FFmpeg rough-cut rendering;
4. conservative dialogue cleanup and loudness normalization;
5. optional background-music and timestamped SFX lanes;
6. handoff into the existing 9:16 normalize -> WhisperX -> Remotion render path.

## Authorities

### `pipeline/rough_cut.py`

Primary edit-plan and dialogue-cleanup authority.

### `pipeline/audio_lanes.py`

Optional background-music/SFX mixing authority. This module never runs unless one or more explicit audio lanes are supplied.

### `pipeline/real_footage.py`

End-to-end Package 03 production entrypoint. It invokes rough cut automatically unless `--skip-rough-cut` is provided, then optionally invokes the audio-lane mixer before 9:16 normalization.

## Scene detection

Default threshold:

```text
scene threshold = 0.32
```

FFmpeg's scene score is used only as structural evidence. A scene score by itself does not authorize deleting footage.

## Silence authority

Defaults:

```text
noise threshold = -40 dB
minimum silence = 0.55 s
padding = 0.12 s
scene snap tolerance = 0.35 s
```

Only silence intervals that satisfy the configured minimum duration can create removal windows. Padding is retained around active material.

If a scene transition exists inside the same qualified silence interval and falls within the snap tolerance, the edit boundary may be snapped to that transition. The boundary is never moved outside the qualified silence interval.

## Rough-cut output

The source is cut with FFmpeg `trim` / `atrim`, timestamp reset, and `concat` filters. Video and audio are rebuilt from the same keep-segment list so A/V sync remains deterministic.

Output defaults:

```text
video: H.264 / libx264 / CRF 18 / yuv420p
audio: AAC / 192 kbps
container: MP4 / faststart
```

## Dialogue cleanup

When source audio exists and cleanup is enabled:

```text
highpass=f=70
lowpass=f=15000
loudnorm=I=-16:TP=-1.5:LRA=11
```

The purpose is to remove sub-bass/handling rumble, reduce irrelevant very-high-frequency content and normalize perceived level for social-video dialogue.

This stage does not claim source separation, dereverberation, voice cloning, spectral reconstruction or studio-grade noise removal.

## Optional background music

Music is opt-in only.

Runtime controls:

```text
--music /path/to/music.wav
--music-volume 0.12
```

Rules:

- music volume default is `0.12`;
- accepted music-volume range is `0..1`;
- music is looped only to cover the edited-video duration;
- the final mixed bus is trimmed back to the exact video duration;
- no music asset is bundled or committed.

## Optional timestamped SFX

SFX are opt-in and repeatable.

Accepted forms:

```text
PATH@SECONDS
PATH@SECONDS@VOLUME
```

Examples:

```text
/path/to/hit.wav@1.40
/path/to/click.wav@4.20@0.50
```

Rules:

- SFX timestamp cannot be negative;
- SFX default volume is `0.75`;
- accepted SFX volume range is `0..2`;
- each SFX is delayed to the requested timestamp with FFmpeg `adelay`;
- the final audio bus uses `amix` and a `0.95` limiter;
- no SFX asset is bundled or committed.

## Audio-lane output contract

`pipeline/audio_lanes.py` preserves the edited video stream with `-c:v copy`, replaces/mixes the audio bus, writes AAC 192 kbps, trims to source duration and writes `faststart` MP4.

The mixer can operate with:

- cleaned dialogue + music;
- cleaned dialogue + one or more SFX;
- cleaned dialogue + music + SFX;
- video without dialogue audio + music/SFX.

## Generated reports

### `rough-cut-report.json`

Records:

- source duration;
- scene threshold;
- detected scene timestamps;
- silence detection parameters;
- detected silence intervals;
- keep segments;
- removed seconds;
- rough-cut duration;
- audio presence;
- whether the cleanup chain was applied.

### `audio-lanes-report.json`

Records:

- source path;
- output path;
- final duration;
- audio presence;
- music path and applied volume when present;
- every SFX path, timestamp and applied volume.

## Runtime controls

```text
--skip-rough-cut
--scene-threshold <0.01..0.99>
--silence-db <-1 or lower>
--min-silence <seconds>
--silence-padding <seconds>
--scene-snap <seconds>
--no-audio-cleanup
--music <path>
--music-volume <0..1>
--sfx PATH@SECONDS[@VOLUME]
```

## Failure policy

Package 03 is fail-closed for its own editing stages.

- If rough-cut generation fails, `real_footage.py` stops instead of silently rendering a different edit.
- If an explicitly requested music/SFX lane is missing or invalid, the pipeline stops instead of silently dropping that lane.
- Operators can explicitly bypass rough cut with `--skip-rough-cut`.
- Audio lanes remain disabled unless explicitly supplied.

## Privacy and repository policy

- Raw customer/reference video is not committed.
- Generated MP4 files remain ignored.
- No third-party audio or visual assets are vendored.
- No model weights are committed.
- Music/SFX paths are runtime inputs only.

## WordPress impact

None. Package 03 is isolated under `tools/kbm-video-factory/` plus the dedicated CI workflow.
