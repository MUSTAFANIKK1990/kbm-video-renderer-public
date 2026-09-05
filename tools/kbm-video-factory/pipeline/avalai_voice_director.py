#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from audio_critic import analyze_audio
from avalai_creative_client import chat_json, classify_cupai_error
from persian_asr_quality import transcribe_media, write_pronunciation_review
from tts_client import synthesize_speech

TAKES = [
    ("commercial", "با کیفیت استودیویی و لحن تبلیغاتی حرفه‌ای، پرانرژی و مطمئن فارسی صحبت کن. جمله اول ضربه‌ای و کنجکاوی‌ساز باشد، روی واژه‌های کلیدی تاکید شنیداری مشخص داشته باش، بین جمله‌ها مکث کوتاه و طبیعی بده و CTA را دعوت‌کننده و پرقدرت تمام کن. لحن یکنواخت نباشد."),
    ("industrial", "با کیفیت استودیویی و لحن صنعتی، معتبر و جدی فارسی صحبت کن. کلمات فنی را واضح بگو، روی نکات کلیدی تاکید کنترل‌شده داشته باش، شدت و سرعت جمله‌ها کمی تغییر کند و پایان CTA قاطع باشد. لحن تخت و یکنواخت نباشد."),
    ("social", "با کیفیت استودیویی و لحن طبیعی، امروزی و مناسب ریلز اینستاگرام فارسی صحبت کن. شروع سریع و punchy باشد، ریتم جمله‌ها متنوع اما کاملاً قابل فهم باشد، روی Hook و CTA تاکید واضح بده و از لحن یکنواخت پرهیز کن."),
]

CREDIT_EXHAUSTED_TOKENS = (
    "insufficient_quota",
    "quota_exceeded",
    "credit_not_enough",
    "credit has been exhausted",
    "credit exhausted",
    "cupai_credit_exhausted",
)


def _duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        raw = subprocess.check_output([
            ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)
        ], text=True, timeout=20).strip()
        return max(0.0, float(raw))
    except Exception:
        return 0.0


def _words(text: str) -> list[str]:
    return [part for part in re.split(r"\s+", text.strip()) if part]


def _is_persian(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]", text or ""))


