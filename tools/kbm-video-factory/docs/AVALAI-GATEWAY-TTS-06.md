# KBM Video Factory — AvalAI Gateway TTS 06

Package: `KBM-VIDEO-FACTORY-AVALAI-GATEWAY-TTS-06`

## Purpose

Connect the isolated KBM Video Factory to the deployed KBM Cloudflare Gateway for natural Persian narration without placing AvalAI credentials in the repository or command line.

## Runtime contract

- `KBM_GATEWAY_URL`: HTTPS Worker origin or complete `/v1/tts` endpoint.
- `KBM_GATEWAY_TOKEN`: encrypted runtime secret used as the Bearer token.
- AvalAI API credentials remain inside the Cloudflare Worker secret store.
- Default voice: `alloy`.
- Output: validated MP3 written atomically to `work/<job>/voiceover.mp3`.

## Pipeline order

```text
creative plan voiceoverScript
        |
        v
KBM Cloudflare Gateway /v1/tts
        |
        v
AvalAI / Gemini 2.5 Flash TTS
        |
        v
voiceover.mp3
        |
        v
audio_lanes loudness normalization + source ducking
        |
        v
WhisperX captions from final mixed speech
```

## Failure policy

- `401`: fail immediately; the token is invalid.
- `400`, `413`, `415`: fail immediately; input/configuration must be corrected.
- `502`, `503`, `504`: retry once with bounded backoff.
- Network timeout: retry once.
- If a Piper model was explicitly configured, a terminal Gateway failure falls back to Piper and records `generated-fallback` in the job report.
- Without an explicitly configured fallback, the job stops before final render.

## Security

- Secrets are never accepted as CLI arguments.
- Reports contain only the secret environment-variable name and whether it was configured.
- Gateway URLs must use HTTPS and cannot include credentials, query parameters or fragments.
- Audio responses are capped at 25 MiB and must have an `audio/*` content type.
- Temporary output is atomically renamed only after response validation.

## Rollback

Remove the Package 06 changes to `voiceover_adapter.py` and `real_footage.py` and restore Package 05. Cloudflare Gateway and WordPress require no rollback.

## WordPress impact

None. No PHP, CPT, database, theme, hook, shortcode or WordPress runtime file is changed.
