#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from avalai_creative_intelligence import critique_final, enabled
from avalai_voice_director import direct_voice
from ingest import duration_seconds, probe
from render_router import render as render_with_fallback

CANDIDATE = "13.1.2-rc.6"
AUTHORITY = "PEP-V41-RC6-SINGLE-VOICE-BRAND-TIMING-CTA-AUTHORITY"
PACKAGE = "KBM-VIDEO-FACTORY-CUPAI-LIVE-CREATIVE-HARDENING-13.1.1"
VERSION = "13.1.1"
THRESHOLD_DEFAULT = 8.0
SOURCE_EXPECTED_CANDIDATE = "13.1.2-rc.5"
DEFAULT_LOGO_URL = "https://karyabmashin.ir/wp-content/plugins/kbm-visual-assets/assets/media/kbm-visual-system-v3/ipui25/brand/kbm-logo-transparent.png"
NARRATION_SCRIPT = "دستگاه را بررسی کن؛ انتخاب بهتر در کاریاب ماشین."


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frames(seconds: float, fps: int = 30) -> int:
    return max(1, round(seconds * fps))


def _audio_stream_count(path: Path) -> int:
    try:
        data = probe(path)
    except Exception:
        return 0
    streams = data.get("streams") if isinstance(data, dict) else []
    return sum(1 for item in streams or [] if isinstance(item, dict) and item.get("codec_type") == "audio")


def _build_props(
    *,
    duration_frames: int,
    logo_url: str,
    narration_url: str,
    source_sha: str,
    source_critic: dict[str, Any],
) -> dict[str, Any]:
    fps = 30
    end_start = max(_frames(6.9, fps), duration_frames - _frames(3.0, fps))
    body_end = max(_frames(6.6, fps), end_start - 1)
    return {
        "templateId": "KBM-V03-MACHINE-REVIEW",
        "title": "کاریاب ماشین",
        "subtitle": "بررسی آگاهانه ماشین‌آلات",
        "cta": "ماشین‌آلات را در KARYABMASHIN.IR ببین و مقایسه کن.",
        "accent": "#F4B400",
        "background": "#0B1F33",
        "media": "rc6-source.mp4",
        "narration": narration_url,
        "narrationVolume": 1,
        "captions": [
            {"from": 0, "to": min(duration_frames - 1, _frames(2.0, fps)), "text": "قبل از اجاره یا معامله، دقیق ببین"},
            {"from": _frames(2.0, fps), "to": min(duration_frames - 1, _frames(4.25, fps)), "text": "وضعیت واقعی دستگاه را بررسی کن"},
            {"from": _frames(4.25, fps), "to": min(duration_frames - 1, _frames(6.45, fps)), "text": "بررسی فنی را قبل از تصمیم جدی بگیر"},
            {"from": _frames(6.45, fps), "to": min(duration_frames - 1, body_end), "text": "گزینه‌ها را در کاریاب ماشین ببین"},
        ],
        "captionPolicy": "single-lane",
        "captionProfile": {
            "fontSize": 56,
            "hookFontSize": 66,
            "minFontSize": 48,
            "maxFontSize": 72,
            "maxWords": 8,
            "maxLines": 2,
            "bottom": 360,
            "outlinePx": 5,
            "activeScale": 1.05,
            "pill": True,
            "accent": "#F4B400",
        },
        "brand": {
            "logoSrc": logo_url,
            "requireLogo": True,
            "watermark": True,
            "logoReveal": False,
            "endCard": True,
            "site": "KARYABMASHIN.IR",
            "name": "کاریاب ماشین",
            "persistentBug": True,
            "endCardRequired": True,
            "prominence": "strong",
        },
        "criticPolish": {
            "enabled": True,
            "closeupFromFrame": min(duration_frames - 2, _frames(4.15, fps)),
            "closeupToFrame": min(duration_frames - 1, _frames(5.85, fps)),
            "closeupScale": 1.18,
            "brandLeadInFromFrame": max(0, end_start - _frames(.55, fps)),
            "sourceVideoSha256": source_sha,
            "sourceCriticOverall": float(source_critic.get("overall") or 0),
            "authority": AUTHORITY,
        },
        "editorial": {
            "package": PACKAGE,
            "version": VERSION,
            "cupaiCritic": source_critic,
            "repairPass": 3,
            "repairAuthority": AUTHORITY,
        },
        "muted": True,
        "volume": 0,
        "durationInFrames": duration_frames,
    }


