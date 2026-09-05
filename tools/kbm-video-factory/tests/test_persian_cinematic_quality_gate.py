from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

import cinematic_ad_protocol  # noqa: E402
import perceptual_quality_gate as quality  # noqa: E402
import persian_asr_quality as asr_quality  # noqa: E402


def passing_evidence() -> dict:
    return {
        "audio": {
            "codec": "aac",
            "sampleRate": 48000,
            "channels": 2,
            "bitRate": 192000,
            "measuredLufs": -14.67,
            "measuredTruePeakDb": -1.02,
            "measuredLra": 2.4,
        },
        "voice": {
            "finalMixNarrationDetected": True,
            "asrVerified": True,
            "asrProvenanceVerified": True,
            "language": "fa-IR",
            "asrTranscript": "ماشینت هنوز فروش نرفته با کاریاب ماشین مستقیم دیده شو",
            "expectedScript": "ماشینت هنوز فروش نرفته با کاریاب ماشین مستقیم دیده شو",
            "scriptTranscriptSimilarity": 1.0,
            "persianCharacterRatio": 0.95,
            "pronunciationReviewPassed": True,
            "pronunciationReviewAuthority": "KBM-PERSIAN-ASR-PRONUNCIATION-AUTHORITY-01",
            "pronunciationReviewMethod": "deterministic-final-mix-asr-lexicon-v1",
        },
        "captions": {
            "present": True,
            "wordTiming": True,
            "asrBackedWordTiming": True,
            "coverageRatio": 0.93,
            "transcriptAgreement": 0.94,
            "keywordHighlightColor": "#F4B400",
            "maxWordsPerCue": 5,
            "maxCharsPerCue": 38,
        },
        "visual": {
            "semanticBeatCount": 9,
            "maxUnchangedSeconds": 2.1,
            "realIndustrialFootage": True,
            "thirdPartyWatermarkDetected": False,
        },
        "brand": {
            "logoPresent": True,
            "ctaPresent": True,
            "sitePresent": True,
            "endCardPresent": True,
        },
    }


