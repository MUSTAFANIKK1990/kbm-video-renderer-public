# KBM Video Factory Package 05

Package: `KBM-VIDEO-FACTORY-CREATIVE-REEL-TEXT-TTS-MUSIC-SFX-05`

## Purpose

Package 05 adds the creative reel layer after Package 03/04 editing. It turns an edited machine clip into a branded short-form reel with a duration-aware story plan, animated Persian overlays, optional Persian narration, background music, SFX and a CTA.

## Authorities

- `config/creative-presets.json`: versioned subject/story presets.
- `pipeline/creative_plan.py`: scales preset timing to the actual edited duration.
- `pipeline/creative_audio.py`: deterministic FFmpeg-generated fallback music/SFX.
- `pipeline/voiceover_adapter.py`: optional Piper TTS adapter using a user-supplied model.
- `pipeline/audio_lanes.py`: source audio + voiceover + music + SFX mixing with source ducking.
- `src/KbmReel.tsx`: animated Persian creative overlays.
- `pipeline/real_footage.py`: end-to-end Package 05 authority.

## First production preset

`excavator-rental-3-checks`

Topic:

`۳ نکته مهم قبل از اجاره بیل مکانیکی`

Story beats:

1. hook;
2. body/cabin condition;
3. boom and working sections;
4. ready-to-work status;
5. Karyab Mashin CTA.

The preset contains Persian overlay copy, narration copy, timing, SFX cue types and an industrial music profile.

## Creative timeline scaling

The preset has a reference duration of 17 seconds. `creative_plan.py` rescales every overlay and SFX cue to the actual post-edit video duration, then emits both second-based and frame-based timing at 30 fps.

## Voiceover policy

Package 05 never invents a voice file. There are three supported states:

- `provided`: operator supplies `--voiceover-audio`;
- `generated`: Piper is available and the operator supplies an appropriate model with `--piper-model`;
- `script-only`: the creative preset/script is ready but no narration engine/audio was supplied.

No voice model is committed to the repository.

Example Piper usage:

```bash
python pipeline/real_footage.py \
  --input /path/to/excavator.mp4 \
  --creative-preset excavator-rental-3-checks \
  --piper-model /path/to/fa-model.onnx \
  --piper-config /path/to/fa-model.onnx.json \
  --job excavator-reel-001
```

## Rights-clean fallback audio

`creative_audio.py` can synthesize a simple deterministic industrial bed and four SFX types entirely through FFmpeg:

- `hit`
- `whoosh`
- `tick`
- `rise`

This fallback contains no third-party music/asset file. It is intentionally replaceable with licensed production audio using `--music` and repeatable `--sfx` arguments.

## Audio mix

When narration exists, source audio is ducked by default:

```text
source duck volume = 0.22
voiceover volume = 1.0
music volume = 0.12
final limiter = 0.95
```

The voiceover lane is normalized around `-16 LUFS / -1.5 dBTP` before final mixing.

## Visual overlay contract

Each overlay contains:

```text
from / to frames
kind: hook | point | badge | cta
eyebrow
text
accentText
position: top | center | bottom
```

Remotion renders these with KBM yellow/navy styling, RTL direction, safe-zone positioning and spring/interpolation entry/exit motion.

## Safety / limitations

- Package 05 is deterministic creative composition, not semantic machine recognition.
- The excavator topic is an explicit preset selected by the operator; Package 05 does not infer machine identity from pixels.
- Generated FFmpeg music is a fallback, not a substitute for a licensed high-quality production track.
- Piper TTS requires an operator-supplied model and executable.
- No competitor branding/assets, stock audio or model weights are committed.

## WordPress impact

None. Package 05 remains isolated under `tools/kbm-video-factory/` plus its dedicated CI workflow.
