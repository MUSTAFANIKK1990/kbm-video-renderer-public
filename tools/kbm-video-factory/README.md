# KBM Video Factory

Current package: `KBM-VIDEO-FACTORY-GITHUB-ACTIONS-FREE-ANDROID-RUNNER-08`

Previous package: `KBM-VIDEO-FACTORY-CLOUDFLARE-CONTAINER-ANDROID-RUNNER-07`

An isolated, versioned video-production toolchain for Karyab Mashin. It lives under `tools/` and does **not** modify WordPress runtime code.

## What Package 08 adds

- a zero-payment Android control room served by a Workers Free deployment;
- raw binary video streaming to a private, unpublished GitHub draft release;
- GitHub Actions rendering with Python, FFmpeg and Remotion;
- a 95 MiB input ceiling below the Cloudflare Free account request limit;
- short-lived private MP4 download tickets proxied through the Worker;
- one render at a time through a repository-wide Actions concurrency group;
- automatic removal of KBM draft jobs after 48 hours;
- no Containers, R2, Durable Objects, Docker host or international payment method;
- strict GitHub release/run ownership checks before status or download access.

Daily flow:

```text
Android browser -> authenticated Workers Free control plane
               -> unpublished GitHub draft release input
               -> GitHub Actions -> Package 06 pipeline
               -> unpublished final MP4 -> five-minute download ticket
```

Package 08 is source-only until separate Branch/PR and deployment approvals. The existing AvalAI Gateway remains independent.

## What Package 07 adds

- an Android-first Persian control room served by a Cloudflare Worker;
- authenticated multipart video uploads from a mobile browser to private R2;
- one Cloudflare Container per render job for Python, FFmpeg and Remotion;
- persistent job state and private final MP4 delivery through R2;
- bounded input, route, object-key, preset, voice and duration validation;
- short-lived signed download tickets instead of exposing the Studio token in URLs;
- GitHub/Workers Builds deployment so no PC, Windows or local Docker workflow is required;
- explicit health, progress, failure and rollback paths.

Daily flow:

```text
Android browser -> authenticated Worker -> private R2 upload
               -> Cloudflare Container -> Package 06 pipeline
               -> private R2 MP4 -> short-lived download ticket
```

Package 07 is source-only until a separate deployment approval. Containers require a Workers Paid plan and R2 must be activated before first deployment.

## What Package 06 adds

- secure Persian narration through the KBM Cloudflare Gateway and AvalAI;
- `KBM_GATEWAY_TOKEN` read only from the hosted runtime environment;
- no API key or gateway token in CLI arguments, logs or Git;
- one bounded retry for transient `502`, `503` and `504` responses;
- MP3 response validation and atomic output writes;
- Piper fallback when an operator has explicitly configured a Piper model;
- Package 05 creative audio, captions and Remotion behavior remain unchanged.

## What Package 05 adds

Package 04 chooses stronger visual sections. Package 05 turns the edited clip into a real branded reel:

- duration-aware creative story presets;
- animated Persian RTL text overlays;
- hook / numbered points / CTA cards;
- optional Persian voiceover;
- source-audio ducking under narration;
- background music and timestamped SFX;
- deterministic FFmpeg-generated fallback audio;
- Remotion final composition.

## First creative preset

`excavator-rental-3-checks`

Topic:

`۳ نکته مهم قبل از اجاره بیل مکانیکی`

Narrative:

1. Hook: check three items before renting an excavator.
2. Visual/body/cabin condition.
3. Boom and working-section condition.
4. Ready-to-work status.
5. Karyab Mashin CTA.

The preset is versioned in `config/creative-presets.json` and includes Persian overlay copy, narration script, reference timing and SFX cues.

## Current end-to-end pipeline

