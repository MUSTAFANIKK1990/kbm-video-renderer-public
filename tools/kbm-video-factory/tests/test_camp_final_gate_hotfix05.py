from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

import asset_router  # noqa: E402
import avalai_creative_intelligence  # noqa: E402
import avalai_voice_director  # noqa: E402
import broll_scout  # noqa: E402


class Hotfix05SemanticTests(unittest.TestCase):
    def test_search_query_cannot_score_itself(self) -> None:
        item = {
            "query": "excavator hydraulic close up detail",
            "sourceUrl": "https://www.pexels.com/video/industrial-machining-process-in-workshop-30409129/",
            "title": "industrial machining process in workshop",
        }
        score = broll_scout._semantic_relevance(item, "excavator hydraulic close up detail")
        self.assertLess(score, 0.28)

    def test_related_source_slug_scores_above_unrelated(self) -> None:
        query = "excavator digging working action"
        related = {"sourceUrl": "https://www.pexels.com/video/excavator-operating-at-construction-site-34521511/"}
        unrelated = {"sourceUrl": "https://www.pexels.com/video/industrial-machining-process-in-workshop-30409129/"}
        self.assertGreater(broll_scout._semantic_relevance(related, query), broll_scout._semantic_relevance(unrelated, query))


class Hotfix05MediaDiversityTests(unittest.TestCase):
    def test_camp_machine_sale_requests_expand_to_seven(self) -> None:
        storyboard = {
            "scenes": [
                {"id": "one", "kind": "broll", "copy": "خرید و فروش ماشین آلات سنگین"},
                {"id": "two", "kind": "image", "copy": "ثبت آگهی فروش ماشین آلات"},
            ]
        }
        with mock.patch.dict(os.environ, {"KBM_CAMP_MEDIA_DIVERSITY": "1", "KBM_CAMP_MEDIA_PROFILE": "machine-sale"}, clear=False):
            requests = broll_scout._requests(storyboard)
        self.assertGreaterEqual(len(requests), 7)
        roles = {str(item.get("shotRole")) for item in requests}
        self.assertIn("operation", roles)
        self.assertIn("context", roles)
        self.assertTrue("closeup" in roles or "detail" in roles)

    def test_asset_router_avoids_global_duplicate_identity(self) -> None:
        shared = {
            "provider": "pexels", "providerId": "A", "sourceUrl": "https://pexels.example/A",
            "downloadUrl": "https://videos.pexels.com/A.mp4", "mediaType": "video", "semanticRelevance": .9, "score": .9,
            "rightsDecision": {"approved": True},
        }
        alt = {
            "provider": "pexels", "providerId": "B", "sourceUrl": "https://pexels.example/B",
            "downloadUrl": "https://videos.pexels.com/B.mp4", "mediaType": "video", "semanticRelevance": .85, "score": .85,
            "rightsDecision": {"approved": True},
        }
        report = {
            "requests": [
                {"id": "r1", "sceneId": "s1", "mediaType": "video"},
                {"id": "r2", "sceneId": "s2", "mediaType": "video"},
            ],
            "candidates": [
                {**shared, "requestId": "r1"},
                {**shared, "requestId": "r2"},
                {**alt, "requestId": "r2"},
            ],
        }
        routed = asset_router.route_assets(report, Path("unused"), materialize=False)
        ids = [str(item.get("providerId")) for item in routed["selected"]]
        self.assertEqual(ids, ["A", "B"])
        self.assertEqual(routed["duplicateSelectedCount"], 0)


