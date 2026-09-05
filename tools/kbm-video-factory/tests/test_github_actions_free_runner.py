from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "github_actions" / "release_runner.py"
SPEC = importlib.util.spec_from_file_location("kbm_github_actions_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)

JOB_ID = "123e4567-e89b-12d3-a456-426614174000"


def job_environment() -> dict[str, str]:
    return {
        "GITHUB_REPOSITORY": "mustafanikk1990-del/karyabmashin-wp-stack",
        "GITHUB_TOKEN": "github-test-token",
        "JOB_ID": JOB_ID,
        "RELEASE_ID": "101",
        "INPUT_ASSET_ID": "202",
        "INPUT_EXTENSION": "mp4",
        "CREATIVE_PRESET": "excavator-rental-3-checks",
        "KBM_TEMPLATE": "KBM-V03-MACHINE-REVIEW",
        "KBM_VOICE": "alloy",
        "MAX_SECONDS": "60",
        "CAMPAIGN_BRIEF_B64": "",
        "EDIT_STYLE": "high-energy",
        "KBM_GATEWAY_URL": "https://gateway.example.workers.dev",
        "KBM_GATEWAY_TOKEN": "gateway-test-token",
    }


class RunnerValidationTests(unittest.TestCase):
    def test_valid_job_defaults_to_v2(self) -> None:
        with patch.dict(os.environ, job_environment(), clear=True):
            job = runner.validated_job()
        self.assertEqual(job["jobId"], JOB_ID)
        self.assertEqual(job["maxSeconds"], 60)
        self.assertEqual(job["pipelineMode"], "v2")

    def test_pipeline_mode_accepts_v2_v3_and_v4_only(self) -> None:
        self.assertEqual(runner.validated_pipeline_mode("v2"), "v2")
        self.assertEqual(runner.validated_pipeline_mode("V3"), "v3")
        self.assertEqual(runner.validated_pipeline_mode("V4"), "v4")
        self.assertEqual(runner.validated_pipeline_mode(""), "v2")
        for value in ("latest", "package13", "v5", "../../bin/sh"):
            with self.subTest(value=value), self.assertRaises(runner.JobError):
                runner.validated_pipeline_mode(value)

    def test_rejects_unbounded_or_arbitrary_core_inputs(self) -> None:
        for field, value in (
            ("JOB_ID", "../../etc/passwd"),
            ("INPUT_EXTENSION", "exe"),
            ("CREATIVE_PRESET", "bad;rm"),
            ("KBM_TEMPLATE", "../../bin/sh"),
            ("KBM_VOICE", "custom"),
            ("MAX_SECONDS", "500"),
            ("KBM_PIPELINE_MODE", "v5"),
        ):
            with self.subTest(field=field):
                env = job_environment()
                env[field] = value
                with patch.dict(os.environ, env, clear=True), self.assertRaises(runner.JobError):
                    runner.validated_job()

    def _command(self, mode: str) -> list[str]:
        env = job_environment()
        env["KBM_PIPELINE_MODE"] = mode
        with patch.dict(os.environ, env, clear=True):
            job = runner.validated_job()
        return runner.build_command(ROOT, job, Path("/tmp/input.mp4"), Path("/tmp/final.mp4"))

    def test_v2_command_is_argument_list_without_secrets(self) -> None:
        command = self._command("v2")
        joined = " ".join(command)
        self.assertIsInstance(command, list)
        self.assertEqual(command[0], sys.executable)
        self.assertIn("orchestrator_v2.py", command[1])
        self.assertIn("--output", command)
        self.assertNotIn("GITHUB_TOKEN", joined)
        self.assertNotIn("KBM_GATEWAY_TOKEN", joined)

    def test_v3_command_selects_pro_edit_desk(self) -> None:
        command = self._command("v3")
        joined = " ".join(command)
        self.assertIn("orchestrator_v3.py", command[1])
        self.assertNotIn("--enable-broll", command)
        self.assertNotIn("GITHUB_TOKEN", joined)

    def test_v4_command_keeps_campaign_and_provider_credentials_out_of_cli(self) -> None:
        command = self._command("v4")
        joined = " ".join(command)
        self.assertIn("orchestrator_v4.py", command[1])
        for secret_or_context in (
            "PEXELS_API_KEY",
            "PIXABAY_API_KEY",
            "GITHUB_TOKEN",
            "KBM_GATEWAY_TOKEN",
            "CAMPAIGN_BRIEF_B64",
            "EDIT_STYLE",
        ):
            self.assertNotIn(secret_or_context, joined)

    def test_final_qc_accepts_project_authority_420_formats(self) -> None:
        for pixel_format in ("yuv420p", "yuvj420p"):
            with self.subTest(pixel_format=pixel_format), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "final.mp4"
                output.write_bytes(b"0" * 2048)
                payload = {
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "h264",
                            "pix_fmt": pixel_format,
                            "width": 1080,
                            "height": 1920,
                            "avg_frame_rate": "30/1",
                        },
                        {"codec_type": "audio", "codec_name": "aac"},
                    ],
                    "format": {"duration": "6.000"},
                }
                with patch.object(runner.shutil, "which", return_value="/usr/bin/ffprobe"), patch.object(
                    runner.subprocess, "check_output", return_value=json.dumps(payload)
                ):
                    report = runner.validate_final_output(output, 6.0)
                self.assertTrue(report["pass"])
                self.assertEqual(report["pixelFormat"], pixel_format)

    def test_final_qc_rejects_non_420_pixel_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "final.mp4"
            output.write_bytes(b"0" * 2048)
            payload = {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "pix_fmt": "yuv444p",
                        "width": 1080,
                        "height": 1920,
                        "avg_frame_rate": "30/1",
                    },
                    {"codec_type": "audio", "codec_name": "aac"},
                ],
                "format": {"duration": "6.000"},
            }
            with patch.object(runner.shutil, "which", return_value="/usr/bin/ffprobe"), patch.object(
                runner.subprocess, "check_output", return_value=json.dumps(payload)
            ), self.assertRaises(runner.JobError):
                runner.validate_final_output(output, 6.0)

    def test_v4_report_contract_accepts_safe_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path = root / "work" / JOB_ID / "package13-report.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(json.dumps({
                "package": "KBM-VIDEO-FACTORY-FULL-CINEMATIC-EDITORIAL-13",
                "version": "0.13.0",
                "pipelineMode": "v4",
                "rendered": True,
                "brandReady": False,
                "rights": {"approved": 0, "rejected": 0},
                "editorial": {"score": 82.5, "pass": True},
            }), encoding="utf-8")
            result = runner.validate_v4_editorial(root, JOB_ID)
            self.assertTrue(result["pass"])
            self.assertEqual(result["score"], 82.5)
            self.assertFalse(result["brandReady"])

    def test_redirect_allowlist_rejects_token_exfiltration(self) -> None:
        safe = "https://release-assets.githubusercontent.com/path/signed"
        self.assertEqual(runner._validate_asset_redirect(safe), safe)
        for unsafe in ("http://objects.githubusercontent.com/file", "https://github.example.test/file"):
            with self.assertRaises(runner.JobError):
                runner._validate_asset_redirect(unsafe)

    def test_cleanup_only_targets_old_kbm_drafts(self) -> None:
        cutoff = dt.datetime(2026, 8, 27, tzinfo=dt.timezone.utc)
        valid = {"draft": True, "tag_name": f"kbm-job-{JOB_ID}", "created_at": "2026-08-24T00:00:00Z"}
        self.assertTrue(runner.is_expired_release(valid, cutoff))
        self.assertFalse(runner.is_expired_release({**valid, "draft": False}, cutoff))
        self.assertFalse(runner.is_expired_release({**valid, "tag_name": "v1.0.0"}, cutoff))