def _blockers(
    critic: dict[str, Any],
    output: Path,
    threshold: float,
    *,
    voice_manifest: dict[str, Any],
    output_audio_streams: int,
) -> list[str]:
    blockers: list[str] = []
    if not output.is_file():
        blockers.append("OUTPUT_MISSING")
    if voice_manifest.get("complete") is not True or voice_manifest.get("durationFit") is not True:
        blockers.append("SINGLE_NARRATION_NOT_READY")
    if int(voice_manifest.get("takeCount") or 0) != 1:
        blockers.append("NARRATION_TRACK_COUNT_MISMATCH")
    if output_audio_streams != 1:
        blockers.append("OUTPUT_AUDIO_STREAM_COUNT_MISMATCH")
    if critic.get("criticComplete") is not True:
        blockers.append("CRITIC_INCOMPLETE")
        return blockers
    overall = float(critic.get("overall") or 0)
    if overall < threshold:
        blockers.append("CRITIC_BELOW_THRESHOLD")
    if critic.get("publishReady") is not True:
        blockers.append("CRITIC_NOT_PUBLISH_READY")
    if float(critic.get("captionReadability") or 0) < 7.5:
        blockers.append("CAPTION_READABILITY_BELOW_RC6_FLOOR")
    if float(critic.get("ctaStrength") or 0) < 7.5:
        blockers.append("CTA_BELOW_RC6_FLOOR")
    if float(critic.get("brandVisibility") or 0) < 7.5:
        blockers.append("BRAND_BELOW_RC6_FLOOR")
    return blockers


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply one bounded rc.6 audio/brand/timing/CTA correction to an existing rc.5 final MP4, then rerun the final CupAI critic.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--candidate", default=CANDIDATE)
    parser.add_argument("--source-run-id", default=os.environ.get("SOURCE_RUN_ID", ""))
    parser.add_argument("--source-artifact-id", default=os.environ.get("SOURCE_ARTIFACT_ID", ""))
    parser.add_argument("--source-artifact-digest", default=os.environ.get("SOURCE_ARTIFACT_DIGEST", ""))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    video = Path(args.video).expanduser().resolve()
    work = Path(args.work).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    report_path = work / "package13-1-report.json"
    report = _read_json(report_path, {})
    source_critic = _read_json(work / "package13-1-cupai-critic.json", {})

    if not isinstance(report, dict) or not report:
        raise SystemExit("Package 13.1.1 report is missing")
    if report.get("package") != PACKAGE or report.get("version") != VERSION or report.get("pipelineMode") != "v41":
        raise SystemExit("Source report is not the Package 13.1.1 v41 contract")
    if not video.is_file():
        raise SystemExit("Source rc.5 MP4 is missing")
    if not isinstance(source_critic, dict) or source_critic.get("criticComplete") is not True:
        raise SystemExit("A complete rc.5 critic is required before rc.6 polish")

    threshold = float(os.environ.get("KBM_PACKAGE131_CRITIC_THRESHOLD", str(THRESHOLD_DEFAULT)) or THRESHOLD_DEFAULT)
    source_overall = float(source_critic.get("overall") or 0)
    if source_overall >= threshold and source_critic.get("publishReady") is True:
        raise SystemExit("Source is already release-ready; rc.6 polish is not required")
    if not enabled():
        raise SystemExit("CupAI critic is not configured for rc.6")

    before_sha = _sha256(video)
    data = probe(video)
    duration = float(duration_seconds(data))
    if duration <= 0:
        raise SystemExit("Source rc.5 MP4 has invalid duration")
    duration_frames = max(1, round(duration * 30))

    public_dir = root / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    public_source = public_dir / "rc6-source.mp4"
    shutil.copy2(video, public_source)
    if _sha256(public_source) != before_sha:
        raise SystemExit("rc.6 public source copy failed hash verification")

    narration_voice = os.environ.get("KBM_RC6_NARRATION_VOICE", "onyx").strip() or "onyx"
    voice_manifest = direct_voice(
        NARRATION_SCRIPT,
        work,
        voice=narration_voice,
        max_seconds=min(duration, 9.5),
        maximum=False,
    )
    narration_path = Path(str(voice_manifest.get("selectedPath") or ""))
    if voice_manifest.get("complete") is not True or voice_manifest.get("durationFit") is not True or not narration_path.is_file():
        evidence = {
            "candidate": args.candidate,
            "authority": AUTHORITY,
            "releaseReady": False,
            "blockers": ["SINGLE_NARRATION_NOT_READY"],
            "voiceManifest": voice_manifest,
            "sourceAudioMuted": True,
        }
        _write_json(work / "package13-1-rc6-polish-evidence.json", evidence)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 55

    public_narration = public_dir / "rc6-narration.mp3"
    shutil.copy2(narration_path, public_narration)
    if _sha256(public_narration) != _sha256(narration_path):
        raise SystemExit("rc.6 narration copy failed hash verification")

    logo_url = os.environ.get("KBM_RC6_BRAND_LOGO_URL", "").strip() or DEFAULT_LOGO_URL
    props = _build_props(
        duration_frames=duration_frames,
        logo_url=logo_url,
        narration_url="rc6-narration.mp3",
        source_sha=before_sha,
        source_critic=source_critic,
    )
    props_path = work / "package13-1-rc6-render-props.json"
    _write_json(props_path, props)

    renderer, render_error = render_with_fallback(
        root=root,
        source=video,
        props_path=props_path,
        template="KBM-V03-MACHINE-REVIEW",
        output=output,
        duration_frames=duration_frames,
        allow_remotion=True,
    )
    if renderer.get("fallback") is True:
        evidence = {
            "candidate": args.candidate,
            "authority": AUTHORITY,
            "releaseReady": False,
            "blockers": ["RC6_REMOTION_REPAIR_NOT_EXECUTED"],
            "renderError": render_error,
            "renderer": renderer,
            "sourceVideoSha256": before_sha,
            "sourceAudioMuted": True,
            "narrationTrackCount": 1,
        }
        _write_json(work / "package13-1-rc6-polish-evidence.json", evidence)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 54

    if not output.is_file():
        raise SystemExit("rc.6 polished MP4 was not created")

    output_sha = _sha256(output)
    output_audio_streams = _audio_stream_count(output)
    critic = critique_final(output, work)
    _write_json(work / "package13-1-cupai-critic-rc6.json", critic)
    blockers = _blockers(
        critic,
        output,
        threshold,
        voice_manifest=voice_manifest,
        output_audio_streams=output_audio_streams,
    )
    release_ready = not blockers

    states = report.get("states") if isinstance(report.get("states"), list) else []
    states.append({
        "stage": "single-voice-brand-timing-cta-rc6",
        "state": "PASS" if release_ready else "BLOCKED",
        "authority": AUTHORITY,
        "sourceOverall": source_overall,
        "finalOverall": critic.get("overall"),
        "scoreDelta": round(float(critic.get("overall") or 0) - source_overall, 2),
        "renderExecuted": True,
        "renderMode": "single-render-post-render-rebuild",
        "sourceAudioMuted": True,
        "narrationTrackCount": 1,
        "outputAudioStreamCount": output_audio_streams,
        "blockers": blockers,
    })

    if isinstance(report.get("campaign"), dict):
        report["campaign"]["voiceoverScript"] = NARRATION_SCRIPT
        report["campaign"]["cta"] = "ماشین‌آلات را در KARYABMASHIN.IR ببین و مقایسه کن."
    report["voiceDirector"] = voice_manifest
    report["candidate"] = args.candidate
    report["authority"] = AUTHORITY
    report["output"] = str(output)
    report["rendered"] = output.is_file()
    report["critic"] = critic
    report["brandReady"] = bool(logo_url)
    report["gatePass"] = release_ready
    report["releaseGateAuthority"] = AUTHORITY
    report["releaseGate"] = {
        "pass": release_ready,
        "blockers": blockers,
        "threshold": threshold,
        "visualOnlyPolish": False,
        "singleVoiceCorrection": True,
        "sourceAudioMuted": True,
        "narrationTrackCount": 1,
        "outputAudioStreamCount": output_audio_streams,
        "sourceVideoSha256": before_sha,
        "outputVideoSha256": output_sha,
    }
    report["states"] = states
    if isinstance(report.get("package13"), dict):
        report["package13"]["output"] = str(output)
    _write_json(report_path, report)

    evidence = {
        "candidate": args.candidate,
        "authority": AUTHORITY,
        "package": PACKAGE,
        "version": VERSION,
        "pipelineMode": "v41",
        "sourceCandidate": SOURCE_EXPECTED_CANDIDATE,
        "sourceRunId": str(args.source_run_id),
        "sourceArtifactId": str(args.source_artifact_id),
        "sourceArtifactDigest": str(args.source_artifact_digest),
        "sourceVideoSha256": before_sha,
        "outputVideoSha256": output_sha,
        "videoChanged": output_sha != before_sha,
        "visualOnlyPolish": False,
        "singleVoiceCorrection": True,
        "sourceAudioMuted": True,
        "narrationRegenerated": True,
        "narrationVoice": narration_voice,
        "narrationTrackCount": 1,
        "narrationDuration": voice_manifest.get("selectedDuration"),
        "narrationDurationFit": voice_manifest.get("durationFit") is True,
        "outputAudioStreamCount": output_audio_streams,
        "brandLogoSource": logo_url,
        "brandLogoAuthority": "user-confirmed-site-logo",
        "mediaResearchRepeated": False,
        "sourceCriticOverall": source_overall,
        "criticComplete": critic.get("criticComplete") is True,
        "criticOverall": critic.get("overall"),
        "criticPublishReady": critic.get("publishReady"),
        "scoreDelta": round(float(critic.get("overall") or 0) - source_overall, 2),
        "hook": critic.get("hook"),
        "shotVariety": critic.get("shotVariety"),
        "brandVisibility": critic.get("brandVisibility"),
        "captionReadability": critic.get("captionReadability"),
        "ctaStrength": critic.get("ctaStrength"),
        "audioEnergy": critic.get("audioEnergy"),
        "threshold": threshold,
        "releaseReady": release_ready,
        "blockers": blockers,
        "renderer": renderer,
        "renderError": render_error,
    }
    _write_json(work / "package13-1-rc6-polish-evidence.json", evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if release_ready else 53


if __name__ == "__main__":
    raise SystemExit(main())
