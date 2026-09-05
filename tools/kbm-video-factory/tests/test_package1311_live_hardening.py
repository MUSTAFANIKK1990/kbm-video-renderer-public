from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
for path in (str(PIPELINE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

audio_critic = importlib.import_module("audio_critic")
avalai_client = importlib.import_module("avalai_creative_client")
intelligence = importlib.import_module("avalai_creative_intelligence")
voice_director = importlib.import_module("avalai_voice_director")
broll_scout = importlib.import_module("broll_scout")
providers = importlib.import_module("providers")
provider_preflight = importlib.import_module("provider_connection_preflight")


class AudioEvidenceTests(unittest.TestCase):
    def test_real_audio_evidence_drives_audio_energy(self) -> None:
        samples = array("f")
        for index in range(16000 * 2):
            amplitude = 0.05 if index < 16000 else 0.25
            samples.append(amplitude if index % 2 == 0 else -amplitude)
        loudness = {"measuredLufs": -14.2, "measuredTruePeakDb": -1.2, "measuredLra": 4.0}
        with patch.object(audio_critic, "_extract_pcm", return_value=samples), patch.object(audio_critic, "_loudnorm", return_value=loudness):
            evidence = audio_critic.analyze_audio(Path("demo.mp4"))
        self.assertTrue(evidence["audioPresent"])
        self.assertGreater(evidence["energyVariationDb"], 5)
        self.assertGreaterEqual(evidence["technicalAudioScore"], 6)

    def test_final_critic_overrides_audio_score_with_measured_evidence(self) -> None:
        response = {
            "hook": 8, "pacing": 8, "brollRelevance": 8, "shotVariety": 8,
            "brandVisibility": 8, "captionReadability": 8, "audioEnergy": 10,
            "ctaStrength": 8, "overall": 10, "publishReady": 1, "actions": [],
        }
        evidence = {"audioPresent": True, "technicalAudioScore": 4.0}
        with tempfile.TemporaryDirectory() as temporary, patch.object(intelligence, "extract_contact_sheet_frames", return_value=[]), patch.object(intelligence, "analyze_audio", return_value=evidence), patch.object(intelligence, "chat_json", return_value=response):
            result = intelligence.critique_final(Path("demo.mp4"), Path(temporary))
        self.assertEqual(result["audioEnergy"], 4.0)
        self.assertFalse(result["publishReady"])
        self.assertLess(result["overall"], 8.0)


class TTSHardeningTests(unittest.TestCase):
    def test_html_tts_response_is_rejected(self) -> None:
        headers = {"content-type": "text/html; charset=UTF-8"}
        with self.assertRaisesRegex(RuntimeError, "HTML_GATEWAY_RESPONSE"):
            avalai_client._validate_audio_response(b"<html>cdn-cgi" + b"x" * 2000, headers)

    def test_quota_error_is_classified(self) -> None:
        result = avalai_client.classify_cupai_error(RuntimeError('{"code":"insufficient_quota"}'))
        self.assertEqual(result["code"], "CUPAI_INSUFFICIENT_QUOTA")
        self.assertTrue(result["quotaBlocked"])

    def test_maximum_voice_keeps_successful_takes_and_records_failures(self) -> None:
        calls = {"count": 0}

        def fake_speech(_text: str, destination: Path, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("CupAI HTTP 429: rate limit")
            destination.write_bytes(b"0" * 2048)
            return {"provider": "cupai", "model": "gpt-4o-mini-tts", "voice": kwargs.get("voice"), "path": str(destination), "bytes": 2048, "contentType": "audio/mpeg"}

        with tempfile.TemporaryDirectory() as temporary, patch.object(voice_director, "synthesize_speech", side_effect=fake_speech), patch.object(voice_director, "_duration", side_effect=[8.0, 9.0]):
            manifest = voice_director.direct_voice("نمونه نریشن", Path(temporary), voice="alloy", max_seconds=12, maximum=True)
        self.assertEqual(manifest["takeCount"], 2)
        self.assertTrue(manifest["complete"])
        self.assertEqual(len(manifest["failures"]), 1)
        self.assertEqual(manifest["failures"][0]["code"], "CUPAI_RATE_LIMITED")


class MediaProviderHealthTests(unittest.TestCase):
    def test_avalai_quota_failure_is_visible_while_stock_can_still_pass(self) -> None:
        board = {"scenes": [{"id": "s1", "kind": "broll", "copy": "هیدرولیک", "searchQuery": "excavator hydraulic"}]}
        stock = [{
            "provider": "pexels", "providerId": "1", "mediaType": "video", "width": 1080, "height": 1920,
            "duration": 4, "downloadUrl": "https://videos.pexels.com/demo.mp4", "sourceUrl": "https://pexels.com/video/1",
            "title": "excavator hydraulic", "creator": "demo", "license": "PEXELS",
        }]
        pexels = SimpleNamespace(configured=lambda: True, search_videos=lambda _q, per_page=8: stock, search_images=lambda _q, per_page=6: [])
        disabled = SimpleNamespace(configured=lambda: False)
        avalai = SimpleNamespace(configured=lambda: True, search_videos=lambda _q, per_page=8: (_ for _ in ()).throw(RuntimeError('{"code":"insufficient_quota"}')), search_images=lambda _q, per_page=6: [])
        env = {"KBM_PACKAGE131_CUPAI_MEDIA": "1", "KBM_PACKAGE131_CUPAI_GENERATE_ALWAYS": "1", "CUPAI_API_KEY": "x"}
        with patch.dict(os.environ, env, clear=True), patch.object(providers, "pexels_provider", pexels), patch.object(providers, "pixabay_provider", disabled), patch.object(providers, "iran_media_provider", disabled), patch.object(providers, "cupai_generated_provider", avalai):
            result = broll_scout.scout(board, enabled=True)
        self.assertIn("pexels", result["researchSummary"]["providersHealthy"])
        self.assertIn("cupai-generated", result["researchSummary"]["providersQuotaBlocked"])
        self.assertTrue(any(x.get("provider") == "pexels" for x in result["candidates"]))

    def test_provider_preflight_redacts_stock_keys_from_errors(self) -> None:
        env = {"PEXELS_API_KEY": "pexels-secret-value", "PIXABAY_API_KEY": "pixabay-secret-value"}
        with patch.dict(os.environ, env, clear=True):
            rendered = provider_preflight._redact("https://pixabay.com/api/videos/?key=pixabay-secret-value&q=excavator pexels-secret-value")
        self.assertNotIn("pixabay-secret-value", rendered)
        self.assertNotIn("pexels-secret-value", rendered)
        self.assertIn("key=***", rendered)


class SourceGateTests(unittest.TestCase):
    def test_v41_requires_official_brand_by_default(self) -> None:
        source = (PIPELINE / "orchestrator_v41.py").read_text(encoding="utf-8")
        self.assertIn("KBM_PACKAGE131_REQUIRE_BRAND", source)
        self.assertIn("brand-preflight", source)
        self.assertIn("brand-authority-gate", source)
        self.assertIn("13.1.1", source)

    def test_audio_critic_is_wired_into_final_critic(self) -> None:
        source = (PIPELINE / "avalai_creative_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("analyze_audio", source)
        self.assertIn("package13-1-audio-evidence.json", source)

    def test_render_workflow_has_first_party_brand_and_stock_secrets(self) -> None:
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "kbm-video-render-free.yml").read_text(encoding="utf-8")
        self.assertIn("secrets.PEXELS_API_KEY", workflow)
        self.assertIn("secrets.PIXABAY_API_KEY", workflow)
        self.assertIn("https://karyabmashin.ir/wp-content/plugins/kbm-visual-assets/assets/media/kbm-visual-system-v3/ipui25/brand/kbm-logo-transparent.png", workflow)

    def test_live_provider_smoke_is_secret_safe(self) -> None:
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "kbm-video-factory-package13-1-provider-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("secrets.PEXELS_API_KEY", workflow)
        self.assertIn("secrets.PIXABAY_API_KEY", workflow)
        self.assertIn("provider_connection_preflight.py", workflow)
        self.assertNotIn("echo $PEXELS_API_KEY", workflow)
        self.assertNotIn("echo $PIXABAY_API_KEY", workflow)

    def test_release_runner_contract_matches_package1311_and_forwards_creative_inputs(self) -> None:
        runner = (ROOT / "github_actions" / "release_runner_131.py").read_text(encoding="utf-8")
        self.assertIn("KBM-VIDEO-FACTORY-CUPAI-LIVE-CREATIVE-HARDENING-13.1.1", runner)
        self.assertIn('report.get("version") != "13.1.1"', runner)
        self.assertIn("CAMPAIGN_BRIEF_B64", runner)
        self.assertIn("--campaign-brief-b64", runner)
        self.assertIn("EDIT_STYLE", runner)
        self.assertIn("--edit-style", runner)
        self.assertIn("brand gate failed", runner)
        self.assertIn("critic gate failed", runner)

    def test_real_footage_smoke_uses_private_release_asset_and_no_synthetic_testsrc(self) -> None:
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "kbm-package13-1-1-real-footage-v41-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("release_runner_131.py render", workflow)
        self.assertIn("INPUT_ASSET_ID", workflow)
        self.assertIn("KBM_PIPELINE_MODE: v41", workflow)
        self.assertIn("KBM_PACKAGE131_REQUIRE_BRAND: '1'", workflow)
        self.assertIn("kbm-logo-transparent.png", workflow)
        self.assertNotIn("testsrc2", workflow)


if __name__ == "__main__":
    unittest.main()
