from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
for item in (str(PIPELINE), str(ROOT)):
    if item not in sys.path:
        sys.path.insert(0, item)

client = importlib.import_module("avalai_creative_client")
intelligence = importlib.import_module("avalai_creative_intelligence")
voice_director = importlib.import_module("avalai_voice_director")
orchestrator = importlib.import_module("orchestrator_v41")


class EditorialRepairTests(unittest.TestCase):
    def test_repairs_materially_strengthen_brand_caption_and_cta(self) -> None:
        props = {
            "cta": "کاریاب ماشین؛ آگاهانه انتخاب کن.",
            "captionProfile": {"bottom": 270, "outlinePx": 3, "pill": False},
            "brand": {"requireLogo": True},
        }
        critique = {"captionReadability": 7, "brandVisibility": 5, "ctaStrength": 5}
        repaired = intelligence.apply_bounded_repairs(props, critique)
        self.assertTrue(repaired["captionProfile"]["pill"])
        self.assertGreaterEqual(repaired["captionProfile"]["outlinePx"], 5)
        self.assertEqual(repaired["brand"]["prominence"], "strong")
        self.assertTrue(repaired["brand"]["endCardRequired"])
        self.assertIn("KARYABMASHIN.IR", repaired["cta"])


class VoiceDurationTests(unittest.TestCase):
    def test_long_script_is_compacted_before_tts_and_duration_fit_is_reported(self) -> None:
        long_text = " ".join(["بررسی" for _ in range(70)]) + " کاریاب ماشین را ببین."

        def fake_chat(_prompt: str, **_kwargs):
            return {"voiceoverScript": "وضعیت واقعی دستگاه را بررسی کن و گزینه‌ها را در کاریاب ماشین ببین."}

        def fake_speech(_text: str, destination: Path, **kwargs):
            destination.write_bytes(b"0" * 2048)
            return {"model": "text-to-speech-multilingual-v2", "voice": kwargs.get("voice"), "path": str(destination), "bytes": 2048, "contentType": "audio/mpeg"}

        with tempfile.TemporaryDirectory() as temporary, patch.object(voice_director, "chat_json", side_effect=fake_chat), patch.object(voice_director, "synthesize_speech", side_effect=fake_speech), patch.object(voice_director, "_duration", side_effect=[10.2, 10.6, 10.9]):
            manifest = voice_director.direct_voice(long_text, Path(temporary), voice="alloy", max_seconds=15, maximum=True)
        self.assertTrue(manifest["scriptFit"]["compacted"])
        self.assertTrue(manifest["durationFit"])
        self.assertLessEqual(manifest["selectedDuration"], manifest["durationCeilingSeconds"])
        self.assertLess(manifest["scriptFit"]["fittedWords"], manifest["scriptFit"]["originalWords"])

    def test_campaign_failure_has_deterministic_voice_and_actionable_cta_fallback(self) -> None:
        campaign = orchestrator._fallback_campaign("ویدیوی واقعی دستگاه برای اجاره و معامله")
        self.assertTrue(campaign["fallback"])
        self.assertIn("اجاره", campaign["voiceoverScript"])
        self.assertIn("معامله", campaign["voiceoverScript"])
        self.assertIn("KARYABMASHIN.IR", campaign["cta"])

    def test_existing_gateway_audio_is_promoted_only_with_measured_duration_fit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            audio = work / "voiceover.mp3"
            audio.write_bytes(b"0" * 2048)
            (work / "voice-report.json").write_text(
                json.dumps({
                    "engine": "avalai-gateway",
                    "provider": "AvalAI",
                    "model": "gateway-managed",
                    "voice": "alloy",
                    "script": "وضعیت واقعی دستگاه را ببین و گزینه‌ها را در کاریاب ماشین مقایسه کن.",
                    "output": str(audio),
                    "contentType": "audio/mpeg",
                    "sizeBytes": 2048,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            prior = {"engine": "avalai-directed-tts", "complete": False, "durationFit": False, "failures": [{"code": "AVALAI_INSUFFICIENT_QUOTA"}]}
            with patch.object(orchestrator, "probe", return_value={}), patch.object(orchestrator, "duration_seconds", return_value=10.4):
                manifest, state = orchestrator._promote_gateway_voice(work, prior, 15)
        self.assertEqual(manifest["engine"], "avalai-gateway-fallback")
        self.assertTrue(manifest["complete"])
        self.assertTrue(manifest["durationFit"])
        self.assertEqual(manifest["fallbackFrom"]["failures"][0]["code"], "AVALAI_INSUFFICIENT_QUOTA")
        self.assertIsNotNone(state)
        self.assertEqual(state["state"], "PASS")


class CriticResilienceTests(unittest.TestCase):
    def test_provider_quota_failure_returns_structured_incomplete_evidence(self) -> None:
        audio = {"technicalAudioScore": 10.0, "measuredLufs": -15.2}
        with tempfile.TemporaryDirectory() as temporary, patch.object(intelligence, "extract_contact_sheet_frames", return_value=[]), patch.object(intelligence, "analyze_audio", return_value=audio), patch.object(intelligence, "chat_json", side_effect=RuntimeError("insufficient_quota")) as mocked_chat:
            result = intelligence.critique_final(Path("unused.mp4"), Path(temporary))
        self.assertFalse(result["criticComplete"])
        self.assertFalse(result["publishReady"])
        self.assertEqual(result["overall"], 0.0)
        self.assertEqual(result["frameSampling"], "even-plus-end")
        self.assertEqual(result["criticRequestAttempts"], 3)
        self.assertEqual(mocked_chat.call_args.kwargs["attempts"], 3)
        self.assertIn("insufficient_quota", result["criticError"])
        self.assertEqual(result["authority"], "PEP-V41-BRAND-ASSET-PRESERVE-CRITIC-GATE-RESILIENCE-AUTHORITY")

    def test_chat_json_forwards_bounded_attempt_count(self) -> None:
        response = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        with patch.object(client, "_json", return_value=response) as mocked_json:
            result = client.chat_json("critic", attempts=3)
        self.assertTrue(result["ok"])
        self.assertEqual(mocked_json.call_args.kwargs["attempts"], 3)

    def test_transient_504_is_classified_retryable(self) -> None:
        diagnostic = client.classify_cupai_error("CupAI HTTP 504: Gateway Time-out")
        self.assertEqual(diagnostic["code"], "CUPAI_UPSTREAM_RETRYABLE")
        self.assertTrue(diagnostic["retryable"])

    def test_incomplete_critic_is_blocked_not_passed(self) -> None:
        self.assertEqual(orchestrator._critic_state({"criticComplete": False}), "BLOCKED")
        self.assertEqual(orchestrator._critic_state({"criticComplete": True}), "PASS")


class SourceAuthorityTests(unittest.TestCase):
    def test_orchestrator_recritiques_after_bounded_reedit(self) -> None:
        source = (PIPELINE / "orchestrator_v41.py").read_text(encoding="utf-8")
        self.assertIn("PEP-V41-EDITORIAL-CTA-BRAND-TTS-DURATION-AUTHORITY", source)
        self.assertIn("package13-1-cupai-critic-pass0.json", source)
        self.assertGreaterEqual(source.count("critique_final(output_path, work)"), 2)
        self.assertIn('critic.get("publishReady") is not True', source)
        self.assertIn("needs_repair = critic_complete and", source)
        self.assertIn('"state": _critic_state(critic)', source)

    def test_voice_director_is_not_coupled_to_multimodal_campaign_success(self) -> None:
        source = (PIPELINE / "orchestrator_v41.py").read_text(encoding="utf-8")
        self.assertNotIn("if enabled() and campaign:", source)
        self.assertIn("campaign: dict[str, Any] = _fallback_campaign(seed)", source)
        self.assertIn("_promote_gateway_voice(work, voice_manifest, max_seconds)", source)
        self.assertIn('"engine": "avalai-gateway-fallback"', source)

    def test_brand_layer_consumes_repair_flags_and_renders_cta(self) -> None:
        source = (ROOT / "src" / "Package13BrandLayer.tsx").read_text(encoding="utf-8")
        self.assertIn("endCardRequired", source)
        self.assertIn("prominence==='strong'", source)
        self.assertIn("props.cta", source)
        self.assertIn("forcedEndStart", source)

    def test_polished_renderer_mounts_authoritative_brand_layer(self) -> None:
        source = (ROOT / "src" / "CinematicPolishedReel.tsx").read_text(encoding="utf-8")
        self.assertIn("import {Package13BrandLayer} from './Package13BrandLayer';", source)
        self.assertIn("<Package13BrandLayer {...props} />", source)
        self.assertNotIn("showBrandBug", source)
        self.assertGreater(
            source.index("<Package13BrandLayer {...props} />"),
            source.index("{transitionOverlay(activeScene, frame, fps, accent)}"),
        )

    def test_brand_source_survives_asset_recompile(self) -> None:
        director = (PIPELINE / "brand_director.py").read_text(encoding="utf-8")
        layer = (ROOT / "src" / "Package13BrandLayer.tsx").read_text(encoding="utf-8")
        types = (ROOT / "src" / "types.ts").read_text(encoding="utf-8")
        self.assertGreaterEqual(director.count('"logoSrc": src'), 2)
        self.assertIn("logo?.src??brand?.logoSrc", layer)
        self.assertIn("logoSrc?:string|null", types)

    def test_critic_sampler_is_even_and_forces_near_end_frame(self) -> None:
        source = (PIPELINE / "avalai_creative_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("def _video_duration", source)
        self.assertIn("safe_end", source)
        self.assertIn("sample_count - 1", source)
        self.assertIn('"frameSampling": "even-plus-end"', source)
        self.assertIn("attempts=3", source)
        self.assertIn('"criticRequestAttempts": 3', source)

    def test_smoke_gate_is_structured_when_critic_evidence_is_missing(self) -> None:
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "kbm-pep-v41-real-footage-execution.yml").read_text(encoding="utf-8")
        self.assertIn("PEP_RENDER_CANDIDATE: '13.1.2-rc.4'", workflow)
        self.assertIn("def load_json(name, default):", workflow)
        self.assertIn("CRITIC_EVIDENCE_MISSING", workflow)
        self.assertIn("CRITIC_RETRY_POLICY_MISMATCH", workflow)
        self.assertIn("CRITIC_INCOMPLETE", workflow)
        self.assertIn("VOICE_NOT_COMPLETE", workflow)
        self.assertIn("VOICE_DURATION_FIT_FAILED", workflow)
        self.assertIn("package13-1-cupai-critic-pass0.json", workflow)
        self.assertIn("criticRequestAttempts", workflow)
        self.assertIn("criticFrameSampling", workflow)

    def test_release_runner_enforces_voice_duration_and_complete_critic(self) -> None:
        source = (ROOT / "github_actions" / "release_runner_131.py").read_text(encoding="utf-8")
        self.assertIn('voice.get("durationFit") is not True', source)
        self.assertIn("voice duration gate failed", source)
        self.assertIn('critic.get("criticComplete") is not True', source)
        self.assertIn("critic evidence is incomplete", source)


if __name__ == "__main__":
    unittest.main()
