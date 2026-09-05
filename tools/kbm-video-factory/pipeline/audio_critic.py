#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import shutil
import subprocess
from array import array
from pathlib import Path
from typing import Any

PACKAGE = "KBM-VIDEO-FACTORY-AVALAI-LIVE-CREATIVE-HARDENING-13.1.1"
VERSION = "13.1.1"
CAMP_AUDIO_LIMITS = {
    "technicalAudioScore": 8.2,
    "lufsMin": -16.0,
    "lufsMax": -12.0,
    "truePeakMaxDb": -1.0,
    "clipRatioMax": 0.0002,
}


def _db(value: float) -> float:
    return 20.0 * math.log10(max(1e-12, value))


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return -120.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * max(0.0, min(1.0, ratio))))
    return float(ordered[index])


def _extract_pcm(video: Path, sample_rate: int = 16000) -> array:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not video.is_file():
        return array("f")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(video),
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "f32le",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120)
    except Exception:
        return array("f")
    if result.returncode != 0 or len(result.stdout) < 4:
        return array("f")
    samples = array("f")
    try:
        samples.frombytes(result.stdout)
    except Exception:
        return array("f")
    return samples


def _loudnorm(video: Path) -> dict[str, float]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not video.is_file():
        return {}
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i", str(video),
        "-vn",
        "-af", "loudnorm=I=-14:TP=-1:LRA=7:print_format=json",
        "-f", "null",
        "-",
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=False, timeout=120)
    except Exception:
        return {}
    text = result.stderr or ""
    start, end = text.rfind("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        raw = json.loads(text[start:end + 1])
    except Exception:
        return {}

    def number(name: str) -> float | None:
        try:
            value = float(raw.get(name))
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    mapped = {
        "measuredLufs": number("input_i"),
        "measuredTruePeakDb": number("input_tp"),
        "measuredLra": number("input_lra"),
        "measuredThresholdDb": number("input_thresh"),
    }
    return {k: round(float(v), 3) for k, v in mapped.items() if v is not None}


def _technical_score(evidence: dict[str, Any]) -> float:
    if not evidence.get("audioPresent"):
        return 0.0
    score = 10.0
    lufs = evidence.get("measuredLufs")
    peak = evidence.get("measuredTruePeakDb")
    activity = float(evidence.get("activityRatio") or 0.0)
    variation = float(evidence.get("energyVariationDb") or 0.0)
    clip_ratio = float(evidence.get("clipRatio") or 0.0)

    if isinstance(lufs, (int, float)):
        if lufs < -22 or lufs > -8:
            score -= 3.0
        elif lufs < -18 or lufs > -10:
            score -= 1.2
    if isinstance(peak, (int, float)):
        if peak > -0.2:
            score -= 2.0
        elif peak > -0.8:
            score -= 0.8
        elif peak < -8:
            score -= 1.0
    if activity < 0.20:
        score -= 3.0
    elif activity < 0.45:
        score -= 1.2
    if variation < 1.2:
        score -= 2.0
    elif variation < 2.5:
        score -= 0.8
    elif variation > 24:
        score -= 0.8
    if clip_ratio > 0.002:
        score -= 2.5
    elif clip_ratio > 0.0002:
        score -= 0.8
    return round(max(0.0, min(10.0, score)), 2)


def camp_audio_gate(evidence: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if evidence.get("audioPresent") is not True:
        blockers.append("AUDIO_MISSING")
    if float(evidence.get("technicalAudioScore") or 0.0) < CAMP_AUDIO_LIMITS["technicalAudioScore"]:
        blockers.append("AUDIO_TECHNICAL_SCORE_LOW")
    lufs = evidence.get("measuredLufs")
    if not isinstance(lufs, (int, float)):
        blockers.append("AUDIO_LUFS_EVIDENCE_MISSING")
    elif not CAMP_AUDIO_LIMITS["lufsMin"] <= float(lufs) <= CAMP_AUDIO_LIMITS["lufsMax"]:
        blockers.append("AUDIO_LUFS_OUTSIDE_CAMP_RANGE")
    peak = evidence.get("measuredTruePeakDb")
    if not isinstance(peak, (int, float)):
        blockers.append("AUDIO_TRUE_PEAK_EVIDENCE_MISSING")
    elif float(peak) > CAMP_AUDIO_LIMITS["truePeakMaxDb"]:
        blockers.append("AUDIO_TRUE_PEAK_TOO_HIGH")
    if float(evidence.get("clipRatio") or 0.0) > CAMP_AUDIO_LIMITS["clipRatioMax"]:
        blockers.append("AUDIO_CLIPPING")
    return {"pass": not blockers, "blockers": blockers, "limits": CAMP_AUDIO_LIMITS}


def analyze_audio(video: Path, sample_rate: int = 16000) -> dict[str, Any]:
    samples = _extract_pcm(video, sample_rate=sample_rate)
    if not samples:
        evidence = {
            "package": PACKAGE,
            "version": VERSION,
            "audioPresent": False,
            "technicalAudioScore": 0.0,
            "reason": "No decodable audio evidence",
        }
        evidence["campAudioGate"] = camp_audio_gate(evidence)
        return evidence

    frame = max(1, int(sample_rate * 0.10))
    levels: list[float] = []
    total_sq = 0.0
    peak = 0.0
    clipped = 0
    for index in range(0, len(samples), frame):
        chunk = samples[index:index + frame]
        if not chunk:
            continue
        square = sum(float(x) * float(x) for x in chunk)
        total_sq += square
        local_peak = max(abs(float(x)) for x in chunk)
        peak = max(peak, local_peak)
        clipped += sum(1 for x in chunk if abs(float(x)) >= 0.999)
        levels.append(_db(math.sqrt(square / len(chunk))))

    duration = len(samples) / float(sample_rate)
    rms = math.sqrt(total_sq / max(1, len(samples)))
    active_levels = [value for value in levels if value > -45.0]
    activity_ratio = len(active_levels) / max(1, len(levels))
    p10 = _percentile(active_levels or levels, 0.10)
    p90 = _percentile(active_levels or levels, 0.90)
    evidence: dict[str, Any] = {
        "package": PACKAGE,
        "version": VERSION,
        "audioPresent": True,
        "sampleRate": sample_rate,
        "durationSeconds": round(duration, 3),
        "rmsDbfs": round(_db(rms), 3),
        "peakDbfs": round(_db(peak), 3),
        "activityRatio": round(activity_ratio, 4),
        "silenceRatio": round(1.0 - activity_ratio, 4),
        "energyVariationDb": round(max(0.0, p90 - p10), 3),
        "energyP10Dbfs": round(p10, 3),
        "energyP90Dbfs": round(p90, 3),
        "clipRatio": round(clipped / max(1, len(samples)), 7),
        "windowMs": 100,
    }
    evidence.update(_loudnorm(video))
    evidence["technicalAudioScore"] = _technical_score(evidence)
    evidence["campAudioGate"] = camp_audio_gate(evidence)
    return evidence
