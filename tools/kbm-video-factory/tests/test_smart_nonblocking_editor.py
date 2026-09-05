from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE))

from asset_registry import load_registry, resolve_assets
from caption_aligner import align_script
from cinematic_scene_builder import build_scene_props, is_duplicate_caption
from creative_director import build_brief
from effect_router import build_effect_plan
from fallback_policy import HARD_BLOCKERS, SOFT_STAGES
from quality_control import inspect_output
from stage03_visual_edit import effect_filter
from timeline_planner import build_timeline


class Package09UnitTests(unittest.TestCase):
    def test_policy_has_small_hard_blocker_set(self) -> None:
        self.assertIn("render-all", HARD_BLOCKERS)
        self.assertIn("voiceover", SOFT_STAGES)
        self.assertNotIn("voiceover", HARD_BLOCKERS)
        self.assertIn("whisperx", SOFT_STAGES)

    def test_missing_preset_degrades_to_safe_brief(self) -> None:
        brief, fallback, reason = build_brief("missing-preset", duration_seconds=12.0)
        self.assertTrue(fallback)
        self.assertTrue(reason)
        self.assertEqual(brief["presetId"], "package09-safe-default")
        self.assertTrue(brief["voiceoverScript"])
        self.assertGreaterEqual(len(brief["overlays"]), 2)

    def test_script_alignment_creates_word_timing(self) -> None:
        cues = align_script("این یک تست فارسی کاریاب ماشین است", duration_seconds=4.0, fps=30)
        self.assertTrue(cues)
        self.assertTrue(all(cue["from"] < cue["to"] for cue in cues))
        self.assertTrue(any(cue.get("words") for cue in cues))

    def test_timeline_and_effect_router_are_semantic(self) -> None:
        brief = {"overlays": [
            {"fromSeconds": 0, "toSeconds": 2, "kind": "hook", "text": "۳ نکته مهم"},
            {"fromSeconds": 2, "toSeconds": 5, "kind": "point", "text": "قدرت موتور"},
            {"fromSeconds": 5, "toSeconds": 8, "kind": "cta", "text": "وارد کاریاب ماشین شو"}
        ]}
        timeline = build_timeline(brief, duration_seconds=8.0)
        joined = json.dumps(build_effect_plan(timeline), ensure_ascii=False)
        self.assertIn("number-pop", joined)
        self.assertIn("machine-highlight", joined)
        self.assertIn("logo-reveal", joined)

    def test_66377_stage03_edit_plan_matches_approved_voice(self) -> None:
        config = json.loads((ROOT / "config" / "66377-stage03-edit.json").read_text(encoding="utf-8"))
        planned = 0.0
        for shot in config["shots"]:
            for segment in shot["segments"]:
                planned += (float(segment["to"]) - float(segment["from"])) / float(segment.get("speed", 1.0))
            planned += float(shot.get("freezeTailSeconds", 0.0) or 0.0)
        self.assertAlmostEqual(planned, float(config["target"]["durationSeconds"]), places=3)
        self.assertEqual(config["target"]["durationSeconds"], 18.84)
        self.assertEqual(config["target"]["width"], 1080)
        self.assertEqual(config["target"]["height"], 1920)
        self.assertEqual(config["target"]["fps"], 30)
        purposes = {shot["purpose"] for shot in config["shots"]}
        self.assertIn("speed-ramp", purposes)
        self.assertIn("freeze-accent", purposes)
        self.assertIn("cta-freeze", purposes)
        self.assertIn("zoompan", effect_filter("punch-zoom"))


class Package10UnitTests(unittest.TestCase):
    def test_optional_generated_assets_fall_back_without_blocking(self) -> None:
        registry = load_registry(ROOT / "config" / "66377-cinematic-assets.json")
        with tempfile.TemporaryDirectory() as tmp:
            assets, diagnostics = resolve_assets(registry, Path(tmp))
        self.assertEqual(len(assets), 3)
        self.assertTrue(all(item["status"] == "FALLBACK" for item in diagnostics))
        self.assertTrue(all(asset["src"] is None for asset in assets))

    def test_scene_graph_matches_approved_66377_duration(self) -> None:
        config = json.loads((ROOT / "config" / "66377-cinematic-scenes.json").read_text(encoding="utf-8"))
        registry = load_registry(ROOT / "config" / "66377-cinematic-assets.json")
        props = build_scene_props(config, registry=registry, asset_dir=None)
        self.assertEqual(props["version"], "0.10.0")
        self.assertEqual(props["captionPolicy"], "single-lane")
        self.assertEqual(props["durationInFrames"], 565)
        self.assertEqual(len(props["scenes"]), 9)
        self.assertEqual(props["scenes"][-1]["kind"], "end-card")
        self.assertEqual(props["scenes"][-1]["to"], 565)

    def test_caption_de_duplication_normalizes_persian(self) -> None:
        scene = {"title": "ماشین می‌خوای؟", "accentText": ""}
        self.assertTrue(is_duplicate_caption("ماشین می‌خوای؟", scene))
        self.assertFalse(is_duplicate_caption("کاریاب ماشین سریع‌تر وصل می‌کند", scene))


class Package09IntegrationTests(unittest.TestCase):
    def test_orchestrator_survives_missing_tts_and_no_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=size=720x1280:rate=30","-t","4","-c:v","libx264","-pix_fmt","yuv420p",str(source)], check=True)
            job = "package09-unittest"
            command = [sys.executable, str(PIPELINE / "orchestrator_v2.py"), "--input", str(source), "--creative-preset", "missing-preset", "--job", job, "--skip-rough-cut", "--skip-visual-smart-cut", "--skip-transcribe", "--no-render", "--max-seconds", "4"]
            result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((ROOT / "work" / job / "job-report.json").read_text(encoding="utf-8"))
            states = {item["stage"]: item["status"] for item in report["states"]}
            self.assertIn(states["voiceover"], {"FALLBACK", "WARNING"})
            self.assertNotIn("FAILED", states.values())
            self.assertTrue((ROOT / "work" / job / "shot-plan.json").is_file())

    def test_ffmpeg_qc_accepts_standard_vertical_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "final.mp4"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=size=1080x1920:rate=30","-t","1","-c:v","libx264","-pix_fmt","yuv420p",str(output)], check=True)
            qc = inspect_output(output)
            self.assertTrue(qc["pass"], qc)


if __name__ == "__main__":
    unittest.main()
