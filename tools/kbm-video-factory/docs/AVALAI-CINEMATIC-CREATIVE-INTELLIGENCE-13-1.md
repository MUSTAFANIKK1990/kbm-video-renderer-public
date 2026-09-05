# KBM Video Factory — Package 13.1

## AvalAI Cinematic Creative Intelligence

Package 13.1 adds an optional `v41` pipeline above Package 13 (`v4`). It does not activate itself in Production. The hosted workflow default remains `v4` until a separate activation approval changes `KBM_PIPELINE_MODE` to `v41`.

## Objective

Turn the existing automated Reel renderer into a bounded AI-assisted commercial editor that can:

- inspect real input footage before editing;
- create a stronger Persian campaign hook, body and CTA from the operator brief;
- request relevant stock B-roll from existing rights-gated providers;
- generate missing portrait B-roll and stills through AvalAI when enabled;
- generate multiple directed Persian voice takes and select a duration-fit take;
- preserve the official KBM logo as a separate brand authority instead of generating it with AI;
- review the final Reel with an AI critic;
- perform at most one bounded repair render when quality is below the configured threshold.

## Pipeline

```text
Studio brief + raw footage
        |
        v
AvalAI multimodal campaign director
        |
        +-- contact-sheet frames from source footage
        +-- Persian hook / body / CTA / narration
        +-- semantic media-search requirements
        |
        v
Package 13 base editor
        |
        +-- Pexels / Pixabay / approved Iran gateway
        +-- rights gate
        +-- optional AvalAI generated video / image
        +-- official KBM brand authority
        |
        v
AvalAI directed Persian voice
        |
        +-- commercial take
        +-- industrial take
        +-- social take
        +-- duration-fit selection in Maximum mode
        |
        v
Package 13 timeline + Remotion / FFmpeg render
        |
        v
AvalAI final Reel critic
        |
        +-- hook
        +-- pacing
        +-- B-roll relevance
        +-- shot variety
        +-- brand visibility
        +-- caption readability
        +-- CTA strength
        |
        v
Optional one-pass bounded repair
        |
        v
Final 1080x1920 Reel
```

## Authorities

- `pipeline/avalai_creative_client.py`
  - secure direct AvalAI API client;
  - multimodal chat;
  - directed TTS;
  - still generation;
  - asynchronous video generation;
  - bounded retry and response-size limits.
- `pipeline/avalai_creative_intelligence.py`
  - source-frame extraction;
  - campaign direction;
  - storyboard refinement;
  - final Reel critic;
  - bounded repair policy.
- `pipeline/avalai_voice_director.py`
  - directed multi-take Persian speech generation;
  - duration-fit take selection.
- `pipeline/providers.py`
  - Pexels;
  - Pixabay;
  - approved Iran gateway;
  - AvalAI generated media provider.
- `pipeline/asset_router.py`
  - rights manifest;
  - public HTTPS allowlist;
  - trusted local generated-asset materialization.
- `pipeline/orchestrator_v41.py`
  - Package 13.1 orchestration authority.
- `github_actions/release_runner_131.py`
  - backwards-compatible hosted runner shim supporting `v41` while preserving the proven Package 08/13 download, upload and cleanup contracts.

## Runtime mode

Production remains on:

```text
KBM_PIPELINE_MODE=v4
```

Package 13.1 is selected only by:

```text
KBM_PIPELINE_MODE=v41
```

Rollback is immediate by returning the repository/runtime variable to:

```text
KBM_PIPELINE_MODE=v4
```

or, if required, to an earlier supported pipeline.

## Required secret for direct Package 13.1 intelligence

GitHub Actions secret:

```text
AVALAI_API_KEY
```

The real value must never be committed, copied into workflow YAML, passed as a command-line argument or printed in logs. `release_runner_131.py` additionally redacts the value from surfaced errors.

The existing KBM AvalAI Gateway remains a fallback path for narration if the Package 13.1 direct voice stage cannot complete.

## Optional runtime variables

```text
KBM_PACKAGE131_MODE=maximum
KBM_PACKAGE131_CRITIC_THRESHOLD=8.0
KBM_AVALAI_VISION_MODEL=gpt-5.5
KBM_AVALAI_IMAGE_MODEL=gpt-image-2
KBM_AVALAI_VIDEO_MODEL=veo-3.1-fast-generate-001
KBM_AVALAI_TTS_MODEL=gpt-4o-mini-tts
KBM_AVALAI_BROLL_SECONDS=4
```

Package 13 existing optional provider/brand settings remain supported:

```text
PEXELS_API_KEY
PIXABAY_API_KEY
KBM_IRAN_MEDIA_SEARCH_URL
KBM_IRAN_MEDIA_SEARCH_TOKEN
KBM_MEDIA_DOWNLOAD_HOSTS
KBM_BRAND_LOGO_URL
KBM_BRAND_ASSET_HOSTS
```

## Standard vs Maximum

`standard`

- uses the AvalAI multimodal director when configured;
- uses one directed speech take;
- stock providers are preferred;
- generated media fills missing approved media requests;
- final critic remains available.

`maximum`

- uses multimodal direction;
- generates three directed Persian voice takes and selects a duration-fit take;
- allows generated media for requested B-roll/still scenes even when stock candidates exist;
- performs the final critic;
- permits one bounded repair render if the score is below threshold.

No mode contains an unbounded retry or recursive render loop.

## Media rights and brand policy

Public stock assets pass the Package 13 rights gate before materialization.

AvalAI-created media is represented internally as:

```text
provider=avalai-generated
license=KBM-OWNED
```

This is an internal provenance label for media generated for the KBM job and does not override any external provider terms that may apply.

AI media prompts explicitly request no text, no watermark and no logo. The official Karyab Mashin logo is not generated by an image/video model. It remains controlled by `brand_director.py` and is composited as a separate verified brand asset.

## Cost and failure bounds

Package 13.1 intentionally has no infinite generation loop.

- API retries are bounded.
- Generated B-roll duration is bounded to 2–8 seconds by the client.
- Maximum mode generation is bounded by the storyboard media-request count.
- Final AI repair is limited to one additional render pass.
- CI never calls the live AvalAI API and uses empty credentials / mocks.
- A live AvalAI test must be separately approved because image/video/voice generation can consume account credit.

## Final critic limitation

The current final critic extracts a small contact sheet from the rendered MP4 and scores visual qualities from those frames. It does not infer audio quality from still images. Audio-energy claims are therefore not considered authoritative until a future audio-analysis input is wired to the critic.

## QA gate

`.github/workflows/kbm-video-factory-package13-1-ci.yml` validates:

- TypeScript renderer and Worker contracts;
- Python compilation;
- Package 13 regression tests;
- Package 13.1 offline contracts;
- direct API key exclusion from CLI;
- secret redaction;
- generated media rights/materialization boundaries;
- multi-take voice selection;
- one-pass repair behavior;
- `v41` wiring;
- explicit proof that Production default remains `v4`.

## Activation policy

Package 13.1 implementation, PR merge and Production activation are separate gates.

Merging Package 13.1 source must not silently switch Production to `v41`. Production activation requires its own explicit approval and should be followed by a short, non-sensitive end-to-end Reel test and review of the Package 13.1 report before broader use.
