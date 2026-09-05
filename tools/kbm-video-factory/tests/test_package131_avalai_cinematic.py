from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
GITHUB_ACTIONS = ROOT / "github_actions"
for path in (str(PIPELINE), str(ROOT), str(GITHUB_ACTIONS)):
    if path not in sys.path:
        sys.path.insert(0, path)

avalai_client = importlib.import_module("avalai_creative_client")
intelligence = importlib.import_module("avalai_creative_intelligence")
voice_director = importlib.import_module("avalai_voice_director")
asset_router = importlib.import_module("asset_router")
broll_scout = importlib.import_module("broll_scout")
rights_gate = importlib.import_module("rights_gate")
providers = importlib.import_module("providers")
runner131 = importlib.import_module("release_runner_131")


class AvalAIClientContractTests(unittest.TestCase):
    def test_client_is_off_without_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(avalai_client.configured())
            self.assertFalse(intelligence.enabled())

    def test_direct_api_key_never_appears_in_runner_cli(self) -> None:
        job = {
            "pipelineMode": "v41",
            "preset": "excavator-rental-3-checks",
            "template": "KBM-V03-MACHINE-REVIEW",
            "voice": "alloy",
            "maxSeconds": 30,
            "jobId": "123e4567-e89b-12d3-a456-426614174000",
        }
        with patch.dict(os.environ, {"CUPAI_API_KEY": "super-secret", "KBM_PACKAGE131_MODE": "maximum"}, clear=False):
            command = runner131.build_command(ROOT, job, Path("/tmp/in.mp4"), Path("/tmp/out.mp4"))
        joined = " ".join(command)
        self.assertIn("orchestrator_v41.py", joined)
        self.assertIn("--package131-mode maximum", joined)
        self.assertNotIn("CUPAI_API_KEY", joined)
        self.assertNotIn("super-secret", joined)

    def test_runner_redacts_direct_avalai_key(self) -> None:
        with patch.dict(os.environ, {"CUPAI_API_KEY": "secret-value"}, clear=False):
            self.assertNotIn("secret-value", runner131.redact("failure secret-value"))


class AvalAIVoiceDirectorTests(unittest.TestCase):
    def test_maximum_mode_generates_three_takes_and_selects_duration_fit(self) -> None:
        def fake_speech(_text: str, destination: Path, **kwargs):
            destination.write_bytes(b"0" * 2048)
            return {"provider": "cupai", "model": "gpt-4o-mini-tts", "voice": kwargs.get("voice"), "path": str(destination), "bytes": 2048}

        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(voice_director, "synthesize_speech", side_effect=fake_speech), \
             patch.object(voice_director, "_duration", side_effect=[12.0, 15.0, 18.0]):
            manifest = voice_director.direct_voice(
                "قبل از اجاره بیل مکانیکی این سه نکته را بررسی کن.",
                Path(temporary),
                voice="alloy",
                max_seconds=20,
                maximum=True,
            )
        self.assertEqual(manifest["takeCount"], 3)
        self.assertEqual(manifest["selectedTake"], "industrial")
        self.assertEqual(len(manifest["takes"]), 3)


class GeneratedAssetRightsTests(unittest.TestCase):
    def test_avalai_generated_asset_is_approved_as_kbm_owned(self) -> None:
        candidate = {
            "provider": "cupai-generated",
            "license": "KBM-OWNED",
            "downloadUrl": "https://api.cupai.ir/v1/videos/video_demo/content",
            "sourceUrl": "https://api.cupai.ir/",
        }
        self.assertTrue(rights_gate.evaluate(candidate)["approved"])

    def test_router_copies_only_generated_asset_inside_authority_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            generated = temp / "generated"
            generated.mkdir()
            local = generated / "shot.mp4"
            local.write_bytes(b"0" * 4096)
            scout = {
                "requests": [{"id": "media-a", "sceneId": "a", "mediaType": "video"}],
                "candidates": [{
                    "requestId": "media-a", "sceneId": "a", "provider": "cupai-generated",
                    "providerId": "video_demo", "mediaType": "video",
                    "downloadUrl": "https://api.cupai.ir/v1/videos/video_demo/content",
                    "sourceUrl": "https://api.cupai.ir/", "creator": "KBM via CupAI",
                    "license": "KBM-OWNED", "localPath": str(local), "rightsDecision": {"approved": True},
                }],
            }
            with patch.dict(os.environ, {"KBM_PACKAGE131_MEDIA_DIR": str(generated)}, clear=False):
                result = asset_router.route_assets(scout, temp / "public", materialize=True)
            self.assertEqual(len(result["assets"]), 1)
            self.assertEqual(result["assets"][0]["kind"], "video")
            self.assertTrue((temp / "public" / result["assets"][0]["src"]).is_file())
            self.assertTrue(result["rights"][0]["materialized"])

    def test_broll_scout_can_use_generated_provider_without_real_network(self) -> None:
        board = {"scenes": [{"id": "s1", "kind": "broll", "copy": "جک هیدرولیک", "searchQuery": "excavator hydraulic cylinder"}]}
        fake = [{
            "provider": "cupai-generated", "providerId": "video_demo", "mediaType": "video",
            "width": 720, "height": 1280, "duration": 4,
            "downloadUrl": "https://api.cupai.ir/v1/videos/video_demo/content",
            "sourceUrl": "https://api.cupai.ir/", "title": "excavator hydraulic cylinder", "creator": "KBM via CupAI", "license": "KBM-OWNED",
            "localPath": "/tmp/fake.mp4",
        }]
        fake_provider = SimpleNamespace(
            configured=lambda: True,
            search_videos=lambda _query, per_page=1: fake,
            search_images=lambda _query, per_page=1: [],
        )
        env = {"KBM_PACKAGE131_CUPAI_MEDIA": "1", "KBM_PACKAGE131_CUPAI_GENERATE_ALWAYS": "1", "CUPAI_API_KEY": "x", "KBM_PACKAGE131_MEDIA_DIR": "/tmp"}
        with patch.dict(os.environ, env, clear=True), patch.object(providers, "cupai_generated_provider", fake_provider):
            result = broll_scout.scout(board, enabled=True)
        self.assertTrue(any(x.get("provider") == "cupai-generated" for x in result["candidates"]))


