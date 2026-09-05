# Reference Audit 01

Package: `KBM-VIDEO-FACTORY-REFERENCE-PATTERN-AUTOMATION-01`

## Scope

This audit maps the six supplied reference MP4 files into reusable KBM patterns. Technique identification is based on visible output behavior; the exported MP4 files do not prove which exact editor or AI product was used.

## Reference mapping

| Reference file | Observed production pattern | KBM template |
|---|---|---|
| `oring_paking13_ceb7edaab5da4e3d88a5002312cc6ea8.mp4` | Static/near-static poster, fade/brightness reveal, restrained motion | `KBM-V01-INFOGRAPHIC` / `KBM-V04-MOTION-POSTER` |
| `mixin.ir_2f7fff412fc8462b978958cbf41237a1.mp4` | Talking head, jump cuts, punch-in zoom, animated subtitles, UI/phone overlays, logo reveal | `KBM-V02-PRESENTER-UI` |
| `pirouzanco__231c2589341c4966afafe12f10b635ce.mp4` | Real machinery footage, fast cuts, speed emphasis, radial/zoom transitions, bold text hits | `KBM-V03-MACHINE-REVIEW` |
| `persiajonoub_fee395e937b44b5a86bfe79f2656d7fc.mp4` | Layered motion poster, masks, scale animation, parallax/2.5D feeling, glitch/warp accents | `KBM-V04-MOTION-POSTER` |
| `liftrakmohamad_81d56ee65368464086c27b7f1c90864b.mp4` | Presenter + machine, glitch text, silhouette/flash treatment, neon outline, tracked labels/location callouts | `KBM-V05-TECHNICAL-VFX` |
| `auto__fx_14ad74a81a2c4957be6784f87074abe5.mp4` | B-roll, caption bubbles, match cuts, flash transformation/reveal, prop-based storytelling, logo end card | `KBM-V06-STORY-REVEAL` |

## Automation interpretation

### Deterministic stages

These should work without generative AI:

- FFmpeg normalization and final encoding
- scene splitting / rough cut
- caption timing import
- branded typography
- CTA and lower-third layout
- punch-in / scale / flash / poster reveals
- logo/end-card treatment

### Optional AI-assisted stages

Use only when a template benefits from them:

- WhisperX: Persian transcription + word timing
- SAM2: subject/machine masks and tracking
- ComfyUI + Wan/LTX: generated B-roll or image-to-video
- RIFE: interpolation for slow motion or generated footage

## KBM-specific adaptation rules

- Preserve Karyab Mashin industrial yellow/navy identity.
- Do not reproduce source brand logos, copy, exact graphic assets, or proprietary layouts.
- Prefer machine-specific data: category, brand/model, city, rental/sale context, operator/service context.
- Keep vertical output at 1080x1920, 30 fps by default.
- Keep subtitles and CTA within safe zones to avoid Instagram/Reels overlays.
- Generated shots must not falsify machine condition, availability, project location, or commercial claims.

## v0.1 acceptance criteria

- All six template IDs appear in Remotion Studio.
- A sample JSON renders to MP4 without source changes to WordPress.
- RTL Persian title, subtitle, caption, CTA and website label are readable.
- Base render does not require AI services.
- AI adapters remain optional and fail-safe.
- Output files and raw footage remain excluded from Git version control.