class PackageContractTests(unittest.TestCase):
    def test_wrangler_uses_only_free_worker_assets(self) -> None:
        config = json.loads((ROOT / "wrangler.jsonc").read_text(encoding="utf-8"))
        self.assertEqual(config["name"], "kbm-video-render-control-free-08")
        self.assertEqual(config["compatibility_date"], "2026-08-27")
        self.assertIn("nodejs_compat", config["compatibility_flags"])
        self.assertEqual(config["assets"]["run_worker_first"], ["/v1/*"])
        for paid_binding in ("containers", "r2_buckets", "durable_objects", "migrations"):
            self.assertNotIn(paid_binding, config)

    def test_worker_streams_video_and_uses_private_github_jobs(self) -> None:
        source = (ROOT / "cloud" / "src" / "index.ts").read_text(encoding="utf-8")
        for authority in (
            "MAX_UPLOAD_BYTES = 95 * 1024 * 1024",
            "body: request.body",
            "draft: true",
            "workflow_run_id",
            "timingSafeEqual",
            "ctx.waitUntil",
            "download-ticket",
            "validateCampaignBriefB64",
            "ALLOWED_EDIT_STYLES",
        ):
            self.assertIn(authority, source)
        self.assertNotIn("arrayBuffer()", source)
        self.assertNotIn("R2Bucket", source)
        self.assertNotIn("RenderContainer", source)
        self.assertNotIn("AVALAI_API_KEY", source)

    def test_worker_matches_dispatch_run_by_authoritative_metadata_not_display_title(self) -> None:
        source = (ROOT / "cloud" / "src" / "index.ts").read_text(encoding="utf-8")
        for authority in (
            "head_branch",
            "workflowPath",
            "run.id !== runId",
            'run.event !== "workflow_dispatch"',
            "run.headBranch !== env.KBM_GITHUB_REF",
            "run.workflowPath !== expectedWorkflowPath",
        ):
            self.assertIn(authority, source)
        self.assertNotIn("run.displayTitle !==", source)
        self.assertNotIn("displayTitle:", source)

    def test_mobile_ui_is_package13_android_first_and_session_only(self) -> None:
        html = (ROOT / "cloud" / "dist" / "index.html").read_text(encoding="utf-8")
        self.assertIn("PACKAGE 13 · FULL CINEMATIC", html)
        self.assertIn('id="brief"', html)
        self.assertIn("X-KBM-Brief-B64", html)
        self.assertIn("X-KBM-Edit-Style", html)
        self.assertIn("XMLHttpRequest", html)
        self.assertIn("95 * 1024 * 1024", html)
        self.assertIn("sessionStorage", html)
        self.assertNotIn("localStorage", html)
        self.assertIn('dir="rtl"', html)

    def test_workflow_is_bounded_and_package13_runtime_is_optional(self) -> None:
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "kbm-video-render-free.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("timeout-minutes: 60", workflow)
        self.assertIn("release_runner.py cleanup", workflow)
        self.assertIn("vars.KBM_PIPELINE_MODE || 'v4'", workflow)
        for authority in (
            "inputs.campaign_brief_b64",
            "inputs.edit_style",
            "secrets.PEXELS_API_KEY",
            "secrets.PIXABAY_API_KEY",
            "vars.KBM_BRAND_LOGO_URL",
            "vars.KBM_PACKAGE13_MEDIA_RESEARCH || '1'",
            "vars.KBM_PACKAGE13_MATERIALIZE_MEDIA || '1'",
        ):
            self.assertIn(authority, workflow)
        self.assertNotIn("pull_request_target", workflow)

    def test_runner_streams_files_never_uses_shell_and_has_final_qc(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertIn("while chunk := stream.read(1024 * 1024)", source)
        self.assertIn("shell=False", source)
        self.assertIn("validate_final_output", source)
        self.assertIn('"pipelineMode"', source)
        self.assertIn("orchestrator_v4.py", source)
        self.assertIn("yuvj420p", source)
        self.assertNotIn("read_bytes()", source)


if __name__ == "__main__":
    unittest.main()
