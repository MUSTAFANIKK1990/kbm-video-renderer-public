# Real Footage Source Matrix — Package 02

Package: `KBM-VIDEO-FACTORY-REAL-FOOTAGE-WHISPERX-AUTO-CAPTION-RENDER-02`

The six user-supplied MP4 files were inspected locally with `ffprobe`. Media files are intentionally **not committed** to GitHub. This document records only technical metadata needed to validate ingest rules.

| Source | Video | Size | FPS | Duration | Audio | SHA-256 |
|---|---|---:|---:|---:|---|---|
| `oring_paking13_...mp4` | H.264 | 720×1280 | 30 | 12.560590 s | AAC | `68196851302c4c01617a73be637220ccca0ec0f26509a58cec261be48a5c9eb3` |
| `mixin.ir_...mp4` | H.264 | 720×1280 | 30 | 47.460181 s | AAC | `5b131dd326d6ed20ce41e9a7fb1183cf325013c931cec2af1cddb63a94b1f6fb` |
| `pirouzanco_...mp4` | H.264 | 1280×720 | 25 | 23.040000 s | AAC | `251d3119b48cf3cc2303ffe7a15e727859f3cf7a306aef04e74462c152502802` |
| `persiajonoub_...mp4` | H.264 | 720×1280 | 29.97 | 16.788042 s | AAC | `95d5ca4700c29bcc5e12e86253bca712d104c26fcfb8fa026b6b30603a5ea9b0` |
| `liftrakmohamad_...mp4` | H.264 | 1280×720 | 30 | 30.000181 s | AAC | `c5afbca05467031e2ec6fc05237e940ec8baa20524c64e6b8bc24d4aa4b0ef8d` |
| `auto__fx_...mp4` | H.264 | 1280×720 | 30 | 30.325261 s | AAC | `2ecf2675a1831254036554307056634f8eeb4d2f73af955bfe8eb83ff124150c` |

## Ingest decisions

- Portrait sources default to `cover` at 1080×1920.
- Landscape sources default to `blurred-bg` so the machine/person remains fully visible while the output stays 9:16.
- Output is normalized to 30 fps, H.264, `yuv420p`, AAC and `+faststart`.
- Package 02 deliberately caps one reel job at 60 seconds.
- Audio is preserved unless the job is explicitly rendered with `--mute`.

## First production validation target

`liftrakmohamad_...mp4` is the preferred validation source for `KBM-V03-MACHINE-REVIEW` because it combines landscape field footage, a presenter/machine context, AAC audio and an exact ~30 second duration. The file remains local/private; only its generated output may be exported by the operator after review.

No transcript text from the supplied videos is asserted in this document. Persian captions are generated only when WhisperX is actually run against the source audio or when a verified WhisperX JSON file is supplied.
