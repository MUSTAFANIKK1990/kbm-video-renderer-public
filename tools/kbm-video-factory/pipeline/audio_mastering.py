#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from audio_critic import analyze_audio
from ingest import audio_present, duration_seconds, probe, require

PACKAGE = "KBM-VIDEO-FACTORY-FULL-CINEMATIC-EDITORIAL-13"


def _linear_ceiling(db: float) -> float:
    return max(0.10, min(0.99, 10.0 ** (float(db) / 20.0)))


def _loudnorm_measure(ffmpeg: str, path: Path, filter_chain: str) -> dict[str, float]:
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-vn",
        "-af",
        filter_chain,
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"CAMP loudnorm measurement failed: {(result.stderr or '')[-500:]}")
    text = result.stderr or ""
    start, end = text.rfind("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError("CAMP loudnorm measurement JSON is missing")
    try:
        raw = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("CAMP loudnorm measurement JSON is invalid") from exc

    mapping = {
        "input_i": "input_i",
        "input_tp": "input_tp",
        "input_lra": "input_lra",
        "input_thresh": "input_thresh",
        "target_offset": "target_offset",
    }
    measured: dict[str, float] = {}
    for target, source in mapping.items():
        try:
            value = float(raw.get(source))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"CAMP loudnorm measurement {source} is missing") from exc
        if not math.isfinite(value):
            raise RuntimeError(f"CAMP loudnorm measurement {source} is not finite")
        measured[target] = value
    return measured


