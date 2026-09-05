#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

from audio_critic import analyze_audio
from perceptual_quality_gate import evaluate as evaluate_perceptual_quality

PACKAGE = "KBM-VIDEO-FACTORY-CAMP-13.2"
VERSION = "13.2.0-rc.1"
AUTHORITY = "KBM-CAMP-13.2-CINEMATIC-AD-MASTER-AUTHORITY"

ALLOWED_VERTICALS = {
    "rental",
    "machine-sale",
    "services",
    "drivers",
    "tenders",
    "articles",
    "generic",
}

CRITIC_FLOORS = {
    "hook": 8.2,
    "pacing": 8.0,
    "brollRelevance": 8.3,
    "shotVariety": 8.0,
    "brandVisibility": 8.3,
    "captionReadability": 8.3,
    "audioEnergy": 8.2,
    "ctaStrength": 8.3,
    "overall": 8.3,
}

AUDIO_LIMITS = {
    "technicalAudioScore": 8.2,
    "lufsMin": -16.0,
    "lufsMax": -12.0,
    "truePeakMaxDb": -1.0,
    "clipRatioMax": 0.0002,
}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def normalize_brief(
    *,
    topic: str,
    vertical: str,
    duration_seconds: float = 20.0,
    goal: str = "conversion",
    cta: str = "",
    website_routes: list[str] | None = None,
) -> dict[str, Any]:
    normalized_vertical = (vertical or "generic").strip().lower()
    if normalized_vertical not in ALLOWED_VERTICALS:
        raise ValueError(f"Unsupported CAMP vertical: {normalized_vertical}")
    duration = max(6.0, min(60.0, float(duration_seconds)))
    cleaned_topic = " ".join((topic or "").split()).strip()
    if not cleaned_topic:
        raise ValueError("CAMP topic is required")
    routes = [str(item).strip() for item in (website_routes or []) if str(item).strip()]
    return {
        "package": PACKAGE,
        "version": VERSION,
        "authority": AUTHORITY,
        "topic": cleaned_topic,
        "vertical": normalized_vertical,
        "goal": " ".join((goal or "conversion").split()).strip() or "conversion",
        "durationSeconds": round(duration, 3),
        "cta": " ".join((cta or "").split()).strip(),
        "websiteRoutes": routes,
        "storyArc": ["hook", "problem", "tension", "solution", "proof", "benefit", "cta"],
        "qualityProfile": "cinematic-ad-master",
        "releasePolicy": "hard-gate",
    }


