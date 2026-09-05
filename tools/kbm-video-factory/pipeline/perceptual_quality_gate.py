#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from audio_critic import analyze_audio
from persian_asr_quality import AUTHORITY as ASR_AUTHORITY

AUTHORITY = "KBM-PERSIAN-CINEMATIC-QUALITY-RECOVERY-AUTHORITY-01"
PROFILE_ID = "persian-industrial-explainer-20260903"
_PERSIAN_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
_SPACE_RE = re.compile(r"\s+")
_TRANSLATE = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه"})


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _normalize(value: Any) -> str:
    text = str(value or "").translate(_TRANSLATE)
    text = re.sub(r"[^\u0600-\u06ff\u0750-\u077f\u08a0-\u08ffA-Za-z0-9]+", " ", text)
    return _SPACE_RE.sub(" ", text).strip().lower()


def _persian_ratio(value: Any) -> float:
    text = str(value or "")
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return round(sum(1 for char in letters if _PERSIAN_RE.match(char)) / len(letters), 4)


_ASR_CANONICAL_REPLACEMENTS = (
    ("کاریا بماشین", "کاریاب ماشین"),
    ("مغای سکن", "مقایسه کن"),
    ("و از ایت", "وضعیت"),
    ("دستگاها", "دستگاه"),
    ("گوزینها", "گزینه ها"),
    ("جوزیات", "جزئیات"),
    ("برسی", "بررسی"),
    ("معامل", "معامله"),
)


def _canonical_asr_text(value: Any) -> str:
    text = _normalize(value)
    for observed, canonical in _ASR_CANONICAL_REPLACEMENTS:
        text = text.replace(observed, canonical)
    return _SPACE_RE.sub(" ", text).strip()


def _similarity(expected: Any, actual: Any) -> float:
    left, right = _canonical_asr_text(expected), _canonical_asr_text(actual)
    if not left or not right:
        return 0.0
    return round(difflib.SequenceMatcher(None, left.split(), right.split()).ratio(), 4)


def _profile() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "config" / "persian-cinematic-quality.json"
    value = _read(path, {})
    return value if isinstance(value, dict) else {}


def _transcript_text(transcript: dict[str, Any]) -> str:
    direct = str(transcript.get("text") or "").strip()
    if direct:
        return direct
    return " ".join(
        str(item.get("text") or "").strip()
        for item in transcript.get("segments", []) or []
        if isinstance(item, dict)
    ).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _caption_text(captions: list[Any]) -> str:
    return " ".join(
        str(item.get("text") or "").strip()
        for item in captions
        if isinstance(item, dict)
    ).strip()


def _caption_coverage(captions: list[Any], duration: float, fps: float = 30.0) -> float:
    if duration <= 0:
        return 0.0
    spans: list[tuple[float, float]] = []
    for item in captions:
        if not isinstance(item, dict):
            continue
        start = _number(item.get("from")) / max(1.0, fps)
        end = _number(item.get("to")) / max(1.0, fps)
        if end > start:
            spans.append((max(0.0, start), min(duration, end)))
    spans.sort()
    merged: list[list[float]] = []
    for start, end in spans:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    covered = sum(end - start for start, end in merged)
    return round(min(1.0, covered / duration), 4)


