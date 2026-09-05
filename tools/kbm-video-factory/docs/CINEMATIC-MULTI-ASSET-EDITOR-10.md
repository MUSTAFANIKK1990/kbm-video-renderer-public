# KBM Video Factory Package 10

Package: `KBM-VIDEO-FACTORY-CINEMATIC-MULTI-ASSET-EDITOR-10`

Version: `0.10.0`

## Purpose

Package 10 upgrades the Package 09/Stage 03 reel path from a single-media composition into a non-blocking cinematic scene graph.

It does not replace Package 09. It layers a cinematic composition stage on top of the approved Stage 03 video/voice timeline.

## Authority chain

```text
Package 09 smart editor
  -> Stage 03 66377 shot-selection + AvalAI voice sync (PR #25)
  -> Package 10 cinematic multi-asset composition
```

The Package 10 branch is intentionally stacked on PR #25 so Stage 03 remains independently reviewable and rollback-safe.

## What Package 10 adds

- scene graph with `video`, `freeze`, `image`, `motion-slide`, `infographic`, `split-screen`, `poster`, and `end-card` scene kinds;
- external asset registry for generated images, videos, and future Lottie assets;
- full-screen image inserts without committing customer/generated binary media to Git;
- procedural static-card fallback when an optional image is unavailable;
- transition policy: hard, fade, push, wipe, cross-zoom, flash;
- motion policy: none, slow-push, punch, pan-left, pan-right;
- a single Persian caption lane with existing word-level active-word highlighting;
- automatic caption suppression when scene copy duplicates the spoken/subtitle message;
- image/motion-slide/end-card fallbacks that do not block the final render;
- 66377 cinematic scene authority and three external image asset slots.

## 66377 cinematic timeline

Target: `18.84s`, `30fps`, `1080x1920`.

```text
0.00-2.20   video hook
2.20-3.60   freeze / stop accent
3.60-5.70   video
5.70-7.40   services multi-card image/motion slide
7.40-9.80   video
9.80-11.60  procedural infographic
11.60-14.10 video
14.10-16.10 demand/supply split poster
16.10-18.84 cinematic end card
```

External image slots:

```text
66377-slide-services.png
66377-split-demand-supply.png
66377-end-card.png
```

These files are runtime assets and are intentionally not committed.

## Subtitle de-duplication

Package 10 uses one caption lane only.

If an active scene contains copy that is equal to, contains, or is contained by the current caption after Persian/Arabic normalization, that caption is suppressed for the scene.

This prevents the Stage 04 problem where the same sentence appeared both as a subtitle and as a second title.

## Non-blocking fallbacks

| Optional stage | Failure fallback |
| --- | --- |
| generated image | procedural static card / base video |
| motion slide asset | procedural cards |
| split poster asset | title/accent static card |
| end-card asset | procedural brand end card |
| transition | fade/hard visual continuity |
| cinematic scene | underlying Stage 03 base video |

Package 10 must not introduce a new hard blocker for optional visual assets.

## Build props example

```bash
python pipeline/cinematic_scene_builder.py \
  --config config/66377-cinematic-scenes.json \
  --registry config/66377-cinematic-assets.json \
  --asset-dir /path/to/66377-assets \
  --output /tmp/66377-cinematic-props.json
```

Then merge the generated `scenes` and `assets` into the existing Stage 03 render props with the approved media path and word-level captions.

## Security / scope

- no WordPress, theme, plugin, CPT, database, or production enqueue change;
- no Cloudflare deployment;
- no secret change;
- no billing change;
- no third-party binary asset is committed;
- no generated image is treated as a factual representation of a specific machine model unless the user supplied that fact.

## Risk

The main risk is visual over-composition. Package 10 limits the 66377 reference plan to three external image assets and one procedural infographic, while retaining a single caption lane.

## Rollback

Do not merge the Package 10 PR, or revert it after merge. PR #25 and Package 09 remain independent.
