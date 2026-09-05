from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
SCRIPTS = ROOT / "scripts"

import sys
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from progress_tracker import complete_stage, finalize, init_progress, start_stage, update_stage  # noqa: E402

spec = importlib.util.spec_from_file_location("github_video_monitor", SCRIPTS / "github_video_monitor.py")
monitor = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(monitor)


class VideoLiveMonitorTests(unittest.TestCase):
    def test_monitor_has_exactly_ten_stages(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbm-monitor-") as temporary:
            path = Path(temporary) / "progress.json"
            data = init_progress(path, order_id="T-1", topic="خرید و فروش ماشین‌آلات", vertical="machine-sale", duration_seconds=20)
            self.assertEqual(len(data["stages"]), 10)
            self.assertEqual(data["overallPercent"], 0)

    def test_stage_only_reaches_100_on_real_completion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbm-monitor-") as temporary:
            path = Path(temporary) / "progress.json"
            init_progress(path, order_id="T-2", topic="اجاره", vertical="rental", duration_seconds=20)
            start_stage(path, "brief_preflight")
            update_stage(path, "brief_preflight", percent=73, status="running")
            self.assertEqual(monitor._load(path)["stages"][0]["percent"], 73)
            complete_stage(path, "brief_preflight")
            self.assertEqual(monitor._load(path)["stages"][0]["percent"], 100)

    def test_issue_body_contains_progress_eta_and_artifact_link(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbm-monitor-") as temporary:
            path = Path(temporary) / "progress.json"
            init_progress(
                path,
                order_id="T-3",
                topic="خدمات ماشین‌آلات",
                vertical="services",
                duration_seconds=20,
                workflow_url="https://github.com/example/repo/actions/runs/123",
                run_id="123",
            )
            start_stage(path, "creative_direction", "کارگردانی")
            data = monitor._load(path)
            body = monitor.render_issue(data)
            self.assertIn("پیشرفت کلی", body)
            self.assertIn("ETA تخمینی", body)
            self.assertIn("مراحل تولید", body)
            self.assertIn("Workflow Run", body)
            self.assertIn("لینک دانلود پس از ساخت Artifact", body)

            finalize(path, success=True, artifact_url="https://github.com/example/repo/actions/runs/123/artifacts/456")
            body = monitor.render_issue(monitor._load(path))
            self.assertIn("دانلود فایل نهایی", body)
            self.assertIn("100%", body)
            self.assertIn("COMPLETED", body)

    def test_blocked_issue_shows_explicit_blocker_and_required_action(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbm-monitor-") as temporary:
            path = Path(temporary) / "progress.json"
            init_progress(
                path,
                order_id="T-4",
                topic="خرید و فروش ماشین‌آلات",
                vertical="machine-sale",
                duration_seconds=20,
                workflow_url="https://github.com/example/repo/actions/runs/124",
                run_id="124",
            )
            update_stage(
                path,
                "voice_narration",
                status="blocked",
                percent=0,
                message="CUPAI_CREDIT_EXHAUSTED",
            )
            update_stage(
                path,
                "release_artifact",
                status="blocked",
                percent=0,
                message="Release Gate BLOCKED: VOICE_DIRECTOR_INCOMPLETE, CRITIC_INCOMPLETE",
            )
            body = monitor.render_issue(monitor._load(path))
            self.assertIn("Blocker فعلی و اقدام لازم", body)
            self.assertIn("CUPAI_CREDIT_EXHAUSTED", body)
            self.assertIn("اعتبار CupAI", body)
            self.assertIn("Workflow را مجدد اجرا کنید", body)
            self.assertIn("پس از رفع Blocker و اجرای مجدد Workflow", body)


if __name__ == "__main__":
    unittest.main()