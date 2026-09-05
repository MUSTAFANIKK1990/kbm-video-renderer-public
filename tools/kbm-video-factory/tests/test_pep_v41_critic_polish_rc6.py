from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
for item in (str(PIPELINE), str(ROOT)):
    if item not in sys.path:
        sys.path.insert(0, item)

polish = importlib.import_module("critic_polish_131")


class CriticPolishPropsTests(unittest.TestCase):
    def test_rc6_props_enforce_muted_source_single_narration_brand_and_timing(self) -> None:
        source_critic = {
            "overall": 7.71,
            "hook": 7.5,
            "shotVariety": 7.5,
            "brandVisibility": 7.0,
            "captionReadability": 7.0,
            "ctaStrength": 7.0,
            "criticComplete": True,
            "publishReady": False,
        }
        props = polish._build_props(
            duration_frames=306,
            logo_url="https://example.com/logo.png",
            narration_url="rc6-narration.mp3",
            source_sha="a" * 64,
            source_critic=source_critic,
        )
        self.assertTrue(props["criticPolish"]["enabled"])
        self.assertEqual(props["durationInFrames"], 306)
        self.assertGreaterEqual(props["captionProfile"]["bottom"], 340)
        self.assertTrue(props["captionProfile"]["pill"])
        self.assertEqual(props["brand"]["prominence"], "strong")
        self.assertTrue(props["brand"]["persistentBug"])
        self.assertTrue(props["brand"]["endCardRequired"])
        self.assertEqual(props["brand"]["logoSrc"], "https://example.com/logo.png")
        self.assertEqual(props["narration"], "rc6-narration.mp3")
        self.assertEqual(props["narrationVolume"], 1)
        self.assertTrue(props["muted"])
        self.assertEqual(props["volume"], 0)
        self.assertIn("KARYABMASHIN.IR", props["cta"])
        self.assertIn("مقایسه", props["cta"])

    def test_rc6_gate_keeps_quality_and_single_voice_contract_hard(self) -> None:
        output = Path(__file__)
        voice = {"complete": True, "durationFit": True, "takeCount": 1}
        low = polish._blockers(
            {"criticComplete": True, "overall": 7.99, "publishReady": True, "captionReadability": 8, "ctaStrength": 8, "brandVisibility": 8},
            output,
            8.0,
            voice_manifest=voice,
            output_audio_streams=1,
        )
        self.assertIn("CRITIC_BELOW_THRESHOLD", low)
        not_ready = polish._blockers(
            {"criticComplete": True, "overall": 8.2, "publishReady": False, "captionReadability": 8, "ctaStrength": 8, "brandVisibility": 8},
            output,
            8.0,
            voice_manifest=voice,
            output_audio_streams=1,
        )
        self.assertIn("CRITIC_NOT_PUBLISH_READY", not_ready)
        bad_voice = polish._blockers(
            {"criticComplete": True, "overall": 8.2, "publishReady": True, "captionReadability": 8, "ctaStrength": 8, "brandVisibility": 8},
            output,
            8.0,
            voice_manifest={"complete": True, "durationFit": True, "takeCount": 2},
            output_audio_streams=1,
        )
        self.assertIn("NARRATION_TRACK_COUNT_MISMATCH", bad_voice)
        bad_stream = polish._blockers(
            {"criticComplete": True, "overall": 8.2, "publishReady": True, "captionReadability": 8, "ctaStrength": 8, "brandVisibility": 8},
            output,
            8.0,
            voice_manifest=voice,
            output_audio_streams=2,
        )
        self.assertIn("OUTPUT_AUDIO_STREAM_COUNT_MISMATCH", bad_stream)
        self.assertEqual(polish.THRESHOLD_DEFAULT, 8.0)


class SourceContractTests(unittest.TestCase):
    def test_component_mutes_source_and_uses_one_narration_lane_and_logo(self) -> None:
        source = (ROOT / "src" / "CriticPolishReel.tsx").read_text(encoding="utf-8")
        self.assertIn("muted={true}", source)
        self.assertIn("volume={0}", source)
        self.assertIn("<Audio src={narrationSource}", source)
        self.assertIn("const brandLogo=resolveSource(props.brand?.logoSrc)", source)
        self.assertIn("<Img src={brandLogo}", source)
        self.assertIn("safeBottom=Math.max(340", source)
        self.assertIn("effectiveDurationInFrames=Math.max(1,Number(props.durationInFrames??config.durationInFrames))", source)
        self.assertIn("effectiveDurationInFrames-Math.round(fps*3.0)", source)
        self.assertIn("گزینه‌ها را در", source)
        self.assertIn("ماشین‌آلات را ببین و مقایسه کن", source)
        self.assertIn("مشاهده در کاریاب ماشین", source)
        self.assertIn("KARYABMASHIN.IR", source)
        self.assertIn("کاریاب ماشین", source)
        self.assertNotIn("muted={false}", source)
        self.assertNotIn("Package13BrandLayer", source)

    def test_root_routes_only_explicit_critic_polish_jobs(self) -> None:
        source = (ROOT / "src" / "Root.tsx").read_text(encoding="utf-8")
        self.assertIn("props.criticPolish?.enabled", source)
        self.assertIn("<CriticPolishReel", source)

    def test_python_polish_regenerates_only_one_voice_and_does_not_repeat_media_research(self) -> None:
        source = (PIPELINE / "critic_polish_131.py").read_text(encoding="utf-8")
        self.assertIn("direct_voice", source)
        self.assertIn("maximum=False", source)
        self.assertIn('"sourceAudioMuted": True', source)
        self.assertIn('"narrationTrackCount": 1', source)
        self.assertIn('"mediaResearchRepeated": False', source)
        self.assertNotIn("direct_campaign", source)
        self.assertNotIn("orchestrator_v4", source)
        self.assertIn("critique_final(output, work)", source)


if __name__ == "__main__":
    unittest.main()
