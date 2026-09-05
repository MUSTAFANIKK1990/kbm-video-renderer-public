# KBM GitHub Actions Free Android Runner — Package 08

## Decision

Package 08 replaces the undeployed paid Container/R2 runtime in Package 07 with a free, Android-controlled path. The existing AvalAI Gateway remains unchanged.

```text
Android browser
  -> Cloudflare Worker Free (UI, bearer auth, validation, stream proxy)
  -> GitHub draft release (unpublished input and output assets)
  -> GitHub Actions Ubuntu runner (Python + FFmpeg + Remotion)
  -> existing KBM AvalAI Gateway (Persian TTS)
```

No WordPress, PHP, CPT, database, theme or production-site change is included.

## Free-tier contract

- No Workers Paid activation, R2 subscription or Cloudflare Container is used.
- The Worker accepts one raw video stream up to 95 MiB, below the 100 MB Cloudflare Free account request limit.
- GitHub Actions uses the account's included monthly minutes. With no payment method, jobs stop after the included quota instead of creating an overage charge.
- One video render runs at a time. Initial acceptance testing is limited to a 5–15 second non-sensitive MP4.
- AvalAI usage remains subject to the existing AvalAI account balance; Package 08 adds no new AvalAI charge.

## Components

| Component | Authority | Responsibility |
|---|---|---|
| Mobile UI | `cloud/dist/index.html` | Raw upload progress, start job, poll run and private download |
| Free Worker | `cloud/src/index.ts` | Bearer auth, validation, draft release, streaming upload, workflow dispatch and download proxy |
| Actions workflow | `.github/workflows/kbm-video-render-free.yml` | Bounded Ubuntu render and daily cleanup |
| Actions runner | `github_actions/release_runner.py` | Input validation/download, Package 06 execution, final upload and cleanup |
| Runtime | `wrangler.jsonc` | Workers Free static assets and API routes; no paid bindings |

## Security contract

Cloudflare secrets:

- `KBM_STUDIO_TOKEN`: operator bearer token;
- `KBM_GITHUB_TOKEN`: fine-grained token restricted to the approved repository.

Cloudflare plain variables:

- `KBM_GITHUB_OWNER`;
- `KBM_GITHUB_REPO`;
- `KBM_GITHUB_REF`;
- `KBM_GITHUB_WORKFLOW=kbm-video-render-free.yml`.

GitHub Actions secrets:

- `KBM_GATEWAY_URL`;
- `KBM_GATEWAY_TOKEN`.

`AVALAI_API_KEY` stays only inside the existing AvalAI Gateway Worker.

Required fine-grained GitHub token permissions:

- repository access: only the approved KBM repository;
- Contents: read and write;
- Actions: read and write;
- no account-wide, administration, issues or user permissions.

Rules:

- the Android page keeps `KBM_STUDIO_TOKEN` only in `sessionStorage`;
- GitHub and AvalAI credentials never enter HTML, URLs, release metadata or logs;
- upload and output assets remain in an unpublished draft release;
- release id, workflow run id, job UUID and release tag are cross-checked;
- uploads are streamed and never loaded into Worker memory;
- GitHub asset redirects are restricted to HTTPS `githubusercontent.com` hosts;
- pipeline execution uses an argument list and `shell=False`;
- expired `kbm-job-*` drafts and tags are removed after 48 hours.

## Legacy and duplicate authority scan

Package 08 removes these unused runtime authorities:

- `tools/kbm-video-factory/Dockerfile`;
- `tools/kbm-video-factory/.dockerignore`;
- `tools/kbm-video-factory/cloud/render_runner/server.py`;
- `tools/kbm-video-factory/tests/test_cloud_render_runner.py`.

The Package 07 document remains as version history. Package 06 voice and Package 05 creative authorities remain active dependencies.

## Android-only deployment path — after separate approval

1. Merge the Package 08 workflow into the repository default branch. GitHub requires a dispatchable workflow to exist on the default branch.
2. In GitHub repository Settings, add Actions secrets `KBM_GATEWAY_URL` and `KBM_GATEWAY_TOKEN`.
3. Create a fine-grained GitHub token restricted to this repository with Contents and Actions read/write.
4. Deploy `kbm-video-render-control-free-08` through Cloudflare Workers Builds.
5. Add the two Worker secrets and four plain variables in Cloudflare Settings. Enter values only in the authenticated dashboards, never in chat.
6. Open `/v1/health` and require version `0.8.0` with runner `github-actions-free`.
7. Upload a 5–15 second non-sensitive MP4 smaller than 95 MiB.
8. Require the flow `uploading -> queued -> rendering -> ready`, then download and inspect the MP4.

Android does not need Docker, Node, Python, FFmpeg, Windows or a PC.

## Acceptance criteria

- health endpoint returns HTTP 200 and version `0.8.0`;
- invalid Studio token returns HTTP 401 before a GitHub request;
- files over 95 MiB return HTTP 413;
- unsupported extension/template/voice/duration is rejected;
- input is stored only in a draft release;
- workflow title equals `KBM <job UUID>` and the release tag equals `kbm-job-<job UUID>`;
- final output is H.264 MP4, 1080×1920, 30 fps and playable on Android;
- input asset is deleted after a successful render;
- remaining job draft is removed by cleanup after 48 hours;
- no secret appears in Worker logs, Actions logs, release metadata or output.

## Failure behavior

| Failure | Expected result |
|---|---|
| Missing/invalid Studio token | HTTP 401; no release or upload |
| File over 95 MiB | HTTP 413 before GitHub upload |
| GitHub API/upload failure | Safe 502; partially created draft is scheduled for cleanup |
| Actions quota exhausted | Job remains blocked/failed without automatic billing when no payment method exists |
| Pipeline failure | Workflow fails and writes a bounded `failure-<job>.json` asset |
| Missing output | Worker reports failed; no download ticket |
| Expired ticket | HTTP 401 |
| Cleanup failure | Draft remains private and the next daily cleanup retries it |

## Rollback

1. Stop new uploads.
2. Roll back or disable the Package 08 Worker deployment.
3. Disable `KBM Free Android Video Render` in GitHub Actions.
4. Revert the Package 08 commit/PR to restore Package 07 source authority.
5. Delete only draft releases whose tags start with `kbm-job-` after required outputs are downloaded.
6. Keep the AvalAI Gateway unchanged.

No WordPress or database rollback is required.
