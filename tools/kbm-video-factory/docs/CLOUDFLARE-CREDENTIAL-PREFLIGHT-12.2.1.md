# KBM Video Factory — Package 12.2.1

Authority: `KBM-VIDEO-FACTORY-CLOUDFLARE-CREDENTIAL-PREFLIGHT-12.2.1`

## Goal

Add a read-only credential preflight before the first direct Wrangler production deploy. Package 12.2.1 keeps the zero Git Integration architecture from Package 12.2 and does not restore Cloudflare Workers Builds.

## Manual workflow

Workflow: `.github/workflows/kbm-cloudflare-direct-wrangler-12-2.yml`

Available actions:

- `credential_check`: default safe action. Runs the normal Wrangler dry run/typecheck, then authenticates to the configured Cloudflare account with `wrangler whoami --account ... --json` and reads the target Worker's deployment list with `wrangler deployments list --name kbm-video-render-control-free-08 --json`. It performs no deployment.
- `check`: local bundle/typecheck dry run only. It does not require Cloudflare credentials and performs no Cloudflare API preflight.
- `deploy`: remains manual-only, main-only, and requires the exact phrase `DEPLOY-KBM-WORKER-12.2`. Before deployment it automatically runs the same read-only credential preflight. Deployment starts only after all previous steps succeed.

## Required GitHub configuration

Repository variable:

- `KBM_CLOUDFLARE_ACCOUNT_ID`

Repository secret:

- `KBM_CLOUDFLARE_WORKER_DEPLOY_TOKEN`

Never print, log, echo, commit, or paste the token value into chat or source control.

## Safety properties

- Credentialed actions are allowed only from `main`.
- The credential preflight uses read-only Wrangler commands.
- Command JSON output is redirected to temporary files and only JSON syntax is validated; account details and deployment details are not printed by the workflow.
- `wrangler auth token` is intentionally not used because it would expose the configured token value.
- The deploy step remains separate and conditional on the explicit `deploy` action.
- `keep_vars` remains enabled from Package 12.2.
- Cloudflare Git Integration / Workers Builds remains absent from the production path.

## Acceptance sequence

1. Merge Package 12.2.1 only after CI passes.
2. Run the manual workflow on `main` with `credential_check` and leave confirmation empty.
3. Require a successful credential preflight before requesting approval for the first production deploy.
4. Do not run `deploy` without a separate explicit production approval.

## Rollback

Before merge: discard the Package 12.2.1 branch.

After merge but before deployment: revert the Package 12.2.1 merge commit. No Worker runtime rollback is required because the credential preflight does not mutate production.