def _deterministic_compact(text: str, budget: int) -> str:
    words = _words(text)
    if len(words) <= budget:
        return text.strip()
    sentences = [part.strip() for part in re.split(r"(?<=[.!؟])\s+|\n+", text) if part.strip()]
    if len(sentences) >= 2:
        first = _words(sentences[0])
        last = _words(sentences[-1])
        last_keep = min(len(last), max(5, budget // 3))
        first_keep = max(4, budget - last_keep)
        combined = first[:first_keep] + last[-last_keep:]
        return " ".join(combined[:budget]).strip()
    return " ".join(words[:budget]).strip()


def _fit_script(text: str, target_seconds: float) -> tuple[str, dict[str, Any]]:
    original = " ".join(text.split()).strip()
    target = max(4.0, float(target_seconds))
    words_per_second = 1.45 if _is_persian(original) else 2.10
    budget = max(12, min(72, int(round(target * words_per_second))))
    original_words = len(_words(original))
    if original_words <= budget:
        return original, {
            "compacted": False,
            "method": "not-needed",
            "wordBudget": budget,
            "wordsPerSecondBudget": words_per_second,
            "originalWords": original_words,
            "fittedWords": original_words,
        }

    fitted = ""
    method = "deterministic"
    try:
        response = chat_json(
            f"""
Rewrite this Persian commercial voice-over to at most {budget} words so it can be spoken naturally in about {target:.1f} seconds.
Preserve only claims already present. Preserve the final CTA or next-step intent. Do not add prices, guarantees, specifications or new facts.
Return JSON only with one key: voiceoverScript.
Source:
{original[:1400]}
""".strip(),
            attempts=1,
        )
        candidate = " ".join(str(response.get("voiceoverScript") or "").split()).strip()
        candidate_words = len(_words(candidate))
        if candidate and 4 <= candidate_words <= budget:
            fitted = candidate
            method = "cupai-bounded-rewrite"
    except Exception:
        fitted = ""

    if not fitted:
        fitted = _deterministic_compact(original, budget)
    return fitted, {
        "compacted": fitted != original,
        "method": method,
        "wordBudget": budget,
        "wordsPerSecondBudget": words_per_second,
        "originalWords": original_words,
        "fittedWords": len(_words(fitted)),
    }


def _voice_dynamics(path: Path) -> tuple[float, dict[str, Any]]:
    evidence = analyze_audio(path)
    technical = float(evidence.get("technicalAudioScore") or 0.0)
    variation = float(evidence.get("energyVariationDb") or 0.0)
    activity = float(evidence.get("activityRatio") or 0.0)
    lra = float(evidence.get("measuredLra") or 0.0)

    score = 5.8
    if variation >= 6.0:
        score += 2.1
    elif variation >= 4.0:
        score += 1.8
    elif variation >= 2.5:
        score += 1.4
    elif variation >= 1.8:
        score += 0.9

    if 0.45 <= activity <= 0.96:
        score += 0.9
    elif 0.30 <= activity < 0.45:
        score += 0.45

    if lra >= 4.0:
        score += 0.8
    elif lra >= 2.0:
        score += 0.5
    elif lra >= 1.0:
        score += 0.2

    if technical >= 8.2:
        score += 0.4
    elif technical >= 7.0:
        score += 0.2

    if variation < 1.2 or activity < 0.20:
        score = min(score, 7.4)
    elif variation < 1.8:
        score = min(score, 7.8)

    evidence = {
        **evidence,
        "voiceDynamicsMethod": "expression-energy-activity-lra-v2",
        "voiceDynamicsInputs": {
            "energyVariationDb": round(variation, 3),
            "activityRatio": round(activity, 4),
            "measuredLra": round(lra, 3),
            "technicalAudioScore": round(technical, 2),
        },
    }
    return round(max(0.0, min(10.0, score)), 2), evidence


def _select_take(pool: list[dict[str, Any]], selection_target: float, dynamics_floor: float = 8.0) -> dict[str, Any]:
    if not pool:
        raise ValueError("voice take pool is empty")
    healthy = [item for item in pool if float(item.get("voiceDynamics") or 0.0) >= dynamics_floor]
    if healthy:
        return min(
            healthy,
            key=lambda item: (
                abs(float(item.get("duration") or selection_target) - selection_target),
                -float(item.get("voiceDynamics") or 0.0),
            ),
        )
    return max(
        pool,
        key=lambda item: (
            float(item.get("voiceDynamics") or 0.0),
            -abs(float(item.get("duration") or selection_target) - selection_target),
        ),
    )


def _selected_take_complete(path: Path, duration_seconds: float) -> bool:
    """Director completion means one selected, decodable take exists.

    Maximum mode asks for multiple alternative takes for editorial choice. Those are
    optional candidates, not independent release requirements. Partial candidate
    failure must remain visible in telemetry but must not mark the director incomplete
    when a valid selected take exists. Duration and dynamics remain separate hard gates.
    """
    return path.is_file() and float(duration_seconds) > 0.0


def _speed_fit_take(path: Path, ceiling_seconds: float) -> dict[str, Any]:
    before = _duration(path)
    if before <= 0 or before <= ceiling_seconds:
        return {"applied": False, "beforeSeconds": round(before, 3), "afterSeconds": round(before, 3), "speed": 1.0}
    required = before / max(0.1, ceiling_seconds)
    speed = min(1.22, max(1.0, required * 1.018))
    if speed <= 1.005:
        return {"applied": False, "beforeSeconds": round(before, 3), "afterSeconds": round(before, 3), "speed": 1.0}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"applied": False, "beforeSeconds": round(before, 3), "afterSeconds": round(before, 3), "speed": 1.0, "reason": "ffmpeg-missing"}
    with tempfile.TemporaryDirectory(prefix="kbm-voice-fit-") as temporary:
        output = Path(temporary) / "fit.mp3"
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
            "-filter:a", f"atempo={speed:.6f}", "-c:a", "libmp3lame", "-b:a", "192k", str(output),
        ]
        result = subprocess.run(command, check=False, timeout=120)
        if result.returncode != 0 or not output.is_file():
            return {"applied": False, "beforeSeconds": round(before, 3), "afterSeconds": round(before, 3), "speed": round(speed, 4), "reason": "ffmpeg-fit-failed"}
        shutil.copy2(output, path)
    after = _duration(path)
    return {"applied": True, "beforeSeconds": round(before, 3), "afterSeconds": round(after, 3), "speed": round(speed, 4)}


def _credit_exhausted(error: Exception | str, diagnostic: dict[str, Any] | None = None) -> bool:
    if isinstance(diagnostic, dict) and diagnostic.get("quotaBlocked") is True:
        return True
    text = str(error).lower()
    return any(token in text for token in CREDIT_EXHAUSTED_TOKENS)


def _credit_diagnostic(error: Exception | str) -> dict[str, Any]:
    reason = re.sub(r"\s+", " ", str(error)).strip()[:320]
    return {
        "code": "CUPAI_CREDIT_EXHAUSTED",
        "retryable": False,
        "quotaBlocked": True,
        "reason": reason,
    }


