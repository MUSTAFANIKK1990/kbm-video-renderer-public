from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

ad_director = importlib.import_module("ad_editorial_director")
asset_router = importlib.import_module("asset_router")
brand_director = importlib.import_module("brand_director")
broll_scout = importlib.import_module("broll_scout")
providers = importlib.import_module("providers")
rights_gate = importlib.import_module("rights_gate")
timeline_compiler = importlib.import_module("timeline_compiler")


class RightsGateTests(unittest.TestCase):
    def test_pexels_and_pixabay_official_hosts_are_approved(self) -> None:
        cases = [
            {"provider": "pexels", "license": "PEXELS", "downloadUrl": "https://videos.pexels.com/video-files/123/file.mp4", "sourceUrl": "https://www.pexels.com/video/123/"},
            {"provider": "pixabay", "license": "PIXABAY", "downloadUrl": "https://pixabay.com/get/example.jpg", "sourceUrl": "https://pixabay.com/photos/example-1/"},
        ]
        for case in cases:
            with self.subTest(provider=case["provider"]): self.assertTrue(rights_gate.evaluate(case)["approved"])

    def test_unknown_license_or_wrong_host_is_rejected(self) -> None:
        unknown = {"provider": "random-web", "license": "UNKNOWN", "downloadUrl": "https://example.com/video.mp4", "sourceUrl": "https://example.com/page"}
        wrong_host = {"provider": "pexels", "license": "PEXELS", "downloadUrl": "https://evil.example/video.mp4", "sourceUrl": "https://www.pexels.com/video/123/"}
        self.assertFalse(rights_gate.evaluate(unknown)["approved"])
        self.assertFalse(rights_gate.evaluate(wrong_host)["approved"])


