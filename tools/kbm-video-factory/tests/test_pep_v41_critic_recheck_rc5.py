from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
for item in (str(PIPELINE), str(ROOT)):
    if item not in sys.path:
        sys.path.insert(0, item)

recheck = importlib.import_module("critic_recheck_131")


class Rc5GateSemanticsTests(unittest.TestCase):
    def _report(self) -> dict:
        return {
            "package": recheck.PACKAGE,
            "version": recheck.VERSION,
            "pipelineMode": "v41",
            "brandPreflight": {"configured": True},
            "package13": {"brandReady": True},
            "voiceDirector": {"complete": True, "durationFit": True},
        }

    def test_incomplete_critic_never_passes_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            video = Path(temporary) / "final.mp4"
            video.write_bytes(b"video")
            blockers = recheck._gate_blockers(
                self._report(),
                video,
                {"criticComplete": False, "overall": 0.0, "publishReady": False},
                8.0,
            )
        self.assertIn("CRITIC_INCOMPLETE", blockers)

    def test_valid_critic_passes_without_threshold_weakening(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            video = Path(temporary) / "final.mp4"
            video.write_bytes(b"video")
            blockers = recheck._gate_blockers(
                self._report(),
                video,
                {"criticComplete": True, "overall": 8.2, "publishReady": True},
                8.0,
            )
        self.assertEqual(blockers, [])

    def test_below_threshold_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            video = Path(temporary) / "final.mp4"
            video.write_bytes(b"video")
            blockers = recheck._gate_blockers(
                self._report(),
                video,
                {"criticComplete": True, "overall": 7.99, "publishReady": True},
                8.0,
            )
        self.assertIn("CRITIC_BELOW_THRESHOLD", blockers)


class Rc5SourceAuthorityTests(unittest.TestCase):
    def test_recheck_source_is_critic_only_and_hash_bound(self) -> None:
        source = (PIPELINE / "critic_recheck_131.py").read_text(encoding="utf-8")
        self.assertIn("13.1.2-rc.5", source)
        self.assertIn("PEP-V41-CRITIC-RECHECK-RESUME-GATE-SEMANTICS-AUTHORITY", source)
        self.assertIn("sourceVideoSha256", source)
        self.assertIn("postCriticVideoSha256", source)
        self.assertIn("renderExecuted\": False", source)
        self.assertIn("critique_final(video, work)", source)
        self.assertNotIn("render_with_fallback", source)
        self.assertNotIn("orchestrator_v4", source)
        self.assertNotIn("remotion", source.lower())

    def test_recheck_normalizes_report_gate_semantics(self) -> None:
        source = (PIPELINE / "critic_recheck_131.py").read_text(encoding="utf-8")
        self.assertIn('report["rendered"] = video.is_file()', source)
        self.assertIn('report["gatePass"] = gate_pass', source)
        self.assertIn('"criticOnlyResume": True', source)
        self.assertIn('return 0 if gate_pass else 52', source)

    def test_workflow_reuses_rc4_artifact_without_render_stack(self) -> None:
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "kbm-pep-v41-critic-recheck-rc5.yml")
        if not workflow.is_file():
            self.skipTest("workflow is created in the final rc5 commit")
        source = workflow.read_text(encoding="utf-8")
        self.assertIn("13.1.2-rc.5", source)
        self.assertIn("33286092042", source)
        self.assertIn("9724571573", source)
        self.assertIn("actions/download-artifact@v4", source)
        self.assertIn("critic_recheck_131.py", source)
        self.assertNotIn("npm ci", source)
        self.assertNotIn("remotion", source.lower())
        self.assertNotIn("orchestrator_v41.py", source)


if __name__ == "__main__":
    unittest.main()
