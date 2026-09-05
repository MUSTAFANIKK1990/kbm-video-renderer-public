from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

import cinematic_ad_protocol  # noqa: E402


class Hotfix06QualityFloorTests(unittest.TestCase):
    def test_camp_quality_floors_are_not_weakened(self) -> None:
        floors = cinematic_ad_protocol.CRITIC_FLOORS
        self.assertEqual(floors["brandVisibility"], 8.3)
        self.assertEqual(floors["ctaStrength"], 8.3)
        self.assertEqual(floors["overall"], 8.3)
        self.assertEqual(floors["hook"], 8.2)
        self.assertEqual(floors["pacing"], 8.0)
        self.assertEqual(floors["brollRelevance"], 8.3)
        self.assertEqual(floors["shotVariety"], 8.0)
        self.assertEqual(floors["captionReadability"], 8.3)
        self.assertEqual(floors["audioEnergy"], 8.2)


class Hotfix06EndCardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "src" / "CinematicAdMasterReelV4.tsx").read_text(encoding="utf-8")
        cls.root = (ROOT / "src" / "Root.tsx").read_text(encoding="utf-8")

    def test_camp_still_uses_single_v4_renderer_authority(self) -> None:
        self.assertIn("if(props.camp?.enabled)return <CinematicAdMasterReelV4", self.root)
        self.assertNotIn("CinematicAdMasterReelV5", self.root)

    def test_machine_sale_cta_is_direct_and_url_is_separate(self) -> None:
        self.assertIn("همین حالا آگهی فروش ماشینت را ثبت کن", self.source)
        self.assertIn("برای ثبت آگهی وارد سایت شو", self.source)
        self.assertIn("{site}", self.source)
        self.assertNotIn("همین حالا در KARYABMASHIN.IR آگهی فروش را ثبت کن", self.source)

    def test_final_brand_lockup_is_prominent_but_not_duplicate(self) -> None:
        self.assertIn("width:230,height:230", self.source)
        self.assertIn("fontSize:82", self.source)
        self.assertIn("fontSize:48", self.source)
        self.assertIn("fontSize:49", self.source)
        self.assertIn("width:54,height:56", self.source)

    def test_end_card_is_animated_and_bounded(self) -> None:
        self.assertIn("machineSale?(repair?4.2:3.9)", self.source)
        self.assertIn("logoScale=interpolate", self.source)
        self.assertIn("ctaOpacity=interpolate", self.source)
        self.assertIn("siteOpacity=interpolate", self.source)
        self.assertIn("haloShift=interpolate", self.source)


if __name__ == "__main__":
    unittest.main()