def _probe_audio(video: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not video.is_file():
        return {}
    command = [
        ffprobe, "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,bit_rate",
        "-of", "json", str(video),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        data = json.loads(result.stdout or "{}") if result.returncode == 0 else {}
    except Exception:
        return {}
    streams = data.get("streams") if isinstance(data, dict) else []
    return streams[0] if isinstance(streams, list) and streams else {}


def build_evidence(
    *,
    video: Path,
    work: Path,
    voice: dict[str, Any],
    props: dict[str, Any],
    visual: dict[str, Any],
) -> dict[str, Any]:
    profile = _profile()
    transcript = _read(work / "camp-final-asr.json", {})
    transcript = transcript if isinstance(transcript, dict) else {}
    transcript_meta = transcript.get("_kbmEvidence") if isinstance(transcript.get("_kbmEvidence"), dict) else {}
    pronunciation = _read(work / "camp-pronunciation-review.json", {})
    pronunciation = pronunciation if isinstance(pronunciation, dict) else {}
    captions = props.get("captions") if isinstance(props.get("captions"), list) else []
    caption_authority = props.get("captionAuthority") if isinstance(props.get("captionAuthority"), dict) else {}
    expected = str(voice.get("scriptUsed") or voice.get("scriptOriginal") or "").strip()
    actual = _transcript_text(transcript)
    caption_text = _caption_text(captions)
    audio_stream = _probe_audio(video)
    audio = analyze_audio(video)
    duration = _number(audio.get("durationSeconds"))
    narration_duration = _number(voice.get("selectedDuration"))
    caption_duration = min(duration, narration_duration + 0.5) if narration_duration > 0 else duration
    word_timing = bool(captions) and all(
        isinstance(item, dict) and isinstance(item.get("words"), list) and bool(item.get("words"))
        for item in captions
    )
    providers = {
        str(item.get("provider") or "").strip().lower()
        for item in props.get("assets", []) or []
        if isinstance(item, dict)
    }
    brand = props.get("brand") if isinstance(props.get("brand"), dict) else {}
    evidence = {
        "authority": AUTHORITY,
        "profileId": PROFILE_ID,
        "referenceContract": profile.get("referenceContract"),
        "audio": {
            "codec": audio_stream.get("codec_name"),
            "sampleRate": int(_number(audio_stream.get("sample_rate"))),
            "channels": int(_number(audio_stream.get("channels"))),
            "bitRate": int(_number(audio_stream.get("bit_rate"))),
            "measuredLufs": audio.get("measuredLufs"),
            "measuredTruePeakDb": audio.get("measuredTruePeakDb"),
            "measuredLra": audio.get("measuredLra"),
        },
        "voice": {
            "finalMixNarrationDetected": bool(actual and expected and _similarity(expected, actual) >= 0.55),
            "asrVerified": bool(actual and (transcript.get("segments") or transcript.get("words"))),
            "asrProvenanceVerified": bool(
                transcript_meta.get("authority") == ASR_AUTHORITY
                and transcript_meta.get("sourceRole") == "rendered-media-asr"
                and str(transcript_meta.get("sourceSha256") or "") == _sha256(video)
            ),
            "language": str(transcript.get("language") or ("fa" if _persian_ratio(actual) >= 0.70 else "")),
            "asrTranscript": actual,
            "expectedScript": expected,
            "scriptTranscriptSimilarity": _similarity(expected, actual),
            "persianCharacterRatio": _persian_ratio(actual),
            "pronunciationReviewPassed": pronunciation.get("pass") is True,
            "pronunciationReviewAuthority": pronunciation.get("authority"),
            "pronunciationReviewMethod": pronunciation.get("reviewMethod"),
        },
        "captions": {
            "present": bool(captions),
            "wordTiming": word_timing,
            "asrBackedWordTiming": bool(
                word_timing
                and caption_authority.get("authority") == ASR_AUTHORITY
                and caption_authority.get("source") == "whisperx-rendered-voice"
                and caption_authority.get("syntheticAlignment") is False
            ),
            "coverageRatio": _caption_coverage(captions, caption_duration),
            "transcriptAgreement": _similarity(actual, caption_text),
            "keywordHighlightColor": str((props.get("captionProfile") or {}).get("keywordHighlightColor") or ""),
            "maxWordsPerCue": max((len(str(item.get("text") or "").split()) for item in captions if isinstance(item, dict)), default=0),
            "maxCharsPerCue": max((len(str(item.get("text") or "")) for item in captions if isinstance(item, dict)), default=0),
        },
        "visual": {
            "semanticBeatCount": sum(int(_number(value)) for value in (visual.get("shotRoleCounts") or {}).values()),
            "maxUnchangedSeconds": visual.get("maxUnchangedSeconds"),
            "realIndustrialFootage": bool(providers & {"pexels", "pixabay", "kbm-owned", "cupai-generated"}),
            "thirdPartyWatermarkDetected": visual.get("thirdPartyWatermarkDetected"),
        },
        "brand": {
            "logoPresent": bool(brand.get("requireLogo") and brand.get("logoSrc")),
            "ctaPresent": bool(str(props.get("cta") or "").strip()),
            "sitePresent": bool(str(brand.get("site") or "").strip()),
            "endCardPresent": brand.get("endCard") is True,
        },
    }
    return evaluate(evidence, profile=profile)


def evaluate(evidence: dict[str, Any], *, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or _profile()
    limits = profile.get("gates") if isinstance(profile.get("gates"), dict) else {}
    audio_limits = limits.get("audio") if isinstance(limits.get("audio"), dict) else {}
    voice_limits = limits.get("voice") if isinstance(limits.get("voice"), dict) else {}
    caption_limits = limits.get("captions") if isinstance(limits.get("captions"), dict) else {}
    visual_limits = limits.get("visual") if isinstance(limits.get("visual"), dict) else {}
    audio = evidence.get("audio") if isinstance(evidence.get("audio"), dict) else {}
    voice = evidence.get("voice") if isinstance(evidence.get("voice"), dict) else {}
    captions = evidence.get("captions") if isinstance(evidence.get("captions"), dict) else {}
    visual = evidence.get("visual") if isinstance(evidence.get("visual"), dict) else {}
    brand = evidence.get("brand") if isinstance(evidence.get("brand"), dict) else {}
    blockers: list[str] = []

    if str(audio.get("codec") or "").lower() != "aac":
        blockers.append("PERSIAN_QG_AUDIO_CODEC_NOT_AAC")
    if int(_number(audio.get("sampleRate"))) != int(audio_limits.get("sampleRate") or 48000):
        blockers.append("PERSIAN_QG_AUDIO_SAMPLE_RATE_NOT_48000")
    if int(_number(audio.get("channels"))) != int(audio_limits.get("channels") or 2):
        blockers.append("PERSIAN_QG_AUDIO_NOT_STEREO")
    lufs = audio.get("measuredLufs")
    if not isinstance(lufs, (int, float)):
        blockers.append("PERSIAN_QG_AUDIO_LUFS_EVIDENCE_MISSING")
    elif not _number(audio_limits.get("lufsMin"), -16.0) <= float(lufs) <= _number(audio_limits.get("lufsMax"), -13.0):
        blockers.append("PERSIAN_QG_AUDIO_LUFS_OUTSIDE_REFERENCE_RANGE")
    peak = audio.get("measuredTruePeakDb")
    if not isinstance(peak, (int, float)) or float(peak) > _number(audio_limits.get("truePeakMaxDb"), -1.0):
        blockers.append("PERSIAN_QG_AUDIO_TRUE_PEAK_INVALID")

    if voice.get("finalMixNarrationDetected") is not True:
        blockers.append("PERSIAN_QG_NARRATION_NOT_PROVEN_IN_FINAL_MIX")
    if voice.get("asrVerified") is not True or not str(voice.get("asrTranscript") or "").strip():
        blockers.append("PERSIAN_QG_ASR_EVIDENCE_MISSING")
    if voice.get("asrProvenanceVerified") is not True:
        blockers.append("PERSIAN_QG_FINAL_ASR_PROVENANCE_INVALID")
    if not str(voice.get("language") or "").lower().startswith("fa"):
        blockers.append("PERSIAN_QG_VOICE_LANGUAGE_NOT_FA")
    similarity = _number(voice.get("scriptTranscriptSimilarity"))
    if similarity < _number(voice_limits.get("scriptTranscriptSimilarityMin"), 0.84):
        blockers.append("PERSIAN_QG_SCRIPT_TRANSCRIPT_MISMATCH")
    if _number(voice.get("persianCharacterRatio")) < _number(voice_limits.get("persianCharacterRatioMin"), 0.70):
        blockers.append("PERSIAN_QG_PERSIAN_SPEECH_RATIO_LOW")
    if voice.get("pronunciationReviewPassed") is not True:
        blockers.append("PERSIAN_QG_PRONUNCIATION_REVIEW_NOT_PASSED")
    if voice.get("pronunciationReviewAuthority") != ASR_AUTHORITY:
        blockers.append("PERSIAN_QG_PRONUNCIATION_AUTHORITY_INVALID")
    if voice.get("pronunciationReviewMethod") != "deterministic-final-mix-asr-lexicon-v1":
        blockers.append("PERSIAN_QG_PRONUNCIATION_METHOD_INVALID")

    if captions.get("present") is not True:
        blockers.append("PERSIAN_QG_CAPTIONS_MISSING")
    if captions.get("wordTiming") is not True:
        blockers.append("PERSIAN_QG_CAPTION_WORD_TIMING_MISSING")
    if captions.get("asrBackedWordTiming") is not True:
        blockers.append("PERSIAN_QG_CAPTION_NOT_ASR_BACKED")
    if _number(captions.get("coverageRatio")) < _number(caption_limits.get("coverageRatioMin"), 0.88):
        blockers.append("PERSIAN_QG_CAPTION_COVERAGE_LOW")
    if _number(captions.get("transcriptAgreement")) < _number(caption_limits.get("transcriptAgreementMin"), 0.88):
        blockers.append("PERSIAN_QG_CAPTION_TRANSCRIPT_MISMATCH")
    expected_accent = str(caption_limits.get("keywordHighlightColor") or "#F4B400").upper()
    if str(captions.get("keywordHighlightColor") or "").upper() != expected_accent:
        blockers.append("PERSIAN_QG_KEYWORD_HIGHLIGHT_MISSING")
    if int(_number(captions.get("maxWordsPerCue"))) > int(caption_limits.get("maxWordsPerCue") or 5):
        blockers.append("PERSIAN_QG_CAPTION_TOO_MANY_WORDS")
    if int(_number(captions.get("maxCharsPerCue"))) > int(caption_limits.get("maxCharsPerCue") or 42):
        blockers.append("PERSIAN_QG_CAPTION_TOO_LONG")

    if int(_number(visual.get("semanticBeatCount"))) < int(visual_limits.get("semanticBeatCountMin") or 7):
        blockers.append("PERSIAN_QG_VISUAL_BEAT_DENSITY_LOW")
    if _number(visual.get("maxUnchangedSeconds"), 99.0) > _number(visual_limits.get("maxUnchangedSeconds"), 2.5):
        blockers.append("PERSIAN_QG_VISUAL_STAGNATION")
    if visual.get("realIndustrialFootage") is not True:
        blockers.append("PERSIAN_QG_REAL_INDUSTRIAL_FOOTAGE_MISSING")
    if visual.get("thirdPartyWatermarkDetected") is not False:
        blockers.append("PERSIAN_QG_THIRD_PARTY_WATERMARK")
    for key, code in (
        ("logoPresent", "PERSIAN_QG_LOGO_MISSING"),
        ("ctaPresent", "PERSIAN_QG_CTA_MISSING"),
        ("sitePresent", "PERSIAN_QG_SITE_MISSING"),
        ("endCardPresent", "PERSIAN_QG_END_CARD_MISSING"),
    ):
        if brand.get(key) is not True:
            blockers.append(code)

    result = dict(evidence)
    result.update({
        "authority": AUTHORITY,
        "profileId": PROFILE_ID,
        "gatePass": not blockers,
        "releaseReady": not blockers,
        "blockers": blockers,
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed Persian cinematic perceptual quality gate")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    evidence = _read(Path(args.evidence), {})
    result = evaluate(evidence if isinstance(evidence, dict) else {})
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["gatePass"] else 73


if __name__ == "__main__":
    raise SystemExit(main())