class PersianCinematicQualityGateTests(unittest.TestCase):
    def test_complete_reference_quality_evidence_passes(self) -> None:
        result = quality.evaluate(passing_evidence())
        self.assertTrue(result["gatePass"])
        self.assertEqual(result["blockers"], [])

    def test_missing_asr_and_final_mix_voice_fail_closed(self) -> None:
        evidence = passing_evidence()
        evidence["voice"].update({
            "finalMixNarrationDetected": False,
            "asrVerified": False,
            "asrTranscript": "",
            "scriptTranscriptSimilarity": 0.0,
        })
        result = quality.evaluate(evidence)
        self.assertFalse(result["gatePass"])
        self.assertIn("PERSIAN_QG_NARRATION_NOT_PROVEN_IN_FINAL_MIX", result["blockers"])
        self.assertIn("PERSIAN_QG_ASR_EVIDENCE_MISSING", result["blockers"])

    def test_unsynchronised_subtitles_fail_closed(self) -> None:
        evidence = passing_evidence()
        evidence["captions"].update({"wordTiming": False, "coverageRatio": 0.4, "transcriptAgreement": 0.2})
        result = quality.evaluate(evidence)
        self.assertIn("PERSIAN_QG_CAPTION_WORD_TIMING_MISSING", result["blockers"])
        self.assertIn("PERSIAN_QG_CAPTION_COVERAGE_LOW", result["blockers"])
        self.assertIn("PERSIAN_QG_CAPTION_TRANSCRIPT_MISMATCH", result["blockers"])

    def test_stale_asr_and_synthetic_caption_authority_fail_closed(self) -> None:
        evidence = passing_evidence()
        evidence["voice"]["asrProvenanceVerified"] = False
        evidence["captions"]["asrBackedWordTiming"] = False
        result = quality.evaluate(evidence)
        self.assertIn("PERSIAN_QG_FINAL_ASR_PROVENANCE_INVALID", result["blockers"])
        self.assertIn("PERSIAN_QG_CAPTION_NOT_ASR_BACKED", result["blockers"])

    def test_reference_audio_profile_matches_user_sample(self) -> None:
        profile = quality._profile()
        audio = profile["gates"]["audio"]
        self.assertEqual(audio["sampleRate"], 48000)
        self.assertEqual(audio["channels"], 2)
        self.assertEqual(audio["referenceMeasuredLufs"], -14.67)
        self.assertEqual(audio["referenceMeasuredTruePeakDb"], -1.02)

    def test_camp_release_gate_has_perceptual_authority(self) -> None:
        source = (PIPELINE / "cinematic_ad_protocol.py").read_text(encoding="utf-8")
        orchestrator = (PIPELINE / "orchestrator_camp.py").read_text(encoding="utf-8")
        self.assertIn('"perceptual": evaluate_perceptual_quality', source)
        self.assertIn("camp-perceptual-quality.json", orchestrator)
        self.assertIn("build_perceptual_evidence", orchestrator)

    def test_pronunciation_review_requires_brand_and_script_terms(self) -> None:
        transcript = {
            "language": "fa",
            "text": "با کاریاب ماشین آگهی ماشین آلات خودت را ثبت کن",
            "segments": [{
                "text": "با کاریاب ماشین آگهی ماشین آلات خودت را ثبت کن",
                "words": [{"word": "کاریاب", "start": 0.0, "end": 0.3}],
            }],
        }
        review = asr_quality.build_pronunciation_review(
            "با کاریاب ماشین آگهی ماشین‌آلات خودت را ثبت کن",
            transcript,
        )
        self.assertTrue(review["pass"])
        self.assertEqual(review["reviewMethod"], "deterministic-final-mix-asr-lexicon-v1")

    def test_pronunciation_review_fails_when_brand_is_not_recognized(self) -> None:
        transcript = {"language": "fa", "text": "آگهی خودت را ثبت کن", "segments": []}
        review = asr_quality.build_pronunciation_review(
            "در کاریاب ماشین آگهی ثبت کن",
            transcript,
        )
        self.assertFalse(review["pass"])
        self.assertTrue(any("کاریاب ماشین" in blocker for blocker in review["blockers"]))

    def test_transcribe_media_binds_evidence_to_exact_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "voice.mp3"
            source.write_bytes(b"deterministic-voice-fixture")
            output_dir = root / "whisperx"
            output_dir.mkdir()
            (output_dir / "voice.json").write_text(
                '{"language":"fa","text":"کاریاب ماشین",'
                '"segments":[{"text":"کاریاب ماشین","words":['
                '{"word":"کاریاب","start":0.0,"end":0.4},'
                '{"word":"ماشین","start":0.4,"end":0.8}]}]}',
                encoding="utf-8",
            )
            destination = root / "authority.json"
            completed = subprocess.CompletedProcess(["whisperx"], 0)
            with mock.patch.object(asr_quality, "build_command", return_value=["whisperx"]):
                result = asr_quality.transcribe_media(
                    source,
                    destination,
                    output_dir=output_dir,
                    runner=mock.Mock(return_value=completed),
                )
            self.assertTrue(destination.is_file())
            self.assertEqual(result["_kbmEvidence"]["sourceSha256"], asr_quality._sha256(source))
            self.assertTrue(result["_kbmEvidence"]["wordTiming"])

    def test_camp_runs_voice_and_final_mix_asr_without_publish(self) -> None:
        camp = (PIPELINE / "orchestrator_camp.py").read_text(encoding="utf-8")
        v2 = (PIPELINE / "orchestrator_v2.py").read_text(encoding="utf-8")
        self.assertIn('base_env["KBM_PERSIAN_QUALITY_GATE"] = "1"', camp)
        self.assertIn('work / "camp-final-asr.json"', camp)
        self.assertIn('work / "camp-pronunciation-review.json"', camp)
        self.assertIn("perceptual=perceptual", camp)
        self.assertIn('workdir / "package13-1-voice-asr.json"', v2)
        self.assertNotIn("media_" + "publish", camp)


    def test_strict_persian_selection_requires_a_pronouncing_tts_take(self) -> None:
        voice = (PIPELINE / "avalai_voice_director.py").read_text(encoding="utf-8")
        lanes = (PIPELINE / "audio_lanes.py").read_text(encoding="utf-8")
        self.assertIn("CUPAI_TTS_NO_PRONOUNCING_TAKE", voice)
        self.assertIn("pronunciation_eligible", voice)
        self.assertIn("pronunciation_valid or pronunciation_eligible", voice)
        self.assertIn('"48000"', lanes)
        self.assertIn('"2"', lanes)

    def test_tts_script_is_not_rewritten_after_voice_generation(self) -> None:
        v4 = (PIPELINE / "orchestrator_v4.py").read_text(encoding="utf-8")
        mastering = (PIPELINE / "audio_mastering.py").read_text(encoding="utf-8")
        self.assertIn('explicit_voiceover_script = _arg_value(base_args, "--voiceover-script", "").strip()', v4)
        self.assertIn('custom_brief["voiceoverScript"] = explicit_voiceover_script', v4)
        self.assertIn('"-ar", "48000"', mastering)
        self.assertIn('"-ac", "2"', mastering)

    def test_no_publish_e2e_pins_whisperx_and_captures_provenance(self) -> None:
        root = PIPELINE.parent
        workflow = (root.parent.parent / ".github" / "workflows" / "kbm-persian-cinematic-quality-e2e.yml").read_text(encoding="utf-8")
        source_builder = (root / "scripts" / "prepare_persian_quality_source.py").read_text(encoding="utf-8")
        self.assertIn("whisperx==3.8.6", workflow)
        self.assertIn("KBM_EXTERNAL_PUBLISH: '0'", workflow)
        self.assertIn("source-provenance.json", workflow)
        self.assertIn("KBM-PERSIAN-CINEMATIC-QUALITY-SOURCE-AUTHORITY-01", source_builder)
        self.assertIn("Pexels License", source_builder)
        self.assertIn("Pixabay Content License", source_builder)
        self.assertNotIn("media_" + "publish", workflow)


if __name__ == "__main__":
    unittest.main()
