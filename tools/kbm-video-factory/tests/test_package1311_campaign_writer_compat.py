from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))


class Package1311CampaignWriterCompatTests(unittest.TestCase):
    def test_write_ad_brief_uses_campaign_brief_authority(self) -> None:
        from ad_script_writer import HOTFIX, write_ad_brief

        plan = write_ad_brief(
            "قبل از اجاره بیل مکانیکی هیدرولیک را بررسی کن.",
            {"durationSeconds": 6},
            "cinematic",
        )
        self.assertEqual(plan["editStyle"], "cinematic")
        self.assertEqual(plan["subject"], "excavator")
        self.assertTrue(plan["voiceoverScript"])
        self.assertEqual(plan["compatibilityHotfix"], HOTFIX)

    def test_orchestrator_v4_imports_without_missing_campaign_writer(self) -> None:
        module = importlib.import_module("orchestrator_v4")
        self.assertTrue(callable(module.main))


if __name__ == "__main__":
    unittest.main()
