from __future__ import annotations

import base64
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

campaign_brief = importlib.import_module("campaign_brief")
creative_director = importlib.import_module("creative_director")
ad_director = importlib.import_module("ad_editorial_director")


def encode_brief(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


class CampaignBriefTests(unittest.TestCase):
    def test_persian_brief_round_trip_and_campaign_plan(self) -> None:
        text = "یک ریلز تبلیغاتی درباره اجاره بیل مکانیکی با تاکید بر بررسی جک هیدرولیک و انتخاب دستگاه مناسب بساز."
        encoded = encode_brief(text)
        with patch.dict(os.environ, {"CAMPAIGN_BRIEF_B64": encoded, "EDIT_STYLE": "high-energy"}, clear=True):
            self.assertEqual(campaign_brief.decode_campaign_brief(), text)
            plan = campaign_brief.build_campaign_plan(text, 30.0, 30)
        self.assertEqual(plan["presetId"], "auto-commercial")
        self.assertEqual(plan["language"], "fa-IR")
        self.assertEqual(plan["editStyle"], "high-energy")
        self.assertIn("بیل مکانیکی", plan["voiceoverScript"])
        self.assertIn("کاریاب ماشین", plan["voiceoverScript"])
        self.assertEqual(plan["subject"], "excavator")

    def test_invalid_or_oversized_brief_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            campaign_brief.decode_campaign_brief("bad+/encoding")
        oversized = encode_brief("الف" * 601)
        with self.assertRaises(ValueError):
            campaign_brief.decode_campaign_brief(oversized)

    def test_creative_director_prioritizes_campaign_brief_before_preset(self) -> None:
        text = "تبلیغ خدمات تعمیر و سرویس ماشین آلات سنگین با دعوت به کاریاب ماشین"
        with patch.dict(os.environ, {"CAMPAIGN_BRIEF_B64": encode_brief(text), "EDIT_STYLE": "cinematic"}, clear=True):
            plan, fallback, reason = creative_director.build_brief(
                "excavator-rental-3-checks",
                duration_seconds=24.0,
                fps=30,
            )
        self.assertFalse(fallback)
        self.assertIsNone(reason)
        self.assertEqual(plan["authority"], "package13-campaign-brief")
        self.assertEqual(plan["editStyle"], "cinematic")
        self.assertIn("تعمیر", plan["voiceoverScript"])


class EditorialStyleTests(unittest.TestCase):
    def _board(self, style_name: str):
        brief = {
            "title": "اجاره بیل مکانیکی",
            "subtitle": "انتخاب دقیق‌تر",
            "cta": "در کاریاب ماشین ببین",
            "subject": "excavator",
            "editStyle": style_name,
            "voiceoverScript": "قبل از اجاره بیل مکانیکی وضعیت دستگاه را بررسی کن. جک هیدرولیک را ببین. شرایط کار را مقایسه کن.",
        }
        with patch.dict(os.environ, {"EDIT_STYLE": style_name}, clear=True):
            return ad_director.build_ad_storyboard(brief, 30.0, {"visualResetSeconds": 2.4})

    def test_high_energy_creates_more_visual_resets_than_cinematic(self) -> None:
        high = self._board("high-energy")
        cinematic = self._board("cinematic")
        self.assertEqual(high["editStyle"], "high-energy")
        self.assertEqual(cinematic["editStyle"], "cinematic")
        self.assertLess(high["visualResetTargetSeconds"], cinematic["visualResetTargetSeconds"])
        self.assertGreaterEqual(len(high["scenes"]), len(cinematic["scenes"]))
        self.assertGreater(high["policy"]["brollTargetRatio"], cinematic["policy"]["brollTargetRatio"])
        self.assertTrue(any(scene["transition"] == "flash" for scene in high["scenes"]))


class FullStackContractTests(unittest.TestCase):
    def test_studio_worker_workflow_contract_is_complete(self) -> None:
        html = (ROOT / "cloud" / "dist" / "index.html").read_text(encoding="utf-8")
        worker = (ROOT / "cloud" / "src" / "index.ts").read_text(encoding="utf-8")
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "kbm-video-render-free.yml").read_text(encoding="utf-8")
        self.assertIn("PACKAGE 13 · FULL CINEMATIC", html)
        self.assertIn('id="brief"', html)
        self.assertIn("X-KBM-Brief-B64", html)
        self.assertIn("X-KBM-Edit-Style", html)
        self.assertIn("BRIEF_B64_RE", worker)
        self.assertIn("validateCampaignBriefB64", worker)
        self.assertIn("campaign_brief_b64: options.campaignBriefB64", worker)
        self.assertIn("edit_style: options.editStyle", worker)
        self.assertIn("campaign_brief_b64:", workflow)
        self.assertIn("CAMPAIGN_BRIEF_B64: ${{ inputs.campaign_brief_b64 }}", workflow)
        self.assertIn("EDIT_STYLE: ${{ inputs.edit_style }}", workflow)
        self.assertIn("vars.KBM_PIPELINE_MODE || 'v4'", workflow)


if __name__ == "__main__":
    unittest.main()
