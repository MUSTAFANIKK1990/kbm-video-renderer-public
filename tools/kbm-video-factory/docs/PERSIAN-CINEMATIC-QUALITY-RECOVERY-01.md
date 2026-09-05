# KBM Persian Cinematic Quality Recovery 01

Authority: `KBM-PERSIAN-CINEMATIC-QUALITY-RECOVERY-AUTHORITY-01`

## Decision

Instagram and Telegram transport are not the active problem. The published Reel proved the transport path, but the creative output is rejected because Persian narration, final-mix audibility, word-level subtitles, brand composition and advertising narrative were not proven by the release gate.

The user-supplied file `Screen_Recording_20260903_052840_Instagram.mp4` is the perceptual reference for delivery quality. Its screen-recording dimensions are not copied. KBM output remains 1080x1920, 30 fps, H.264/AAC.

## Measured reference audio

- AAC LC, 48 kHz, stereo, about 192 kbps
- Integrated loudness: -14.67 LUFS
- True peak: -1.02 dBTP
- Loudness range: 2.40 LU
- Duration: 23.045 seconds

## Adopted pattern

- One coherent Persian narrative
- Professional, energetic, non-monotone delivery
- Clear pronunciation of technical and brand terms
- Short controlled pauses and audible emphasis on Hook/keywords/CTA
- Word-level Persian subtitles with yellow active-keyword highlighting
- At least seven semantic visual beats and no unchanged visual section longer than 2.5 seconds
- Real industrial imagery, official KBM logo, direct CTA, website and end card
- No third-party watermark

## Fail-closed evidence

A render is not releasable unless all of the following exist and pass:

1. ASR transcript generated from the final MP4, not the source TTS file.
2. Persian language and script-to-ASR similarity evidence.
3. Explicit pronunciation review evidence for technical terms and KARYABMASHIN.
4. Word timing, caption coverage and caption-to-ASR agreement.
5. AAC 48 kHz stereo and reference-bounded LUFS/true peak.
6. Visual cadence, real-footage provenance, brand, CTA and watermark evidence.

ASR and pronunciation-review generation are now wired into the E2E workflow in two fail-closed stages:

1. The rendered Persian voice track is transcribed before render; its real WhisperX word timings become the caption authority. Synthetic equal-duration script alignment is forbidden in strict Persian quality mode.
2. The mastered final MP4 is transcribed again. This transcript proves that narration survived the final mix and drives a deterministic pronunciation-recognition review for the brand and technical terms present in the script.

The automated pronunciation review is explicitly a recognition proxy, not a human phonetics review. The branch remains Draft until the WhisperX runtime is installed in a controlled runner and one non-publishing render produces complete evidence.

## Controlled no-publish E2E

`KBM Persian Cinematic Quality E2E (No Publish)` uses Python 3.12 and pins WhisperX `3.8.6` with the CPU `small` / `int8` profile. A version mismatch is a hard failure, rather than an implicit upgrade.

The prior smoke-video artifact has expired and is not reused. The E2E obtains one current, licensed real industrial clip from configured Pexels or Pixabay credentials, normalizes it to the output media contract, and stores provider, source URL, licence, attribution and SHA-256 provenance with the run evidence.

The runner uses the official first-party KBM logo served by the public KBM visual-assets plugin, forbids external publishing by contract (`KBM_EXTERNAL_PUBLISH=0`), scans its scoped source for publish entrypoints before rendering, has read-only repository permissions, and does not invoke any Instagram, Telegram or WordPress worker.

## Scope exclusions

- No Telegram work
- No merge or deployment
- No secret or token changes
- No external publish
- No copying of the reference page identity or its subject matter