```text
RAW CAMERA / FIELD FOOTAGE
        |
        v
Package 03
scene/silence rough cut + dialogue cleanup
        |
        v
Package 04
visual-quality ranking + smart cut
        |
        v
Package 05
creative plan -> animated Persian overlays
        |
        +-- optional supplied/AvalAI Gateway/Piper voiceover
        +-- generated or supplied music
        +-- generated or supplied SFX
        +-- source-audio ducking
        |
        v
FFmpeg 1080x1920 / 30fps normalization
        |
        v
WhisperX Persian captions when enabled
        |
        v
Remotion branded H.264 reel
```

## Requirements

Base pipeline:

- Node.js 20+
- npm 10+
- FFmpeg / FFprobe on PATH
- Python 3.11+ recommended

Optional automatic speech:

- WhisperX for transcription/captions;
- KBM Cloudflare Gateway with hosted `KBM_GATEWAY_URL` and `KBM_GATEWAY_TOKEN` secrets;
- Piper executable plus an operator-supplied compatible voice model for TTS.

No model weights are committed.

## Install

```bash
cd tools/kbm-video-factory
npm install
```

## Excavator creative reel

```bash
python pipeline/real_footage.py \
  --input /path/to/excavator.mp4 \
  --creative-preset excavator-rental-3-checks \
  --template KBM-V03-MACHINE-REVIEW \
  --job excavator-reel-001
```

With a prepared Persian narration audio file:

```bash
python pipeline/real_footage.py \
  --input /path/to/excavator.mp4 \
  --creative-preset excavator-rental-3-checks \
  --voiceover-audio /path/to/narration.wav \
  --job excavator-reel-001
```

With the hosted AvalAI Gateway (recommended production path):

```bash
export KBM_GATEWAY_URL="https://your-kbm-gateway.workers.dev"
# KBM_GATEWAY_TOKEN must be injected by the hosted runtime secret manager.
python pipeline/real_footage.py \
  --input /path/to/excavator.mp4 \
  --creative-preset excavator-rental-3-checks \
  --avalai-voice alloy \
  --job excavator-reel-001
```

The token must never be passed as a CLI argument or committed to a file. The daily ChatGPT workflow is expected to invoke a hosted runner with these environment values already configured.

With Piper TTS and an operator-supplied model:

```bash
python pipeline/real_footage.py \
  --input /path/to/excavator.mp4 \
  --creative-preset excavator-rental-3-checks \
  --piper-model /path/to/fa-model.onnx \
  --piper-config /path/to/fa-model.onnx.json \
  --job excavator-reel-001
```

If no voiceover engine/audio is supplied, the Package 05 job remains valid with `voiceoverStatus=script-only`; visual text, music/SFX and final composition can still be prepared/rendered.

## Creative audio

By default, a selected creative preset uses a deterministic rights-clean fallback audio bed generated locally with FFmpeg. The preset also creates symbolic SFX cues (`hit`, `whoosh`, `tick`, `rise`).

Disable generated creative audio:

```text
--creative-audio off
```

Replace the generated bed with licensed production music:

```text
--music /path/to/music.wav
--music-volume 0.12
```

Add manual SFX:

```text
--sfx '/path/to/hit.wav@0.25@0.70'
```

When narration is present, source audio is ducked by default:

```text
--source-duck-volume 0.22
--voiceover-volume 1.0
```

## Creative plan only

```bash
python pipeline/creative_plan.py \
  --preset excavator-rental-3-checks \
  --duration 16.6 \
  --fps 30 \
  --output /tmp/creative-plan.json
```

The plan rescales the 17-second reference timeline to the actual edited-media duration.

## Generated fallback music/SFX only

```bash
python pipeline/creative_audio.py \
  --plan /tmp/creative-plan.json \
  --output-dir /tmp/creative-audio
```

## Visual overlays

Remotion accepts frame-based `overlays` with:

```text
kind: hook | point | badge | cta
position: top | center | bottom
eyebrow
text
accentText
from / to frames
```

Creative overlays use KBM yellow/navy, RTL layout, safe zones and spring/interpolation animation. Existing WhisperX captions remain supported.

## Package 04 controls

```text
--visual-sample-fps 2.0
--visual-window 2.5
--visual-scene-threshold 0.22
--visual-target-ratio 0.65
--visual-min-score 0.35
--visual-min-clip 1.2
--skip-visual-smart-cut
```