class ProviderFallbackTests(unittest.TestCase):
    def test_public_providers_do_not_touch_network_without_keys(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(providers.pexels_provider.configured())
            self.assertFalse(providers.pixabay_provider.configured())
            self.assertEqual(providers.pexels_provider.search_videos("excavator"), [])
            self.assertEqual(providers.pixabay_provider.search_images("excavator"), [])

    def test_iran_gateway_requires_https_and_explicit_token(self) -> None:
        with patch.dict(os.environ, {"KBM_IRAN_MEDIA_SEARCH_URL": "http://example.ir/search", "KBM_IRAN_MEDIA_SEARCH_TOKEN": "token"}, clear=True):
            with self.assertRaises(RuntimeError): providers.iran_media_provider.search_videos("بیل مکانیکی")


class EditorialDirectorTests(unittest.TestCase):
    def test_storyboard_has_hook_multisource_body_and_cta(self) -> None:
        brief = {"title": "سه نکته اجاره بیل مکانیکی", "subtitle": "قبل از اجاره بررسی کن", "cta": "آگهی‌های کاریاب ماشین را ببین", "subject": "excavator-rental", "voiceoverScript": "قبل از اجاره بیل مکانیکی بدنه و جک هیدرولیک را بررسی کن. کابین و اپراتور را ببین. در پایان شرایط اجاره را مقایسه کن."}
        style = {"visualResetSeconds": 1.8, "transitions": ["hard", "push", "flash", "wipe"]}
        board = ad_director.build_ad_storyboard(brief, 24.0, style)
        scenes = board["scenes"]
        self.assertGreaterEqual(len(scenes), 8)
        self.assertEqual(scenes[0]["beatRole"], "hook")
        self.assertEqual(scenes[-1]["beatRole"], "cta")
        self.assertEqual(scenes[-1]["kind"], "end-card")
        self.assertTrue(any(scene["kind"] == "broll" for scene in scenes))
        self.assertTrue(any(scene["kind"] == "image" for scene in scenes))
        self.assertTrue(all(float(scene["toSeconds"]) > float(scene["fromSeconds"]) for scene in scenes))
        self.assertEqual(len(board["energyCurve"]), len(scenes))

    def test_scout_disabled_is_non_blocking(self) -> None:
        board = {"scenes": [{"id": "a", "kind": "broll", "copy": "بیل مکانیکی", "searchQuery": "excavator"}, {"id": "b", "kind": "image", "copy": "هیدرولیک", "searchQuery": "hydraulic"}]}
        result = broll_scout.scout(board, enabled=False)
        self.assertFalse(result["enabled"])
        self.assertEqual(len(result["requests"]), 2)
        self.assertEqual(result["candidates"], [])


class AssetAndBrandTests(unittest.TestCase):
    def test_router_keeps_rights_manifest_without_materializing(self) -> None:
        scout = {"requests": [{"id": "media-x", "sceneId": "x", "mediaType": "video"}], "candidates": [{"requestId": "media-x", "sceneId": "x", "mediaType": "video", "provider": "pexels", "providerId": "1", "downloadUrl": "https://videos.pexels.com/video-files/1/file.mp4", "sourceUrl": "https://www.pexels.com/video/1/", "creator": "Creator", "license": "PEXELS", "attribution": "Video by Creator on Pexels", "rightsDecision": {"approved": True}}]}
        with tempfile.TemporaryDirectory() as temporary:
            result = asset_router.route_assets(scout, Path(temporary), materialize=False)
        self.assertEqual(result["assets"], [])
        self.assertEqual(len(result["rights"]), 1)
        self.assertTrue(result["rights"][0]["rightsApproved"])
        self.assertFalse(result["rights"][0]["materialized"])

    def test_brand_missing_never_fabricates_logo_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            fake_root = Path(temporary) / "tools" / "kbm-video-factory"; fake_root.mkdir(parents=True)
            public = fake_root / "public" / "generated" / "job"
            result = brand_director.resolve_brand(fake_root, public)
        self.assertFalse(result["ready"])
        self.assertIsNone(result["asset"])
        self.assertEqual(result["config"]["logoAssetId"], "kbm-brand-logo")
        self.assertTrue(result["config"]["requireLogo"])

    def test_timeline_preserves_energy_and_editorial_metadata(self) -> None:
        board = {"durationSeconds": 5.0, "energyCurve": [0.9], "policy": {"maxUnchangedSeconds": 2.5}, "scenes": [{"id": "x", "fromSeconds": 0.0, "toSeconds": 2.0, "kind": "video", "transition": "flash", "motion": "punch", "intensity": 0.9, "beatRole": "hook", "title": "هوک"}]}
        compiled = timeline_compiler.compile_timeline(board, {"rights": [], "assets": []}, fps=30)
        scene = compiled["scenes"][0]
        self.assertEqual(scene["transitionIn"], "flash")
        self.assertEqual(scene["motion"], "punch")
        self.assertEqual(scene["beatRole"], "hook")
        self.assertEqual(scene["intensity"], 0.9)
        self.assertEqual(compiled["policy"]["maxUnchangedSeconds"], 2.5)


class SourceContractTests(unittest.TestCase):
    def test_package13_orchestrator_and_renderer_contracts_exist(self) -> None:
        orchestrator = (PIPELINE / "orchestrator_v4.py").read_text(encoding="utf-8")
        renderer = (ROOT / "src" / "ProEditDeskReel.tsx").read_text(encoding="utf-8")
        brand = (ROOT / "src" / "Package13BrandLayer.tsx").read_text(encoding="utf-8")
        for authority in ("build_ad_storyboard", "scout(storyboard", "route_assets", "resolve_brand", "master_for_reels", "package13-rights-manifest.json", '"captionPolicy": "single-lane"'):
            self.assertIn(authority, orchestrator)
        self.assertIn("Package13BrandLayer", renderer)
        self.assertIn("OffthreadVideo", renderer)
        self.assertIn("logoReveal", brand)
        self.assertIn("watermark", brand)
        self.assertNotIn("fetch('http://", orchestrator)

    def test_package_metadata_keeps_v13_and_adds_v131(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], "0.13.1")
        self.assertEqual(package["scripts"]["full-cinematic-editor"], "python pipeline/orchestrator_v4.py")
        self.assertEqual(package["scripts"]["avalai-cinematic-editor"], "python pipeline/orchestrator_v41.py")


if __name__ == "__main__":
    unittest.main()
