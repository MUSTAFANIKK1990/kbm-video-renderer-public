from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FACTORY_ROOT = REPO_ROOT / "tools" / "kbm-video-factory"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "kbm-cloudflare-direct-wrangler-12-2.yml"


class DirectWranglerContractTests(unittest.TestCase):
    def test_wrangler_preserves_dashboard_variables(self) -> None:
        config = json.loads((FACTORY_ROOT / "wrangler.jsonc").read_text(encoding="utf-8"))
        self.assertEqual(config["name"], "kbm-video-render-control-free-08")
        self.assertEqual(config["main"], "cloud/src/index.ts")
        self.assertIs(config.get("keep_vars"), True)

    def test_package_deploy_is_direct_wrangler_and_keep_vars(self) -> None:
        package = json.loads((FACTORY_ROOT / "package.json").read_text(encoding="utf-8"))
        command = package["scripts"]["cloud:deploy"]
        self.assertIn("wrangler deploy", command)
        self.assertIn("--keep-vars", command)
        self.assertNotIn("bootstrap", command.lower())
        self.assertNotIn("builds", command.lower())

    def test_deploy_workflow_is_manual_only_and_fail_closed(self) -> None:
        text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("\n  push:", text)
        self.assertNotIn("\n  pull_request:", text)
        self.assertNotIn("\n  schedule:", text)
        self.assertIn("GITHUB_REF_NAME", text)
        self.assertIn("DEPLOY-KBM-WORKER-12.2", text)
        self.assertIn("KBM_CLOUDFLARE_WORKER_DEPLOY_TOKEN", text)
        self.assertIn("KBM_CLOUDFLARE_ACCOUNT_ID", text)
        self.assertNotIn("KBM_CLOUDFLARE_BUILDS_API_TOKEN", text)
        self.assertNotIn("bootstrap_workers_builds", text)

    def test_credential_preflight_is_read_only_and_redacts_token(self) -> None:
        text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("credential_check", text)
        self.assertIn('wrangler whoami --account "$CLOUDFLARE_ACCOUNT_ID" --json', text)
        self.assertIn("wrangler deployments list --name kbm-video-render-control-free-08 --json", text)
        self.assertIn("inputs.action != 'check'", text)
        self.assertNotIn("wrangler auth token", text)
        self.assertNotIn("cat /tmp/kbm-whoami.json", text)
        self.assertNotIn("cat /tmp/kbm-deployments.json", text)

    def test_deploy_runs_preflight_before_mutation(self) -> None:
        text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        preflight = text.index("Validate Cloudflare credentials read-only")
        deploy = text.index("Deploy Worker directly with Wrangler")
        self.assertLess(preflight, deploy)
        self.assertIn("inputs.action == 'deploy'", text)

    def test_workers_builds_source_dependency_is_removed(self) -> None:
        legacy_paths = [
            REPO_ROOT / ".github" / "workflows" / "kbm-cloudflare-builds-bootstrap-12-1.yml",
            REPO_ROOT / ".github" / "workflows" / "kbm-cloudflare-builds-bootstrap-12-1-ci.yml",
            FACTORY_ROOT / "cloud" / "bootstrap_workers_builds.py",
            FACTORY_ROOT / "tests" / "test_cloudflare_builds_bootstrap.py",
            FACTORY_ROOT / "docs" / "CLOUDFLARE-BUILDS-BOOTSTRAP-12.1.md",
        ]
        for path in legacy_paths:
            self.assertFalse(path.exists(), f"legacy Workers Builds dependency still exists: {path}")


if __name__ == "__main__":
    unittest.main()