def _ffprobe(video: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not video.is_file():
        return {}
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate",
        "-of",
        "json",
        str(video),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
    except Exception:
        return {}
    if result.returncode != 0:
        return {}
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {}


def _fps(value: Any) -> float:
    text = str(value or "0/1")
    if "/" in text:
        left, right = text.split("/", 1)
        denominator = _number(right, 1.0) or 1.0
        return _number(left) / denominator
    return _number(text)


def validate_technical(video: Path, expected_duration: float) -> dict[str, Any]:
    probe = _ffprobe(video)
    streams = probe.get("streams") if isinstance(probe, dict) else []
    streams = streams if isinstance(streams, list) else []
    video_streams = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"]
    audio_streams = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"]
    primary = video_streams[0] if video_streams else {}
    fmt = probe.get("format") if isinstance(probe, dict) else {}
    fmt = fmt if isinstance(fmt, dict) else {}
    duration = _number(fmt.get("duration"))
    measured_fps = _fps(primary.get("r_frame_rate"))
    blockers: list[str] = []
    if not video.is_file():
        blockers.append("OUTPUT_MISSING")
    if int(primary.get("width") or 0) != 1080 or int(primary.get("height") or 0) != 1920:
        blockers.append("RESOLUTION_NOT_1080X1920")
    if str(primary.get("codec_name") or "").lower() not in {"h264", "avc1"}:
        blockers.append("VIDEO_CODEC_NOT_H264")
    if not 29.7 <= measured_fps <= 30.3:
        blockers.append("FPS_NOT_30")
    if len(audio_streams) != 1:
        blockers.append("AUDIO_STREAM_COUNT_NOT_ONE")
    elif str(audio_streams[0].get("codec_name") or "").lower() != "aac":
        blockers.append("AUDIO_CODEC_NOT_AAC")
    tolerance = max(0.20, expected_duration * 0.015)
    if abs(duration - expected_duration) > tolerance:
        blockers.append("DURATION_OUTSIDE_CAMP_TOLERANCE")
    return {
        "pass": not blockers,
        "blockers": blockers,
        "width": int(primary.get("width") or 0),
        "height": int(primary.get("height") or 0),
        "fps": round(measured_fps, 3),
        "videoCodec": primary.get("codec_name"),
        "audioCodec": audio_streams[0].get("codec_name") if len(audio_streams) == 1 else None,
        "audioStreamCount": len(audio_streams),
        "durationSeconds": round(duration, 3),
        "sizeBytes": int(_number(fmt.get("size"))),
    }


def validate_renderer(renderer: dict[str, Any]) -> dict[str, Any]:
    name = str(renderer.get("renderer") or "").strip().lower()
    fallback = renderer.get("fallback") is True
    blockers: list[str] = []
    if name != "remotion":
        blockers.append("CAMP_REMOTION_RENDER_REQUIRED")
    if fallback:
        blockers.append("CAMP_FALLBACK_RENDER_NOT_RELEASABLE")
    if renderer.get("releaseEligible") is False:
        blockers.append("RENDERER_MARKED_NON_RELEASE")
    return {"pass": not blockers, "blockers": blockers, "renderer": name, "fallback": fallback}


def validate_voice(manifest: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if manifest.get("complete") is not True:
        blockers.append("VOICE_DIRECTOR_INCOMPLETE")
    if manifest.get("durationFit") is not True:
        blockers.append("VOICE_DURATION_NOT_FIT")
    if int(manifest.get("selectedTrackCount") or manifest.get("narrationTrackCount") or 1) != 1:
        blockers.append("MULTIPLE_NARRATION_TRACKS")
    if "voiceDynamics" not in manifest:
        blockers.append("VOICE_DYNAMICS_EVIDENCE_MISSING")
    dynamics = _number(manifest.get("voiceDynamics"))
    if dynamics < 8.0:
        blockers.append("VOICE_DYNAMICS_LOW")
    if manifest.get("sourceAudioMuted") is False:
        blockers.append("SOURCE_AUDIO_ACTIVE")
    return {
        "pass": not blockers,
        "blockers": blockers,
        "voiceDynamics": round(dynamics, 2),
        "selectedTake": manifest.get("selectedTake"),
        "selectedDuration": manifest.get("selectedDuration"),
    }


def validate_audio(video: Path) -> dict[str, Any]:
    evidence = analyze_audio(video)
    blockers: list[str] = []
    if evidence.get("audioPresent") is not True:
        blockers.append("AUDIO_MISSING")
    technical = _number(evidence.get("technicalAudioScore"))
    if technical < AUDIO_LIMITS["technicalAudioScore"]:
        blockers.append("AUDIO_TECHNICAL_SCORE_LOW")
    lufs = evidence.get("measuredLufs")
    if not isinstance(lufs, (int, float)):
        blockers.append("AUDIO_LUFS_EVIDENCE_MISSING")
    elif not AUDIO_LIMITS["lufsMin"] <= float(lufs) <= AUDIO_LIMITS["lufsMax"]:
        blockers.append("AUDIO_LUFS_OUTSIDE_CAMP_RANGE")
    peak = evidence.get("measuredTruePeakDb")
    if not isinstance(peak, (int, float)):
        blockers.append("AUDIO_TRUE_PEAK_EVIDENCE_MISSING")
    elif float(peak) > AUDIO_LIMITS["truePeakMaxDb"]:
        blockers.append("AUDIO_TRUE_PEAK_TOO_HIGH")
    if _number(evidence.get("clipRatio")) > AUDIO_LIMITS["clipRatioMax"]:
        blockers.append("AUDIO_CLIPPING")
    return {"pass": not blockers, "blockers": blockers, **evidence}


def validate_rights(rights: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    assets = rights.get("assets") if isinstance(rights, dict) else None
    if assets is None:
        approved = rights.get("rightsApproved") if isinstance(rights, dict) else None
        rejected = rights.get("rightsRejected") if isinstance(rights, dict) else None
        if approved is None and rejected is None:
            blockers.append("RIGHTS_EVIDENCE_MISSING")
        elif int(rejected or 0) > 0:
            blockers.append("RIGHTS_REJECTED_ASSET_PRESENT")
    elif isinstance(assets, list):
        if not assets:
            blockers.append("RIGHTS_USED_ASSET_LIST_EMPTY")
        for item in assets:
            if not isinstance(item, dict) or item.get("used") is False:
                continue
            if item.get("rightsApproved") is not True:
                blockers.append("RIGHTS_UNAPPROVED_USED_ASSET")
                break
    return {"pass": not blockers, "blockers": blockers}


def validate_visual(visual: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if visual.get("evidenceComplete") is not True:
        blockers.append("VISUAL_EVIDENCE_INCOMPLETE")
    if not isinstance(visual.get("thirdPartyWatermarkDetected"), bool):
        blockers.append("WATERMARK_EVIDENCE_MISSING")
    elif visual.get("thirdPartyWatermarkDetected") is True:
        blockers.append("THIRD_PARTY_WATERMARK")
    if not isinstance(visual.get("duplicateBrandDetected"), bool):
        blockers.append("DUPLICATE_BRAND_EVIDENCE_MISSING")
    elif visual.get("duplicateBrandDetected") is True:
        blockers.append("BRAND_DUPLICATED")
    if visual.get("brandPresent") is not True:
        blockers.append("BRAND_MISSING")
    if visual.get("websiteRequired") is True and visual.get("realWebsiteCapture") is not True:
        blockers.append("WEBSITE_CAPTURE_NOT_REAL")
    if visual.get("visualStagnationRisk") is True:
        blockers.append("VISUAL_STAGNATION_RISK")
    max_unchanged = _number(visual.get("maxUnchangedSeconds"), 0.0)
    if max_unchanged and max_unchanged > 2.5:
        blockers.append("VISUAL_STAGNATION")
    role_counts = visual.get("shotRoleCounts") if isinstance(visual.get("shotRoleCounts"), dict) else {}
    if role_counts:
        if int(role_counts.get("hero") or 0) < 1:
            blockers.append("SHOT_ROLE_HERO_MISSING")
        if int(role_counts.get("closeup") or 0) + int(role_counts.get("detail") or 0) < 1:
            blockers.append("SHOT_ROLE_CLOSEUP_OR_DETAIL_MISSING")
    else:
        blockers.append("SHOT_ROLE_EVIDENCE_MISSING")
    return {"pass": not blockers, "blockers": blockers}


def validate_critic(critic: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if critic.get("criticComplete") is not True:
        return {"pass": False, "blockers": ["CRITIC_INCOMPLETE"], "floors": CRITIC_FLOORS}
    for metric, floor in CRITIC_FLOORS.items():
        if _number(critic.get(metric)) < floor:
            blockers.append(f"CRITIC_{metric.upper()}_BELOW_CAMP_FLOOR")
    if critic.get("publishReady") is not True:
        blockers.append("PUBLISH_NOT_READY")
    return {"pass": not blockers, "blockers": blockers, "floors": CRITIC_FLOORS}


def release_gate(
    *,
    video: Path,
    brief: dict[str, Any],
    renderer: dict[str, Any],
    voice: dict[str, Any],
    critic: dict[str, Any],
    rights: dict[str, Any],
    visual: dict[str, Any],
    perceptual: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = {
        "technical": validate_technical(video, _number(brief.get("durationSeconds"), 20.0)),
        "renderer": validate_renderer(renderer),
        "voice": validate_voice(voice),
        "audio": validate_audio(video),
        "rights": validate_rights(rights),
        "visual": validate_visual(visual),
        "perceptual": evaluate_perceptual_quality(perceptual or {}),
        "critic": validate_critic(critic),
    }
    blockers: list[str] = []
    for check in checks.values():
        for blocker in check.get("blockers", []):
            if blocker not in blockers:
                blockers.append(blocker)
    return {
        "package": PACKAGE,
        "version": VERSION,
        "authority": AUTHORITY,
        "releaseReady": not blockers,
        "gatePass": not blockers,
        "blockers": blockers,
        "checks": checks,
        "brief": brief,
        "repairPolicy": {"maxPasses": 2, "onExhausted": "CAMP_REQUIRES_HUMAN_CREATIVE_REVIEW"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CAMP 13.2 hard release gate for Karyab Mashin cinematic advertisements")
    parser.add_argument("--video", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--renderer", required=True)
    parser.add_argument("--voice", required=True)
    parser.add_argument("--critic", required=True)
    parser.add_argument("--rights", required=True)
    parser.add_argument("--visual", required=True)
    parser.add_argument("--perceptual", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = release_gate(
        video=Path(args.video).expanduser().resolve(),
        brief=_read_json(Path(args.brief), {}),
        renderer=_read_json(Path(args.renderer), {}),
        voice=_read_json(Path(args.voice), {}),
        critic=_read_json(Path(args.critic), {}),
        rights=_read_json(Path(args.rights), {}),
        visual=_read_json(Path(args.visual), {}),
        perceptual=_read_json(Path(args.perceptual), {}),
    )
    _write_json(Path(args.output).expanduser().resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["gatePass"] else 73


if __name__ == "__main__":
    raise SystemExit(main())
