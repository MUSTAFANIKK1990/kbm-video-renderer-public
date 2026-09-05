# 66377 Stage 03 — Visual Edit + Voice Sync

Package: `KBM-VIDEO-FACTORY-66377-STAGE03-VISUAL-EDIT-SYNC-01`

## Scope

This Stage 03 package edits the approved raw footage `66377.mp4` against the approved AvalAI narration without committing either media file to Git.

It adds a deterministic edit-decision configuration and FFmpeg renderer for:

- shot selection from the single raw source;
- hard jump cuts;
- punch zoom and slow push framing;
- two-part speed ramps;
- short freeze accents;
- source ambience ducking under the approved narration;
- 1080x1920 / 30fps / H.264 / yuv420p output;
- JSON reporting of cut times, shot mapping and sync delta.

## Authority

- `config/66377-stage03-edit.json` — shot and timing authority.
- `pipeline/stage03_visual_edit.py` — deterministic FFmpeg render authority.

Package 09 remains the general smart non-blocking editor. This Stage 03 path is an explicit accepted-content edit on top of that architecture and does not replace `orchestrator_v2.py` or `real_footage.py`.

## Expected external inputs

```text
66377.mp4
66377-avalai-final-20s.mp3
```

Do not commit either file.

## Command

```bash
python3 pipeline/stage03_visual_edit.py \
  --input /path/to/66377.mp4 \
  --voice /path/to/66377-avalai-final-20s.mp3 \
  --config config/66377-stage03-edit.json \
  --output /tmp/66377-stage03-preview.mp4 \
  --report /tmp/66377-stage03-report.json
```

## Approved timeline

The visual plan targets `18.84s` and uses ten output shots. Jump cuts occur at approximately:

```text
2.20, 3.90, 6.10, 8.10, 10.20, 12.80, 14.60, 16.20, 17.60 seconds
```

Speed changes are applied in the rental and connection beats. Freeze accents are applied near the `ماشین می‌خوای؟` and CTA beats.

## Local acceptance result

The implementation was exercised against the actual approved raw footage and the approved AvalAI voice before PR creation.

Observed preview result:

```text
planned duration: 18.840 s
voice duration:   18.840 s
output duration:  18.832 s
sync delta:       0.008 s
video:            1080x1920, 30 fps, H.264, yuv420p
source ambience:  retained at 0.16 under narration
```

The preview artifact is intentionally not committed to the repository.

## Non-goals

Stage 03 does not burn final Persian subtitles, final caption styling, final music bed, final SFX mix or publishing metadata. Those remain for the next approved stage.

## Risk

Low. Changes are isolated to `tools/kbm-video-factory/`. No WordPress, database, Cloudflare deployment, secret, billing or public production change is included.

## Rollback

Close the Stage 03 PR or revert its commits. Package 09 and the existing render paths remain unchanged.
