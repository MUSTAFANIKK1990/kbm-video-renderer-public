from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

SPEC = importlib.util.spec_from_file_location("cinematic_website_20s_131", PIPELINE / "cinematic_website_20s_131.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Rc7CinematicWebsiteContractTests(unittest.TestCase):
    def test_duration_and_candidate_are_explicit(self) -> None:
        self.assertEqual(MODULE.CANDIDATE, "13.1.2-rc.7")
        self.assertEqual(MODULE.TARGET_SECONDS, 20.0)
        self.assertEqual(MODULE.TARGET_FRAMES, 600)
        self.assertEqual(MODULE.SOURCE_EXPECTED_CANDIDATE, "13.1.2-rc.6")

    def test_narration_is_question_led_and_bounded(self) -> None:
        script = MODULE.NARRATION_SCRIPT
        self.assertIn("اجاره نرفته؟", script)
        self.assertIn("خسته شدی؟", script)
        self.assertIn("کاریاب ماشین", script)
        self.assertIn("KARYABMASHIN.IR", script)
        self.assertLessEqual(len(script.split()), 32)

    def test_props_require_real_website_asset_and_clean_brand(self) -> None:
        props = MODULE._build_props(
            source_sha="a" * 64,
            website_sha="b" * 64,
            logo_url="https://example.com/logo.png",
            narration_url="rc7-narration.mp3",
            source_critic={"overall": 8.22},
        )
        self.assertEqual(props["durationInFrames"], 600)
        self.assertEqual(props["criticPolish"]["mode"], "website-20s")
        self.assertFalse(props["brand"]["persistentBug"])
        self.assertTrue(props["rc7"]["legacyCornerBadgeMasked"])
        asset = next(item for item in props["assets"] if item["id"] == "website-walkthrough")
        self.assertEqual(asset["provider"], "karyabmashin-live-site")
        self.assertEqual(asset["sourceUrl"], "https://karyabmashin.ir/")
        self.assertEqual(asset["license"], "first-party-site-capture")

    def test_renderer_contains_browser_walkthrough_and_mobile_readability_guards(self) -> None:
        source = (ROOT / "src" / "CinematicWebsiteReel.tsx").read_text(encoding="utf-8")
        self.assertIn("website-walkthrough", source)
        self.assertIn("karyabmashin.ir", source)
        self.assertIn("height:198", source)
        self.assertIn("height:820", source)
        self.assertIn("rc7-whoosh.wav", source)
        self.assertIn("rc7-bed.wav", source)
        self.assertIn("playbackRate={websitePlaybackRate}", source)
        self.assertIn("startFrom={Math.round(fps*1.0)}", source)
        self.assertIn("ماشینت را همین حالا آگهی کن", source)
        self.assertIn("ورود و ثبت آگهی", source)
        self.assertNotIn(">بازار تخصصی ماشین‌آلات</div>", source)

    def test_capture_script_uses_only_first_party_public_routes(self) -> None:
        source = (ROOT / "scripts" / "capture_karyabmashin_walkthrough.py").read_text(encoding="utf-8")
        self.assertIn('BASE_URL = "https://karyabmashin.ir/"', source)
        self.assertIn('ADS_URL = "https://karyabmashin.ir/ads/"', source)
        self.assertIn("expected = 90", source)
        self.assertNotIn("project-login", source)
        self.assertNotIn("submit-ad", source)


if __name__ == "__main__":
    unittest.main()
