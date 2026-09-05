# KBM Video Factory — Package 12.2

Authority: `KBM-VIDEO-FACTORY-CLOUDFLARE-DIRECT-WRANGLER-ZERO-GIT-INTEGRATION-12.2`

## Goal

Remove the production dependency on Cloudflare Git Integration / Workers Builds and make GitHub Actions + Wrangler the only supported deployment path for the Video Factory control Worker.

## Production deployment path

`GitHub Actions -> npm ci -> Wrangler dry run -> cloud TypeScript check -> explicit safety gate -> wrangler deploy --keep-vars -> Cloudflare Worker`

Cloudflare Workers Builds is not part of this path.

## Worker authority

- Worker name: `kbm-video-render-control-free-08`
- Wrangler config: `tools/kbm-video-factory/wrangler.jsonc`
- Worker entry point: `tools/kbm-video-factory/cloud/src/index.ts`
- Static assets: `tools/kbm-video-factory/cloud/dist`
- Runtime variables/secrets already configured in Cloudflare are preserved by `keep_vars: true` and the deploy command's `--keep-vars` flag.

## GitHub configuration required before deployment

Repository variable:

- `KBM_CLOUDFLARE_ACCOUNT_ID`

Repository secret:

- `KBM_CLOUDFLARE_WORKER_DEPLOY_TOKEN`

The deploy token must be scoped only to the required Cloudflare account and Worker deployment permissions. Never commit or print the token value.

## Deployment workflow

Workflow: `.github/workflows/kbm-cloudflare-direct-wrangler-12-2.yml`

It is intentionally manual-only. Two actions are available:

- `check`: install locked dependencies and run the Wrangler dry run/typecheck path. No production mutation is intended.
- `deploy`: allowed only from `main`, requires the exact confirmation phrase `DEPLOY-KBM-WORKER-12.2`, validates the account/token are present, repeats the dry run/typecheck, then runs `npm run cloud:deploy`.

There is no automatic push trigger in Package 12.2. Production activation remains a separate explicit approval.

## Removed Workers Builds dependency

Package 12.2 removes these source files from the active branch:

- `.github/workflows/kbm-cloudflare-builds-bootstrap-12-1.yml`
- `.github/workflows/kbm-cloudflare-builds-bootstrap-12-1-ci.yml`
- `tools/kbm-video-factory/cloud/bootstrap_workers_builds.py`
- `tools/kbm-video-factory/tests/test_cloudflare_builds_bootstrap.py`
- `tools/kbm-video-factory/docs/CLOUDFLARE-BUILDS-BOOTSTRAP-12.1.md`

Historical commits remain in Git history, but the current production source has no runtime or CI dependency on the removed bootstrap path.

## CI contract

Workflow: `.github/workflows/kbm-cloudflare-direct-wrangler-12-2-ci.yml`

The CI contract validates:

1. Wrangler can complete a dry-run deployment bundle.
2. Cloud TypeScript still typechecks.
3. `keep_vars` is enabled.
4. The deploy command uses direct Wrangler with `--keep-vars`.
5. The deployment workflow remains manual-only and fail-closed.
6. The old Workers Builds token/helper/workflows/docs/tests are absent from active source.

## Risk

Primary risk is deployment-token scope or an unexpected Wrangler configuration regression. The production workflow therefore performs a dry run before every deploy and refuses production mutation outside `main` or without the exact confirmation phrase.

## Acceptance checklist

- Package 12.2 CI passes.
- Generic Video Factory CI passes on the Package 12.2 branch/PR.
- Package 12 CI passes.
- No old Workers Builds source file exists in the branch diff target.
- No production workflow has executed.
- No Cloudflare secret or variable has been changed during implementation.

## Rollback

Before production activation: delete/revert the Package 12.2 branch; `main` remains unchanged.

After a future approved merge but before a future approved deploy: revert the Package 12.2 merge commit. No Worker runtime rollback is needed because no deployment occurred.

After a future approved deploy: redeploy the previously approved Worker revision with Wrangler, or use Cloudflare Worker version rollback procedures. Secret rotation/deletion remains a separate explicit operation.
