#!/usr/bin/env python3
from __future__ import annotations
import os
import sys
import unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import ad_editorial_director
import campaign_brief
class ReferenceReelGrammarTests(unittest.TestCase):
    def test_rights_clean_reference_grammar_is_loaded(self) -> None:
        profile = campaign_brief.reference_editing_profile()
        self.assertEqual(profile["profileId"], "kbm-reference-reel-v1")
        self.assertLessEqual(float(profile["hookMaxSeconds"]), 1.5)
        self.assertLessEqual(float(profile["visualResetTargetSeconds"]), 1.55)
        self.assertIn("do not reuse", profile["sourcePolicy"].lower())
    def test_high_energy_storyboard_emits_reference_proof_beats(self) -> None:
        with mock.patch.dict(os.environ, {"EDIT_STYLE": "high-energy"}, clear=False):
            plan = campaign_brief.build_campaign_plan("فروش بیل مکانیکی با جزئیات واقعی و امکان مقایسه آگهی‌ها", 20)
        storyboard = ad_editorial_director.build_ad_storyboard(plan, 20, {"visualResetSeconds": 1.55, "transitions": ["hard", "flash", "push"]})
        self.assertEqual(storyboard["referenceEditingProfile"]["profileId"], "kbm-reference-reel-v1")
        self.assertLessEqual(float(storyboard["visualResetTargetSeconds"]), 1.55)
        self.assertEqual(storyboard["scenes"][0]["referenceMotif"], "hook-impact")
        body = [scene for scene in storyboard["scenes"] if scene["beatRole"] == "body"]
        self.assertTrue(body)
        self.assertTrue(any(scene.get("proofBadge") for scene in body))
    def test_camp_renderer_consumes_reference_profile_without_reusing_media(self) -> None:
        renderer = (ROOT / "src" / "CinematicAdMasterReelV4.tsx").read_text(encoding="utf-8")
        self.assertIn("referenceEditingProfile", renderer)
        self.assertIn("visualResetSeconds", renderer)
        self.assertIn("proofBadges", renderer)
        self.assertNotIn("84310.mp4", renderer)
        self.assertNotIn("84309.mp4", renderer)
if __name__ == "__main__":
    unittest.main()
