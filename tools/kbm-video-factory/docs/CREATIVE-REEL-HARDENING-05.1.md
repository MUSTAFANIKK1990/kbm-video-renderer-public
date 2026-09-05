# KBM Video Factory — Creative Reel Hardening 05.1

Package: `KBM-VIDEO-FACTORY-CREATIVE-REEL-TEXT-TTS-MUSIC-SFX-05`
Revision: `0.5.1`

## Trigger

Field QA of the excavator reel identified three production gaps:

1. the local eSpeak fallback sounded robotic and was not acceptable as a production Persian narrator;
2. original field audio remained audible under narration;
3. text cards were readable but visually too static/simple for a modern short-form industrial reel.

## Voice authority

Production narration must not use eSpeak.

Preferred natural Persian path:

- `ddehghan/farsi-tts` Chatterbox Persian fine-tune via `pipeline/voiceover_adapter.py --engine chatterbox-fa`;
- user/operator supplies the external repository and model weights locally;
- no model weights, cloned voices, or third-party binaries are committed to KBM.

Lightweight fallback remains Piper with a Persian model such as Mana Persian Piper.

The goal is a natural conversational Persian delivery. The factory does not attempt to copy, extract, or imitate a proprietary ChatGPT product voice.

## Audio policy for the reviewed excavator reel

The approved review mode is narration-only:

```text
source field audio = 0.00
voiceover          = 1.00
music              = off
SFX                = off
```

The existing pipeline supports this without destructive media editing by running with:

```text
--source-duck-volume 0
--creative-audio off
--voiceover-audio /path/to/natural-persian.wav
```

This preserves the picture while eliminating the original microphone/field track from the final mix.

## Motion-graphics upgrade

`src/KbmReel.tsx` now uses a clean-room industrial motion language inspired by current programmatic-video patterns rather than static subtitle boxes:

- kinetic polygon/glass panels instead of plain rectangles;
- spring entrance + directional slide + scale + blur-to-sharp reveal;
- animated yellow accent rail and light sweep;
- large translucent point numbers (`01/02/03`);
- HUD corner brackets and moving scan line;
- transition flash and camera punch-in on creative beat changes;
- animated progress rail;
- persistent KBM brand chip and URL;
- CTA receives a distinct centered end-card treatment;
- source footage receives conservative contrast/saturation treatment only.

No competitor assets or source code are copied.

## Open-source research used for architecture decisions

- `remotion-dev/remotion`: transitions, captions, shapes and programmatic rendering patterns.
- `degueba/onda`: reviewed as a motion-vocabulary reference (entrances, callouts, cinematic motion, transitions); implementation remains clean-room and KBM-specific.
- `ddehghan/farsi-tts`: dedicated Persian Chatterbox/Piper adapters; Chatterbox selected as the preferred practical Persian natural-voice integration path.
- `fishaudio/fish-speech`: evaluated for high-end multilingual Persian support; not selected as the default 05.1 runtime because S2 Pro is materially heavier and has a research-specific model license.

## Runtime notes

Natural TTS model execution is optional and fail-closed. If the required external model/runtime is unavailable, KBM must not silently substitute eSpeak for production output. The operator may provide a verified narration WAV instead.

## WordPress impact

None. Revision 05.1 modifies only `tools/kbm-video-factory/` and its isolated video workflow.

## Rollback

Revert the 05.1 commits on the Package 05 branch to restore the original 0.5.0 creative renderer/voice adapter. No WordPress or database rollback is required.