class Hotfix05VoiceSelectionTests(unittest.TestCase):
    def test_duration_fit_wins_after_dynamics_floor_is_satisfied(self) -> None:
        pool = [
            {"take": "commercial", "duration": 18.456, "voiceDynamics": 9.7},
            {"take": "industrial", "duration": 11.664, "voiceDynamics": 9.2},
            {"take": "social", "duration": 14.760, "voiceDynamics": 9.5},
        ]
        selected = avalai_voice_director._select_take(pool, 15.0, dynamics_floor=8.0)
        self.assertEqual(selected["take"], "social")

    def test_partial_optional_take_failure_does_not_mark_director_incomplete(self) -> None:
        def fake_synthesize(_text: str, destination: Path, *, voice: str, instructions: str) -> dict[str, object]:
            if "industrial" in destination.name:
                raise RuntimeError("temporary provider failure")
            destination.write_bytes(b"fake-audio")
            return {
                "model": "fake-tts",
                "voice": voice,
                "bytes": destination.stat().st_size,
                "path": str(destination),
                "contentType": "audio/mpeg",
            }

        with tempfile.TemporaryDirectory(prefix="kbm-hotfix05-voice-") as temporary:
            work = Path(temporary)
            with (
                mock.patch.object(avalai_voice_director, "synthesize_speech", side_effect=fake_synthesize),
                mock.patch.object(avalai_voice_director, "_duration", return_value=14.0),
                mock.patch.object(avalai_voice_director, "_voice_dynamics", return_value=(8.7, {"technicalAudioScore": 9.0})),
                mock.patch.object(avalai_voice_director, "classify_cupai_error", return_value={"code": "TEMPORARY", "retryable": True, "quotaBlocked": False}),
            ):
                manifest = avalai_voice_director.direct_voice(
                    "ماشین‌آلات واقعی را بررسی کن و گزینه‌ها را در کاریاب ماشین ببین.",
                    work,
                    voice="alloy",
                    max_seconds=20.0,
                    maximum=True,
                )

        self.assertTrue(manifest["complete"])
        self.assertTrue(manifest["selectedTakePlayable"])
        self.assertTrue(manifest["durationFit"])
        self.assertFalse(manifest["allRequestedTakesGenerated"])
        self.assertTrue(manifest["partialTakeFailure"])
        self.assertEqual(manifest["takeCount"], 2)
        self.assertEqual(len(manifest["failures"]), 1)
        self.assertEqual(manifest["completionPolicy"], "selected-decodable-take-v1")


class Hotfix05ProgressiveRepairTests(unittest.TestCase):
    def test_repair_pass_increments_and_sets_targeted_flags(self) -> None:
        props = {"editorial": {"repairPass": 0}, "camp": {"vertical": "machine-sale"}, "cta": "ثبت آگهی"}
        critic = {
            "hook": 8.0, "pacing": 7.0, "brollRelevance": 8.0, "shotVariety": 7.0,
            "brandVisibility": 9.0, "captionReadability": 8.0, "ctaStrength": 7.0,
            "visualEvidence": {"visualStagnationRisk": True},
        }
        first = avalai_creative_intelligence.apply_bounded_repairs(props, critic)
        second = avalai_creative_intelligence.apply_bounded_repairs(first, critic)
        self.assertEqual(first["editorial"]["repairPass"], 1)
        self.assertEqual(second["editorial"]["repairPass"], 2)
        self.assertTrue(second["editorial"]["repairFlags"]["stagnation"])
        self.assertTrue(second["editorial"]["repairFlags"]["cta"])
        self.assertIn("KARYABMASHIN.IR", second["cta"])


class Hotfix05RendererAuthorityTests(unittest.TestCase):
    def test_root_routes_camp_to_v4(self) -> None:
        root = (ROOT / "src" / "Root.tsx").read_text(encoding="utf-8")
        v4 = (ROOT / "src" / "CinematicAdMasterReelV4.tsx").read_text(encoding="utf-8")
        self.assertIn("CinematicAdMasterReelV4", root)
        self.assertIn("if(props.camp?.enabled)return <CinematicAdMasterReelV4", root)
        self.assertIn("without falling back to an already-captioned source frame", v4)
        self.assertNotIn("poolIndex%external.length", v4)


if __name__ == "__main__":
    unittest.main()
