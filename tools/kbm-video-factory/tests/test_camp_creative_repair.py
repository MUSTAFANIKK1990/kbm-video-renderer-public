from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CreativeRepairCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "src" / "CinematicAdMasterReelV4.tsx").read_text(encoding="utf-8")

    def test_hook_is_problem_led_and_specific(self) -> None:
        self.assertIn("بازدید هست، تماس نیست؟", self.source)
        self.assertIn("ماشینت هنوز فروش نرفته؟", self.source)

    def test_static_images_receive_directional_motion_and_entry_transition(self) -> None:
        self.assertIn("translate3d(", self.source)
        self.assertIn("rotate(", self.source)
        self.assertIn("const entry=interpolate", self.source)
        self.assertIn("translateX(", self.source)

    def test_caption_progression_uses_three_distinct_layouts(self) -> None:
        self.assertIn("const cueBottom=[430,340,390]", self.source)
        self.assertIn("const cueInset=[54,112,72]", self.source)
        self.assertIn("cueIndex===1?accent", self.source)
        self.assertIn("عکس واضح، اعتماد خریدار را می‌سازد", self.source)

    def test_website_proof_is_larger_slower_and_held_longer(self) -> None:
        self.assertIn("repair>=2?3.35:2.5", self.source)
        self.assertIn("left:30,right:30,top:95,bottom:215", self.source)
        self.assertIn("playbackRate={1.45}", self.source)

    def test_cta_is_actionable_and_domain_remains_separate(self) -> None:
        self.assertIn("وارد سایت شو؛ آگهی ماشینت را همین حالا ثبت کن", self.source)
        self.assertIn("{site}", self.source)
        self.assertIn("برای ثبت آگهی وارد سایت شو", self.source)

    def test_preserved_final_mix_does_not_double_music_or_sfx(self) -> None:
        self.assertIn("preserveMixedAudio", self.source)
        self.assertIn("!preserveMixedAudio?", self.source)


class CreativeRepairRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "pipeline" / "camp_creative_repair_resume.py").read_text(encoding="utf-8")

    def test_runner_is_pinned_to_immutable_source_artifact(self) -> None:
        self.assertIn('EXPECTED_ARTIFACT_ID = "9757678320"', self.source)
        self.assertIn("sha256:f65ee12f9dfd255b2d67f5d1577578015fcd6005dd51f6469d751bfc6d1fb0e6", self.source)
        self.assertIn("SOURCE_FINAL_MP4_SHA256_MISMATCH", self.source)

    def test_runner_reuses_audio_and_assets_without_expensive_generation(self) -> None:
        self.assertIn('"ttsExecuted": False', self.source)
        self.assertIn('"mediaResearchExecuted": False', self.source)
        self.assertIn('"mediaGenerationExecuted": False', self.source)
        self.assertIn('"engine": "immutable-final-mix-reuse"', self.source)
        self.assertNotIn("synthesize_speech(", self.source)
        self.assertNotIn("direct_voice(", self.source)

    def test_runner_uses_current_cupai_critic_and_hard_release_gate(self) -> None:
        self.assertIn("critic = critique_final(output, work)", self.source)
        self.assertIn("report = release_gate(", self.source)
        self.assertIn('"provider"] = "cupai-generated"', self.source)
        self.assertNotIn("AVALAI_API_KEY", self.source)


if __name__ == "__main__":
    unittest.main()