## Package 03 controls

```text
--scene-threshold 0.32
--silence-db -40
--min-silence 0.55
--silence-padding 0.12
--scene-snap 0.35
--skip-rough-cut
--no-audio-cleanup
```

## Generated working data

```text
work/<job>/rough-cut.mp4
work/<job>/visual-smart-cut.mp4
work/<job>/creative-plan.json
work/<job>/creative-audio/
work/<job>/voiceover.mp3 (AvalAI Gateway) or voiceover.wav (Piper)
work/<job>/audio-lanes.mp4
public/generated/<job>/media.mp4
work/<job>/captions.json
work/<job>/render-props.json
work/<job>/job-report.json
out/<job>.mp4
```

Generated media is ignored by Git.

## Authorities

- `pipeline/rough_cut.py`: Package 03 silence/dead-space edit and dialogue cleanup.
- `pipeline/visual_quality.py`: Package 04 visual scoring/ranking/smart cut.
- `config/creative-presets.json`: Package 05 creative story authority.
- `pipeline/creative_plan.py`: Package 05 duration-aware overlay/SFX plan.
- `pipeline/creative_audio.py`: deterministic fallback music/SFX generation.
- `pipeline/voiceover_adapter.py`: AvalAI Gateway, Piper and Chatterbox Persian adapters.
- `pipeline/audio_lanes.py`: source/voiceover/music/SFX mix and ducking.
- `src/KbmReel.tsx`: creative overlay renderer.
- `pipeline/real_footage.py`: current end-to-end production authority.
- `cloud/src/index.ts`: Package 08 Workers Free control plane, GitHub streaming, auth, job status and private download.
- `github_actions/release_runner.py`: validated release-asset downloader, Package 06 executor, output uploader and 48-hour cleanup.
- `.github/workflows/kbm-video-render-free.yml`: bounded free Actions render and scheduled cleanup workflow.
- `cloud/dist/index.html`: Android-first Persian operator UI.
- `wrangler.jsonc`: free Worker/static-assets runtime configuration without paid bindings.

## Documentation

- `docs/WHISPERX-SETUP-02.md`
- `docs/ROUGH-CUT-AUDIO-CLEANUP-03.md`
- `docs/VISUAL-QUALITY-SCENE-RANKING-SMART-CUT-04.md`
- `docs/CREATIVE-REEL-TEXT-TTS-MUSIC-SFX-05.md`
- `docs/AVALAI-GATEWAY-TTS-06.md`
- `docs/CLOUDFLARE-CONTAINER-ANDROID-RUNNER-07.md`
- `docs/GITHUB-ACTIONS-FREE-ANDROID-RUNNER-08.md`

## Safety / maintenance

- Do not commit customer/reference raw footage.
- Do not commit voice-model weights.
- Do not bundle third-party or competitor media/branding.
- FFmpeg-generated audio is a fallback, not a claim of licensed stock music.
- A preset is explicitly selected by the operator; Package 05 does not infer machine identity from pixels.
- Keep WordPress runtime untouched unless a separate approved integration package is created.
- Never commit `KBM_STUDIO_TOKEN`, `KBM_GITHUB_TOKEN`, `KBM_GATEWAY_TOKEN` or `AVALAI_API_KEY`.
- Raw uploads and final outputs remain unpublished GitHub draft-release assets and are removed after 48 hours.
- Keep the fine-grained GitHub token limited to the approved repository with Contents and Actions read/write only.
- Worker and GitHub Actions deployment require separate explicit approvals.

## WordPress impact

None. Package 08 does not modify PHP, CPTs, database schema, hooks, shortcodes, theme shell, frontend production enqueue or WordPress options.

## Rollback

Roll back the Package 08 Worker deployment from Cloudflare Deployments, disable `kbm-video-render-free.yml`, and revert the Package 08 commit/PR to restore Package 07 source authority. The existing AvalAI Gateway Worker remains independent. No WordPress or database rollback is required.