def direct_voice(
    text: str,
    work: Path,
    *,
    voice: str,
    max_seconds: float,
    maximum: bool,
) -> dict[str, Any]:
    take_specs = TAKES if maximum else TAKES[:1]
    generated: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    # Count actual provider attempts; selection failures must never inflate cost evidence.
    attempted_takes = 0
    target = max(4.0, min(max_seconds * 0.84, max_seconds - 1.5))
    selection_target = max(4.0, min(target, max_seconds * 0.75))
    fitted_text, fit_report = _fit_script(text, target)
    ceiling = max(3.0, min(max_seconds - 0.45, target * 1.12))
    floor = max(2.5, target * 0.52)

    for index, (name, instructions) in enumerate(take_specs, start=1):
        attempted_takes += 1
        destination = work / f"cupai-voice-{index}-{name}.mp3"
        timed_instructions = (
            f"{instructions} مدت هدف نریشن حدود {selection_target:.1f} ثانیه است؛ "
            f"متن را طبیعی و فشرده اجرا کن، از کش‌دادن کلمات پرهیز کن و حداکثر در {ceiling:.1f} ثانیه تمام کن تا برای CTA تصویری انتهای ریل فضا باقی بماند. "
            "نام کاریاب ماشین و واژه‌های فنی را شمرده و بدون تلفظ انگلیسی‌زده ادا کن؛ Hook و CTA باید از نظر شدت و فراز و فرود کاملاً شنیدنی باشند."
        )
        try:
            report = synthesize_speech(fitted_text, destination, voice=voice, instructions=timed_instructions)
            duration = _duration(destination)
            if duration <= 0:
                raise RuntimeError("CUPAI_TTS_INVALID_AUDIO: generated take is not decodable audio")
            dynamics, dynamics_evidence = _voice_dynamics(destination)
            generated.append({
                **report,
                "path": str(destination.resolve()),
                "take": name,
                "instructions": timed_instructions,
                "duration": duration,
                "voiceDynamics": dynamics,
                "voiceDynamicsEvidence": dynamics_evidence,
            })
        except Exception as exc:
            diagnostic = classify_cupai_error(exc)
            if _credit_exhausted(exc, diagnostic):
                diagnostic = _credit_diagnostic(exc)
            failures.append({"take": name, **diagnostic})
            if destination.exists():
                destination.unlink(missing_ok=True)
            if diagnostic.get("quotaBlocked") is True or diagnostic.get("code") in {"CUPAI_TTS_CHANNEL_UNAVAILABLE", "AVALAI_TTS_CHANNEL_UNAVAILABLE"}:
                break

    # In strict Persian mode, pronunciation is the first selection criterion.
    strict_persian_asr = os.environ.get("KBM_PERSIAN_QUALITY_GATE", "").strip() == "1"
    pronunciation_eligible: list[dict[str, Any]] = []
    if strict_persian_asr:
        for item in generated:
            take = str(item.get("take") or "candidate")
            candidate = Path(str(item.get("path") or "")).expanduser()
            try:
                transcript = transcribe_media(
                    candidate,
                    work / f"package13-1-voice-selection-{take}-asr.json",
                    output_dir=work / f"package13-1-voice-selection-{take}-whisperx",
                )
                review = write_pronunciation_review(
                    work / f"package13-1-voice-selection-{take}-pronunciation.json",
                    fitted_text,
                    transcript,
                )
                item["pronunciationReview"] = review
                item["pronunciationReviewPass"] = review.get("pass") is True
                if item["pronunciationReviewPass"]:
                    pronunciation_eligible.append(item)
            except Exception as exc:
                item["pronunciationReview"] = {"pass": False, "error": str(exc)[-400:]}
                item["pronunciationReviewPass"] = False
        if not pronunciation_eligible:
            failures.append({
                "take": "selection",
                "code": "CUPAI_TTS_NO_PRONOUNCING_TAKE",
                "retryable": False,
                "quotaBlocked": False,
            })

    manifest_path = work / "package13-1-voice-manifest.json"
    if not generated:
        manifest = {
            "engine": "cupai-directed-tts",
            "voice": voice,
            "language": "fa-IR",
            "deliveryProfile": "persian-industrial-explainer-20260903",
            "finalMixAsrRequired": True,
            "pronunciationReviewRequired": True,
            "requestedTakeCount": len(take_specs),
            "attemptedTakeCount": attempted_takes,
            "takeCount": 0,
            "complete": False,
            "allRequestedTakesGenerated": False,
            "partialTakeFailure": bool(failures),
            "completionPolicy": "selected-decodable-take-v1",
            "selectedTakePlayable": False,
            "durationFit": False,
            "voiceDynamics": 0.0,
            "voiceDynamicsFloor": 8.0,
            "targetSeconds": round(target, 3),
            "selectionTargetSeconds": round(selection_target, 3),
            "durationFloorSeconds": round(floor, 3),
            "durationCeilingSeconds": round(ceiling, 3),
            "scriptOriginal": text,
            "scriptUsed": fitted_text,
            "scriptFit": fit_report,
            "selectedTake": None,
            "selectedPath": None,
            "selectedDuration": None,
            "takes": [],
            "failures": failures,
            "providerCreditBlocked": any(item.get("quotaBlocked") is True for item in failures),
            "providerChannelBlocked": any(item.get("code") == "CUPAI_TTS_CHANNEL_UNAVAILABLE" for item in failures),
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        codes = ",".join(sorted({str(x.get("code") or "CUPAI_TTS_FAILED") for x in failures}))
        raise RuntimeError(f"CUPAI_TTS_ALL_TAKES_FAILED: {codes or 'unknown'}")

    valid = [item for item in generated if floor <= float(item.get("duration") or 0) <= ceiling]
    pronunciation_valid = [
        item for item in pronunciation_eligible
        if floor <= float(item.get("duration") or 0) <= ceiling
    ]
    pool = pronunciation_valid or pronunciation_eligible or valid or generated
    selected = _select_take(pool, selection_target, dynamics_floor=8.0)

    speed_fit = {"applied": False}
    selected_path = Path(str(selected.get("path") or "")).expanduser()
    selected_duration = float(selected.get("duration") or 0)
    if selected_path.is_file() and selected_duration > ceiling and selected_duration / max(ceiling, 0.1) <= 1.22:
        speed_fit = _speed_fit_take(selected_path, ceiling)
        if speed_fit.get("applied"):
            selected_duration = _duration(selected_path)
            dynamics, dynamics_evidence = _voice_dynamics(selected_path)
            selected["duration"] = selected_duration
            selected["voiceDynamics"] = dynamics
            selected["voiceDynamicsEvidence"] = dynamics_evidence

    duration_fit = floor <= selected_duration <= ceiling
    selected_take_playable = _selected_take_complete(selected_path, selected_duration)
    all_requested_generated = len(generated) == len(take_specs)
    manifest = {
        "engine": "cupai-directed-tts",
        "voice": voice,
        "language": "fa-IR",
        "deliveryProfile": "persian-industrial-explainer-20260903",
        "finalMixAsrRequired": True,
        "pronunciationReviewRequired": True,
        "pronunciationSelectionRequired": strict_persian_asr,
        "pronunciationEligibleTakeCount": len(pronunciation_eligible),
        "requestedTakeCount": len(take_specs),
        "attemptedTakeCount": attempted_takes,
        "takeCount": len(generated),
        "complete": selected_take_playable,
        "allRequestedTakesGenerated": all_requested_generated,
        "partialTakeFailure": bool(failures),
        "completionPolicy": "selected-decodable-take-v1",
        "selectedTakePlayable": selected_take_playable,
        "durationFit": duration_fit,
        "voiceDynamics": selected.get("voiceDynamics"),
        "voiceDynamicsFloor": 8.0,
        "voiceDynamicsEvidence": selected.get("voiceDynamicsEvidence"),
        "targetSeconds": round(target, 3),
        "selectionTargetSeconds": round(selection_target, 3),
        "durationFloorSeconds": round(floor, 3),
        "durationCeilingSeconds": round(ceiling, 3),
        "selectedDuration": round(selected_duration, 3),
        "durationDeltaSeconds": round(selected_duration - selection_target, 3),
        "selectionPolicy": "dynamics-floor-then-duration-fit-v1",
        "scriptOriginal": text,
        "scriptUsed": fitted_text,
        "scriptFit": fit_report,
        "durationRepair": speed_fit,
        "selectedTake": selected.get("take"),
        "selectedPronunciationReview": selected.get("pronunciationReview"),
        "selectedPath": str(selected_path.resolve()) if selected_take_playable else None,
        "takes": [
            {k: item.get(k) for k in ("take", "model", "voice", "duration", "bytes", "path", "contentType", "voiceDynamics")}
            for item in generated
        ],
        "failures": failures,
        "providerCreditBlocked": any(item.get("quotaBlocked") is True for item in failures),
        "providerChannelBlocked": any(item.get("code") == "CUPAI_TTS_CHANNEL_UNAVAILABLE" for item in failures),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
