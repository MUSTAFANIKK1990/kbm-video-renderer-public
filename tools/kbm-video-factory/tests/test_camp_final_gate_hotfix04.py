from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
SCRIPTS = ROOT / "scripts"
for item in (str(PIPELINE), str(SCRIPTS)):
    if item not in sys.path:
        sys.path.insert(0, item)

import avalai_voice_director  # noqa: E402
import broll_scout  # noqa: E402
import run_camp_with_progress  # noqa: E402
from progress_tracker import init_progress  # noqa: E402


class Hotfix04VoiceDynamicsTests(unittest.TestCase):
    def test_expression_score_is_not_penalized_by_pre_master_loudness(self) -> None:
        evidence = {
            "audioPresent": True,
            "technicalAudioScore": 7.0,
            "energyVariationDb": 16.038,
            "activityRatio": 0.8054,
            "measuredLra": 2.0,
            "measuredLufs": -23.58,
        }
        with mock.patch.object(avalai_voice_director, "analyze_audio", return_value=evidence):
            score, enriched = avalai_voice_director._voice_dynamics(Path("unused.mp3"))
        self.assertGreaterEqual(score, 8.0)
        self.assertEqual(enriched.get("voiceDynamicsMethod"), "expression-energy-activity-lra-v2")

    def test_flat_voice_remains_below_release_floor(self) -> None:
        evidence = {
            "audioPresent": True,
            "technicalAudioScore": 10.0,
            "energyVariationDb": 0.8,
            "activityRatio": 0.9,
            "measuredLra": 0.4,
        }
        with mock.patch.object(avalai_voice_director, "analyze_audio", return_value=evidence):
            score, _ = avalai_voice_director._voice_dynamics(Path("unused.mp3"))
        self.assertLess(score, 8.0)


class Hotfix04MediaDiversityTests(unittest.TestCase):
    def test_camp_diversity_adds_distinct_free_provider_requests(self) -> None:
        storyboard = {
            "scenes": [
                {"id": "one", "kind": "broll", "copy": "ماشین آلات در حال کار"},
                {"id": "two", "kind": "image", "copy": "بیل مکانیکی"},
            ]
        }
        with mock.patch.dict(os.environ, {"KBM_CAMP_MEDIA_DIVERSITY": "1"}, clear=False):
            requests = broll_scout._requests(storyboard)
        self.assertGreaterEqual(len(requests), 4)
        roles = {str(item.get("shotRole")) for item in requests}
        self.assertIn("context", roles)
        self.assertIn("closeup", roles)


class Hotfix04ProgressTests(unittest.TestCase):
    def test_intermediate_repair_does_not_terminally_block_live_monitor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir(parents=True)
            progress = root / "progress.json"
            init_progress(
                progress,
                order_id="TEST-1",
                topic="test",
                vertical="machine-sale",
                duration_seconds=20,
            )
            (work / "camp-critic.json").write_text(json.dumps({"criticComplete": True}), encoding="utf-8")
            (work / "camp-release-report.json").write_text(
                json.dumps({"gatePass": False, "releaseReady": False, "repairPass": 0, "blockers": ["CRITIC_PACING_BELOW_CAMP_FLOOR"]}),
                encoding="utf-8",
            )

            run_camp_with_progress._advance(work, progress, final=False)
            data = json.loads(progress.read_text(encoding="utf-8"))
            release = next(item for item in data["stages"] if item["id"] == "release_artifact")
            self.assertEqual(release["status"], "running")
            self.assertNotIn(data["status"], {"blocked", "failed"})

            run_camp_with_progress._advance(work, progress, final=True)
            data = json.loads(progress.read_text(encoding="utf-8"))
            release = next(item for item in data["stages"] if item["id"] == "release_artifact")
            self.assertEqual(release["status"], "blocked")
            self.assertEqual(data["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
