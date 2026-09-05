from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CampFinalGateHotfix03Tests(unittest.TestCase):
    def test_root_uses_adaptive_camp_renderer(self) -> None:
        root = (ROOT / "src" / "Root.tsx").read_text(encoding="utf-8")
        self.assertIn("CinematicAdMasterReelV4", root)
        self.assertIn("if(props.camp?.enabled)return <CinematicAdMasterReelV4", root)

    def test_adaptive_renderer_uses_external_broll_and_short_website_window(self) -> None:
        source = (ROOT / "src" / "CinematicAdMasterReelV4.tsx").read_text(encoding="utf-8")
        self.assertIn("['pexels','pixabay','cupai-generated','kbm-owned']", source)
        self.assertIn("without falling back to an already-captioned source frame", source)
        self.assertIn("external.slice(0,repair>0?8:7)", source)
        self.assertIn("repairFlags", source)
        self.assertIn("websiteStart", source)
        self.assertNotIn("muted={false}", source)

    def test_persian_voice_budget_is_calibrated_without_lowering_release_gate(self) -> None:
        voice = (ROOT / "pipeline" / "avalai_voice_director.py").read_text(encoding="utf-8")
        protocol = (ROOT / "pipeline" / "cinematic_ad_protocol.py").read_text(encoding="utf-8")
        self.assertIn("words_per_second = 1.45 if _is_persian", voice)
        self.assertIn("max_seconds * 0.84", voice)
        self.assertIn("_speed_fit_take", voice)
        self.assertIn("min(1.22", voice)
        self.assertIn('"overall": 8.3', protocol)
        self.assertIn('"clipRatioMax": 0.0002', protocol)

    def test_audio_mastering_measures_encoded_output_and_bounds_repairs(self) -> None:
        audio = (ROOT / "pipeline" / "audio_mastering.py").read_text(encoding="utf-8")
        self.assertIn("post_encode_evidence = analyze_audio(path)", audio)
        self.assertIn("correction_profiles = [", audio)
        self.assertEqual(audio.count('"lufs": -11.5'), 1)
        self.assertEqual(audio.count('"lufs": -10.5'), 1)
        self.assertIn('"status": "PASS" if _gate_pass(post_encode_evidence)', audio)


if __name__ == "__main__":
    unittest.main()