class CreativeIntelligenceTests(unittest.TestCase):
    def test_bounded_repairs_raise_caption_and_brand_authority(self) -> None:
        props = {"captionProfile": {"bottom": 250, "outlinePx": 2}, "brand": {"requireLogo": False}, "editorial": {}}
        critique = {"captionReadability": 5, "brandVisibility": 4}
        repaired = intelligence.apply_bounded_repairs(props, critique)
        self.assertGreaterEqual(repaired["captionProfile"]["bottom"], 300)
        self.assertGreaterEqual(repaired["captionProfile"]["outlinePx"], 4)
        self.assertTrue(repaired["brand"]["requireLogo"])
        self.assertFalse(repaired["brand"]["persistentBug"])
        self.assertEqual(repaired["editorial"]["repairPass"], 1)

    def test_storyboard_refiner_preserves_timing_authority(self) -> None:
        board = {"scenes": [{"id": "a", "kind": "video", "copy": "قدیم", "searchQuery": "old", "transition": "hard", "from": 0, "to": 30}]}
        response = {"scenes": [{"id": "a", "kind": "broll", "copy": "جدید", "searchQuery": "hydraulic close up", "transition": "push"}], "critique": "ok"}
        with patch.object(intelligence, "chat_json", return_value=response):
            refined = intelligence.refine_storyboard(board, [], {})
        scene = refined["scenes"][0]
        self.assertEqual(scene["from"], 0)
        self.assertEqual(scene["to"], 30)
        self.assertEqual(scene["kind"], "broll")
        self.assertEqual(scene["searchQuery"], "hydraulic close up")


class FullStackSourceContractTests(unittest.TestCase):
    def test_v41_authorities_and_workflow_are_wired_but_not_activated(self) -> None:
        orchestrator = (PIPELINE / "orchestrator_v41.py").read_text(encoding="utf-8")
        client = (PIPELINE / "avalai_creative_client.py").read_text(encoding="utf-8")
        provider_source = (PIPELINE / "providers.py").read_text(encoding="utf-8")
        voice_source = (PIPELINE / "avalai_voice_director.py").read_text(encoding="utf-8")
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "kbm-video-render-free.yml").read_text(encoding="utf-8")
        shim = (GITHUB_ACTIONS / "release_runner_131.py").read_text(encoding="utf-8")
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("direct_campaign", orchestrator)
        self.assertIn("direct_voice", orchestrator)
        self.assertIn("critique_final", orchestrator)
        self.assertIn("bounded-auto-reedit", orchestrator)
        self.assertIn("CUPAI_VIDEO_GENERATION_DISABLED_UNVERIFIED_CONTRACT", client)
        self.assertIn('"/images/generations"', client)
        self.assertIn('"/audio/speech"', client)
        self.assertIn('"/chat/completions"', client)
        self.assertIn("CupAIGeneratedProvider", provider_source)
        self.assertIn("TAKES = [", voice_source)
        self.assertIn("release_runner_131.py render", workflow)
        self.assertIn("secrets.CUPAI_API_KEY", workflow)
        self.assertIn("KBM_CUPAI_TTS_MODEL", workflow)
        self.assertIn("vars.KBM_PIPELINE_MODE || 'v4'", workflow)
        self.assertIn('"v41"', shim)
        self.assertEqual(package["version"], "0.13.1")
        self.assertEqual(package["scripts"]["avalai-cinematic-editor"], "python pipeline/orchestrator_v41.py")


if __name__ == "__main__":
    unittest.main()
