from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CampVisualContractRc1Tests(unittest.TestCase):
    def test_root_routes_camp_before_legacy_renderers(self) -> None:
        source = (ROOT / "src" / "Root.tsx").read_text(encoding="utf-8")
        self.assertIn("CinematicAdMasterReel", source)
        self.assertIn("if(props.camp?.enabled)", source)
        self.assertLess(source.index("if(props.camp?.enabled)"), source.index("if(props.criticPolish?.mode==='website-20s')"))

    def test_master_renderer_enforces_muted_source_single_narration_brand_and_vertical_copy(self) -> None:
        source = (ROOT / "src" / "CinematicAdMasterReel.tsx").read_text(encoding="utf-8")
        # Production semantics, not implementation-format artifacts: every video lane is hard-muted.
        self.assertGreaterEqual(source.count("muted={true}"), 2)
        self.assertGreaterEqual(source.count("volume={0}"), 2)
        self.assertNotIn("muted={false}", source)
        # Exactly one narration lane is conditionally rendered by the CAMP master.
        self.assertIn("const narration=resolveSource(props.narration)", source)
        self.assertEqual(source.count("<Audio src={narration}"), 1)
        # CAMP renderer owns its first-party website frame, brand lockup, end card and vertical-specific copy.
        self.assertIn("website-walkthrough", source)
        self.assertIn("karyabmashin.ir", source)
        self.assertIn("brandName", source)
        self.assertIn("brandSite", source)
        self.assertIn("vertical==='machine-sale'", source)
        self.assertIn("ماشینت برای فروش آماده‌ست؟", source)
        self.assertIn("بازار تخصصی خرید و فروش ماشین‌آلات", source)
        self.assertIn("همین حالا آگهی فروش را ثبت کن", source)
        self.assertIn("rc7-whoosh.wav", source)
        self.assertIn("rc7-impact.wav", source)

    def test_render_router_marks_fallback_non_release(self) -> None:
        source = (ROOT / "pipeline" / "render_router.py").read_text(encoding="utf-8")
        self.assertIn('"releaseEligible": False', source)
        self.assertIn("require_remotion: bool = False", source)
        self.assertIn("CAMP_REMOTION_RENDER_REQUIRED", source)

    def test_capture_accepts_explicit_first_party_route_plan_only(self) -> None:
        source = (ROOT / "scripts" / "capture_karyabmashin_walkthrough.py").read_text(encoding="utf-8")
        self.assertIn("--routes-json", source)
        self.assertIn('url.startswith("https://karyabmashin.ir/")', source)
        self.assertIn("routesExplicit", source)
        self.assertIn("_default_routes", source)
        self.assertIn('ADS_URL = "https://karyabmashin.ir/ads/"', source)

    def test_rc7_golden_renderer_is_preserved(self) -> None:
        source = (ROOT / "src" / "CinematicWebsiteReel.tsx").read_text(encoding="utf-8")
        self.assertIn("rc7-whoosh.wav", source)
        self.assertIn("website-walkthrough", source)
        self.assertIn("playbackRate={websitePlaybackRate}", source)


if __name__ == "__main__":
    unittest.main()
