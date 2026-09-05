from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

SPEC = importlib.util.spec_from_file_location("cinematic_ad_protocol", PIPELINE / "cinematic_ad_protocol.py")
assert SPEC and SPEC.loader
CAMP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMP)

from asset_router import route_assets
from brand_director import _owned_asset


class CampProtocolRc1Tests(unittest.TestCase):
    def test_authority_and_quality_floors_are_strict(self) -> None:
        self.assertEqual(CAMP.VERSION, "13.2.0-rc.1")
        self.assertEqual(CAMP.AUTHORITY, "KBM-CAMP-13.2-CINEMATIC-AD-MASTER-AUTHORITY")
        self.assertEqual(CAMP.CRITIC_FLOORS["overall"], 8.3)
        self.assertEqual(CAMP.CRITIC_FLOORS["brollRelevance"], 8.3)
        self.assertEqual(CAMP.CRITIC_FLOORS["captionReadability"], 8.3)
        self.assertEqual(CAMP.AUDIO_LIMITS["technicalAudioScore"], 8.2)
        self.assertLessEqual(CAMP.AUDIO_LIMITS["clipRatioMax"], 0.0002)

    def test_normalize_brief_builds_master_story_arc(self) -> None:
        brief = CAMP.normalize_brief(topic="خرید و فروش ماشین‌آلات", vertical="machine-sale", duration_seconds=20)
        self.assertEqual(brief["vertical"], "machine-sale")
        self.assertEqual(brief["durationSeconds"], 20.0)
        self.assertEqual(brief["storyArc"][0], "hook")
        self.assertEqual(brief["storyArc"][-1], "cta")
        self.assertEqual(brief["releasePolicy"], "hard-gate")

    def test_unknown_vertical_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CAMP.normalize_brief(topic="test", vertical="unknown-vertical")

    def test_fallback_renderer_can_never_release(self) -> None:
        result = CAMP.validate_renderer({"renderer": "ffmpeg", "fallback": True})
        self.assertFalse(result["pass"])
        self.assertIn("CAMP_REMOTION_RENDER_REQUIRED", result["blockers"])
        self.assertIn("CAMP_FALLBACK_RENDER_NOT_RELEASABLE", result["blockers"])

    def test_critic_requires_every_floor_not_only_average(self) -> None:
        critic = {
            "criticComplete": True,
            "publishReady": True,
            "overall": 9.0,
            "hook": 9.0,
            "pacing": 9.0,
            "brollRelevance": 9.0,
            "shotVariety": 9.0,
            "brandVisibility": 9.0,
            "captionReadability": 9.0,
            "audioEnergy": 9.0,
            "ctaStrength": 7.0,
        }
        result = CAMP.validate_critic(critic)
        self.assertFalse(result["pass"])
        self.assertIn("CRITIC_CTASTRENGTH_BELOW_CAMP_FLOOR", result["blockers"])

    def test_critic_pass_contract(self) -> None:
        critic = {"criticComplete": True, "publishReady": True}
        critic.update({key: floor + 0.1 for key, floor in CAMP.CRITIC_FLOORS.items()})
        result = CAMP.validate_critic(critic)
        self.assertTrue(result["pass"])
        self.assertEqual(result["blockers"], [])

    def test_rights_evidence_is_mandatory(self) -> None:
        result = CAMP.validate_rights({})
        self.assertFalse(result["pass"])
        self.assertIn("RIGHTS_EVIDENCE_MISSING", result["blockers"])

    def test_watermark_and_visual_stagnation_block_release(self) -> None:
        result = CAMP.validate_visual({
            "thirdPartyWatermarkDetected": True,
            "brandPresent": True,
            "maxUnchangedSeconds": 3.1,
        })
        self.assertFalse(result["pass"])
        self.assertIn("THIRD_PARTY_WATERMARK", result["blockers"])
        self.assertIn("VISUAL_STAGNATION", result["blockers"])

    def test_materialized_asset_preserves_authoritative_rights_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="camp-rights-") as temporary:
            root = Path(temporary)
            generated = root / "generated.mp4"
            generated.write_bytes(b"x" * 2048)
            previous = os.environ.get("KBM_PACKAGE131_MEDIA_DIR")
            os.environ["KBM_PACKAGE131_MEDIA_DIR"] = str(root)
            try:
                report = route_assets(
                    {
                        "requests": [{"id": "media-scene-1", "sceneId": "scene-1", "mediaType": "video"}],
                        "candidates": [{
                            "requestId": "media-scene-1",
                            "sceneId": "scene-1",
                            "mediaType": "video",
                            "provider": "cupai-generated",
                            "providerId": "generated-1",
                            "sourceUrl": "https://karyabmashin.ir/",
                            "license": "KBM-OWNED",
                            "attribution": "KBM",
                            "localPath": str(generated),
                            "shotRole": "detail",
                            "rightsDecision": {"approved": True},
                        }],
                    },
                    root / "public",
                    materialize=True,
                )
            finally:
                if previous is None:
                    os.environ.pop("KBM_PACKAGE131_MEDIA_DIR", None)
                else:
                    os.environ["KBM_PACKAGE131_MEDIA_DIR"] = previous
            self.assertEqual(len(report["assets"]), 1)
            asset = report["assets"][0]
            self.assertEqual(asset["provider"], "cupai-generated")
            self.assertEqual(asset["license"], "KBM-OWNED")
            self.assertEqual(asset["sourceUrl"], "https://karyabmashin.ir/")
            self.assertEqual(asset["shotRole"], "detail")
            self.assertTrue(asset["rightsDecision"]["approved"])

    def test_official_brand_asset_is_explicitly_first_party(self) -> None:
        asset = _owned_asset("generated/test/brand/kbm-logo.png", source_url="https://karyabmashin.ir/logo.png")
        self.assertEqual(asset["provider"], "kbm-owned")
        self.assertEqual(asset["license"], "KBM-OWNED")
        self.assertTrue(asset["rightsApproved"])

    def test_camp_audio_master_uses_calibrated_dynamic_chain_without_gate_relaxation(self) -> None:
        source = (PIPELINE / "audio_mastering.py").read_text(encoding="utf-8")
        self.assertIn("camp_strict = requested_true_peak <= -1.5", source)
        self.assertIn("acompressor=threshold=0.10:ratio=4", source)
        self.assertIn("linear=false", source)
        self.assertIn("-2.0 if camp_strict", source)
        self.assertIn("limiter_ceiling_db = -1.4 if camp_strict", source)
        self.assertIn("camp-strict-premeasure-dynamic-loudnorm-postlimiter-calibrated", source)
        self.assertEqual(CAMP.AUDIO_LIMITS["lufsMin"], -16.0)
        self.assertEqual(CAMP.AUDIO_LIMITS["lufsMax"], -12.0)
        self.assertEqual(CAMP.AUDIO_LIMITS["clipRatioMax"], 0.0002)

    def test_camp_visual_evidence_has_deterministic_render_contract(self) -> None:
        source = (PIPELINE / "orchestrator_camp.py").read_text(encoding="utf-8")
        self.assertIn('editorial["legacyCornerBadgeMasked"] = True', source)
        self.assertIn('editorial["brandLayerPolicy"] = "single-active-lockup"', source)
        self.assertIn('editorial["shotRoleContract"]', source)
        self.assertIn("cinematic-ad-master-render-contract+asset-routing", source)
        self.assertIn("trusted-provider-provenance+first-party-site-capture", source)
        self.assertIn("single-active-lockup+legacy-corner-mask", source)


if __name__ == "__main__":
    unittest.main()