def _encode_filtered(ffmpeg: str, path: Path, filter_chain: str) -> None:
    with tempfile.TemporaryDirectory(prefix="kbm-audio-master-") as temporary:
        output = Path(temporary) / "mastered.mp4"
        command = [
            ffmpeg, "-y", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "copy", "-af", filter_chain, "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-movflags", "+faststart", str(output),
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.copy2(output, path)


def _gate_pass(evidence: dict[str, Any]) -> bool:
    gate = evidence.get("campAudioGate") if isinstance(evidence.get("campAudioGate"), dict) else {}
    return gate.get("pass") is True


def master_for_reels(path: Path, *, target_lufs: float = -14.0, target_lra: float = 7.0, true_peak: float = -1.0) -> dict[str, Any]:
    path = path.expanduser().resolve()
    info = probe(path)
    duration = duration_seconds(info)
    if not audio_present(info) or duration <= 0.5:
        return {"package": PACKAGE, "status": "SKIPPED", "reason": "no-audio", "path": str(path)}

    ffmpeg = require("ffmpeg")
    fade_out_start = max(0.0, duration - 0.38)

    # CAMP keeps a conservative AAC ceiling. The hard release thresholds live
    # in audio_critic/cinematic_ad_protocol and are not relaxed here.
    requested_true_peak = float(true_peak)
    camp_strict = requested_true_peak <= -1.5
    effective_true_peak = min(requested_true_peak, -2.0 if camp_strict else -1.5)
    limiter_ceiling_db = -1.4 if camp_strict else effective_true_peak
    limiter_ceiling = _linear_ceiling(limiter_ceiling_db)
    base_chain = (
        f"highpass=f=32,lowpass=f=19000,"
        f"afade=t=in:st=0:d=0.12,afade=t=out:st={fade_out_start:.3f}:d=0.36"
    )
    measured: dict[str, float] | None = None

    if camp_strict:
        pre_chain = (
            f"highpass=f=32,lowpass=f=19000,"
            f"acompressor=threshold=0.10:ratio=4:attack=8:release=100:makeup=2.5,"
            f"afade=t=in:st=0:d=0.12,afade=t=out:st={fade_out_start:.3f}:d=0.36"
        )
        measure_chain = (
            f"{pre_chain},"
            f"loudnorm=I={target_lufs}:LRA={target_lra}:TP={effective_true_peak}:print_format=json"
        )
        measured = _loudnorm_measure(ffmpeg, path, measure_chain)
        filter_chain = (
            f"{pre_chain},"
            f"loudnorm=I={target_lufs}:LRA={target_lra}:TP={effective_true_peak}:linear=false,"
            f"alimiter=limit={limiter_ceiling:.6f}:attack=5:release=80:level=false"
        )
        mastering_chain = "camp-strict-premeasure-dynamic-loudnorm-postlimiter-calibrated"
    else:
        filter_chain = (
            f"{base_chain},"
            f"loudnorm=I={target_lufs}:LRA={target_lra}:TP={effective_true_peak},"
            f"alimiter=limit={limiter_ceiling:.6f}:attack=5:release=50:level=false"
        )
        mastering_chain = "highpass-lowpass-fades-loudnorm-postlimiter"

    _encode_filtered(ffmpeg, path, filter_chain)
    post_encode_evidence = analyze_audio(path)
    corrective_passes: list[dict[str, Any]] = []

    # Run 33330744652 proved that a valid pre-master target can still land at
    # -17.41 LUFS with AAC sample overshoot. CAMP therefore measures the actual
    # encoded file and allows at most two deterministic corrective passes.
    # This is a calibration step, not a gate relaxation.
    if camp_strict and not _gate_pass(post_encode_evidence):
        correction_profiles = [
            {"lufs": -11.5, "lra": 6.0, "tp": -3.0, "limit": 0.66},
            {"lufs": -10.5, "lra": 5.5, "tp": -3.2, "limit": 0.64},
        ]
        for index, profile in enumerate(correction_profiles, start=1):
            blockers = ((post_encode_evidence.get("campAudioGate") or {}).get("blockers") or [])
            corrective_chain = (
                "highpass=f=32,lowpass=f=19000,"
                "acompressor=threshold=-18dB:ratio=2:attack=10:release=100:makeup=3dB,"
                f"loudnorm=I={profile['lufs']}:LRA={profile['lra']}:TP={profile['tp']}:linear=false,"
                f"alimiter=limit={profile['limit']:.6f}:attack=5:release=80:level=false"
            )
            before = {
                "measuredLufs": post_encode_evidence.get("measuredLufs"),
                "measuredTruePeakDb": post_encode_evidence.get("measuredTruePeakDb"),
                "clipRatio": post_encode_evidence.get("clipRatio"),
                "blockers": blockers,
            }
            _encode_filtered(ffmpeg, path, corrective_chain)
            post_encode_evidence = analyze_audio(path)
            corrective_passes.append({
                "pass": index,
                "profile": profile,
                "before": before,
                "after": {
                    "measuredLufs": post_encode_evidence.get("measuredLufs"),
                    "measuredTruePeakDb": post_encode_evidence.get("measuredTruePeakDb"),
                    "clipRatio": post_encode_evidence.get("clipRatio"),
                    "gate": post_encode_evidence.get("campAudioGate"),
                },
            })
            if _gate_pass(post_encode_evidence):
                break

    result = probe(path)
    report: dict[str, Any] = {
        "package": PACKAGE,
        "status": "PASS" if _gate_pass(post_encode_evidence) or not camp_strict else "DEGRADED",
        "path": str(path),
        "durationSeconds": round(duration_seconds(result), 3),
        "targetLufs": target_lufs,
        "targetLra": target_lra,
        "requestedTruePeakDb": requested_true_peak,
        "effectiveTruePeakDb": effective_true_peak,
        "limiterCeilingDb": limiter_ceiling_db,
        "limiterCeilingLinear": round(limiter_ceiling, 6),
        "masteringChain": mastering_chain,
        "campStrict": camp_strict,
        "postEncodeEvidence": post_encode_evidence,
        "correctivePasses": corrective_passes,
    }
    if measured is not None:
        report["preMasterMeasurement"] = {key: round(value, 3) for key, value in measured.items()}
    return report


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    try:
        result = master_for_reels(Path(args.input))
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "message": str(exc)[-500:]}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
