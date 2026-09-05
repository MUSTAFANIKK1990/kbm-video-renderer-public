# KBM Video Factory — Package 13.1.1

## AvalAI Live Creative Hardening

Package 13.1.1 hardens the existing optional `v41` pipeline. It does not activate `v41` in Production; the hosted workflow default remains `v4` until a separate production-activation approval.

## Scope

1. Final Audio Evidence
   - decodes the final MP4 audio with FFmpeg;
   - measures RMS, peak, activity/silence ratio, energy variation and clipping;
   - measures integrated loudness, true peak and LRA through FFmpeg loudnorm analysis when available;
   - computes a deterministic `technicalAudioScore`;
   - forces the final AvalAI critic `audioEnergy` score to use measured evidence instead of guessing from still frames.

2. Directed TTS Hardening
   - validates direct `/v1/audio/speech` responses as real audio;
   - rejects HTML/Cloudflare edge responses before they are written as MP3;
   - classifies quota, auth, rate-limit, network, unsupported-parameter and edge failures;
   - isolates commercial, industrial and social takes so one failed take does not erase successful takes;
   - records clean per-take diagnostics in `package13-1-voice-manifest.json`.

3. Multi-provider Media Hardening
   - keeps Pexels, Pixabay, Iran gateway and AvalAI-generated media independent;
   - records provider health, fallback counts, quota-block state and diagnostic codes;
   - allows healthy stock providers to continue if AvalAI generation is quota-blocked;
   - preserves the existing rights gate and KBM-owned generated-media authority.

4. Official Brand Gate
   - `v41` requires an official KBM logo by default through `KBM_PACKAGE131_REQUIRE_BRAND=1`;
   - performs a preflight before expensive live work;
   - verifies Package 13 actually resolved the logo before final refinement/critic stages;
   - returns a failed gate when the official brand asset is missing instead of silently treating an unbranded render as release-ready.

## New/changed authorities

- `pipeline/audio_critic.py`
- `pipeline/avalai_creative_client.py`
- `pipeline/avalai_creative_intelligence.py`
- `pipeline/avalai_voice_director.py`
- `pipeline/broll_scout.py`
- `pipeline/orchestrator_v41.py`
- `tests/test_package1311_live_hardening.py`

## Gate policy

A live `v41 maximum` smoke is acceptable only when:

- official KBM brand gate passes;
- direct AvalAI multimodal director passes;
- directed TTS is direct and complete for all requested takes in Maximum mode;
- at least one rights-approved media path is available for requested B-roll, with quota failures explicitly reported;
- final render is 1080x1920, H.264, 30 fps with audio;
- final critic uses measured audio evidence;
- critic overall score is at least the configured threshold;
- `publishReady=true`;
- no secret value is exposed in logs or artifacts.

Production remains `v4` until a separate activation decision.
