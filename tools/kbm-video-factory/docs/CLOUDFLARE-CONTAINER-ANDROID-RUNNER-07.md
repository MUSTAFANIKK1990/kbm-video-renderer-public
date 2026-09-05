# KBM Cloudflare Container Android Runner — Package 07

## Decision

Package 07 moves heavy video rendering to a Cloudflare Container while keeping the daily operator workflow inside an Android browser. The existing AvalAI Gateway remains a separate service and is not modified.

```text
Android browser
  -> KBM Worker (auth, validation, UI, job API)
  -> private R2 (multipart raw upload, status, final MP4)
  -> Cloudflare Container (Python + FFmpeg + Remotion)
  -> existing KBM AvalAI Gateway (Persian TTS)
```

No WordPress, PHP, CPT, database, theme or production site change is part of this package.

## Why a Container

Cloudflare Workers cannot run the existing Python/FFmpeg/Remotion process. A Container provides Linux/amd64, process execution, ephemeral disk and enough memory for a bounded social-video job. `standard-2` is selected for the first controlled test: 1 vCPU, 6 GiB memory and 12 GB disk. `max_instances` remains `1` until cost, reliability and render duration are measured.

The official Remotion Cloudflare example is a proof of concept and explicitly omits authentication, queuing, progress and client error propagation. Package 07 implements authentication, single-instance admission, durable R2 job status, bounded retry in the client and safe failure messages.

## Components

| Component | Authority | Responsibility |
|---|---|---|
| Mobile UI | `cloud/dist/index.html` | Multipart upload, start job, poll status, private download |
| Worker | `cloud/src/index.ts` | Bearer auth, validation, R2, Container routing, signed download ticket |
| Runner | `cloud/render_runner/server.py` | Input download, Package 06 command, status/output upload |
| Image | `Dockerfile` | Node 22, Python 3, FFmpeg, Persian fonts, Remotion Chrome |
| Runtime | `wrangler.jsonc` | Assets, R2, Container, Durable Object and observability bindings |

## Security contract

Required Worker Secrets:

- `KBM_STUDIO_TOKEN`: operator access to the mobile UI API;
- `KBM_CONTAINER_TOKEN`: Worker-to-Container request authentication;
- `KBM_GATEWAY_URL`: HTTPS URL of the existing KBM AvalAI Gateway;
- `KBM_GATEWAY_TOKEN`: bearer token accepted by that Gateway.

`AVALAI_API_KEY` stays only in the existing Gateway Worker. It is not copied into Package 07.

Rules:

- secrets are never stored in Git, HTML, R2 metadata, query strings or logs;
- the Android UI keeps `KBM_STUDIO_TOKEN` only in `sessionStorage`;
- raw uploads and outputs use a private R2 bucket;
- download URLs contain a derived HMAC ticket valid for five minutes, not the Studio token;
- only known media extensions, templates, voices and durations are accepted;
- the runner uses an argument list with `shell=False`; arbitrary command flags are impossible;
- the Container can read `uploads/` and `jobs/`, but can write only under `jobs/` through the R2 outbound binding.

## Android-only deployment path (after explicit approval)

Prerequisites:

1. Activate Cloudflare Workers Paid. Containers are not available on the free Workers plan.
2. Activate R2 and create a private bucket named `kbm-video-studio-media`.
3. In Cloudflare Dashboard, open **Workers & Pages → Create application → Import a repository**.
4. Connect `mustafanikk1990-del/karyabmashin-wp-stack` through the official GitHub integration.
5. Select the approved Package 07 branch.
6. Set root directory to `tools/kbm-video-factory`.
7. Set deploy command to `npx wrangler deploy`.
8. Add the four Worker Secrets above in **Settings → Variables and Secrets**. Values must be entered in the Dashboard, never in chat.
9. Restrict the build watch path to `tools/kbm-video-factory/**`.
10. Run the first deployment only after the package PR and cost gate are approved.

Workers Builds performs the Docker image build in Cloudflare infrastructure. Android does not need Docker, Node, Python, FFmpeg or Termux for normal production use.

## First production acceptance test

1. Open `/v1/health`; require HTTP 200 and version `0.7.0`.
2. Open the Worker UI on Android.
3. Upload a 5–15 second non-sensitive MP4.
4. Use preset `excavator-rental-3-checks`, template `KBM-V03-MACHINE-REVIEW`, voice `alloy`.
5. Require state sequence: `queued/accepted → downloading → rendering → uploading → ready`.
6. Download and verify MP4 plays, is 1080×1920, 30 fps, H.264/yuv420p, narration is Persian, and no secret appears in logs.
7. Inspect Workers, Container and R2 usage before increasing `max_instances`.

## Failure behavior

| Failure | Expected result |
|---|---|
| Invalid/missing Studio token | HTTP 401; no upload or job |
| Unsupported media or oversized request | HTTP 400/413; no render |
| Duplicate job | HTTP 409 |
| Container cold start/provisioning | Mobile client retries bounded transient 502/503/504 |
| Pipeline failure | R2 status becomes `failed` with redacted bounded message |
| Missing output | Download remains HTTP 404 |
| Container restart | Ephemeral files are lost, but authoritative status/input remain in R2 |

## Cost and capacity gate

- Containers require Workers Paid; the platform has a monthly minimum charge.
- `standard-2` and `max_instances: 1` deliberately cap initial concurrency.
- R2 storage and operations are metered after free allowances; downloads from R2 have no egress charge.
- Before production, configure an R2 lifecycle rule for raw uploads and outputs according to KBM retention policy.

## Rollback

1. Stop new jobs.
2. In Cloudflare **Deployments**, roll back the Package 07 Worker to the previous healthy deployment or disable its route.
3. Keep the existing AvalAI Gateway Worker unchanged.
4. Revert the Package 07 Git commit/PR to restore Package 06 source authority.
5. Do not delete the R2 bucket until required outputs are downloaded and retention is confirmed.

No WordPress or database rollback is required.
