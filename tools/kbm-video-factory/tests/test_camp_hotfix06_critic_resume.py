from __future__ import annotations

import importlib
import json
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

resume = importlib.import_module("camp_critic_resume")


class CampHotfix06CriticResumeTests(unittest.TestCase):
    def _source_report(self) -> dict:
        checks = {
            name: {"pass": True, "blockers": []}
            for name in resume.REQUIRED_PRECRITIC_CHECKS
        }
        checks["critic"] = {
            "pass": False,
            "blockers": [resume.EXPECTED_BLOCKER],
        }
        return {
            "gatePass": False,
            "releaseReady": False,
            "blockers": [resume.EXPECTED_BLOCKER],
            "checks": checks,
        }

    def test_accepts_only_critic_incomplete_source(self) -> None:
        self.assertEqual(resume.validate_source_report(self._source_report()), [])

    def test_rejects_source_with_any_noncritic_blocker(self) -> None:
        report = self._source_report()
        report["blockers"] = ["AUDIO_LUFS_OUTSIDE_CAMP_RANGE", resume.EXPECTED_BLOCKER]
        errors = resume.validate_source_report(report)
        self.assertIn("SOURCE_REPORT_BLOCKERS_NOT_CRITIC_ONLY", errors)

    def test_rejects_failed_precritic_check(self) -> None:
        report = self._source_report()
        report["checks"]["rights"] = {"pass": False, "blockers": ["RIGHTS_EVIDENCE_MISSING"]}
        errors = resume.validate_source_report(report)
        self.assertIn("SOURCE_RIGHTS_NOT_PASS", errors)

    def test_resume_reuses_immutable_video_and_camp_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / "work"
            work.mkdir()
            video = root / "final.mp4"
            video.write_bytes(b"immutable-final-video")
            payloads = {
                "camp-release-report.json": self._source_report(),
                "camp-critic.json": {"criticComplete": False, "criticError": "insufficient_quota"},
                "camp-brief.json": {"durationSeconds": 20.0},
                "camp-renderer.json": {"renderer": "remotion", "fallback": False},
                "package13-1-voice-manifest.json": {"complete": True},
                "camp-rights-evidence.json": {"assets": []},
                "camp-visual-evidence.json": {"evidenceComplete": True},
            }
            for name, value in payloads.items():
                (work / name).write_text(json.dumps(value), encoding="utf-8")

            critic = {
                "criticComplete": True,
                "criticRequestAttempts": 1,
                "overall": 8.6,
                "publishReady": True,
            }
            gate = {
                "gatePass": True,
                "releaseReady": True,
                "blockers": [],
                "checks": {},
            }
            with (
                patch.object(resume, "enabled", return_value=True),
                patch.object(resume, "critique_final", return_value=critic),
                patch.object(resume, "release_gate", return_value=gate) as gate_call,
            ):
                evidence = resume.run_resume(
                    video=video,
                    work=work,
                    source_run_id="33389109590",
                    source_artifact_id="9757678320",
                    source_artifact_digest="sha256:f65ee12",
                )

            self.assertTrue(evidence["gatePass"])
            self.assertTrue(evidence["releaseReady"])
            self.assertTrue(evidence["videoUnchanged"])
            self.assertEqual(video.read_bytes(), b"immutable-final-video")
            gate_call.assert_called_once()
            written = json.loads((work / "camp-release-report.json").read_text(encoding="utf-8"))
            self.assertTrue(written["resume"]["criticOnlyResume"])
            self.assertFalse(written["resume"]["renderExecuted"])
            self.assertEqual(written["resume"]["sourceRunId"], "33389109590")

    def test_source_contains_no_render_or_generation_authority(self) -> None:
        source = (PIPELINE / "camp_critic_resume.py").read_text(encoding="utf-8")
        self.assertIn("critique_final(video, work)", source)
        self.assertIn("release_gate(", source)
        self.assertIn('"renderExecuted": False', source)
        self.assertNotIn("render_with_fallback", source)
        self.assertNotIn("orchestrator_camp", source)
        self.assertNotIn("generate_video", source)


if __name__ == "__main__":
    unittest.main()
