#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import wave
from pathlib import Path
from typing import Any

from avalai_creative_intelligence import critique_final, enabled
from avalai_voice_director import direct_voice
from ingest import duration_seconds, probe
from render_router import render as render_with_fallback

CANDIDATE = "13.1.2-rc.7"
AUTHORITY = "PEP-V41-RC7-CINEMATIC-WEBSITE-20S-AUTHORITY"
PACKAGE = "KBM-VIDEO-FACTORY-CUPAI-LIVE-CREATIVE-HARDENING-13.1.1"
VERSION = "13.1.1"
SOURCE_EXPECTED_CANDIDATE = "13.1.2-rc.6"
THRESHOLD_DEFAULT = 8.0
TARGET_SECONDS = 20.0
TARGET_FRAMES = 600
DEFAULT_LOGO_URL = "https://karyabmashin.ir/wp-content/plugins/kbm-visual-assets/assets/media/kbm-visual-system-v3/ipui25/brand/kbm-logo-transparent.png"
NARRATION_SCRIPT = "ماشینت آماده‌ست... اما هنوز اجاره نرفته؟ از آگهی‌های بی‌نتیجه خسته شدی؟ وقتشه بهتر دیده بشی. وارد کاریاب ماشین شو، آگهی ماشینت رو ثبت کن و مستقیم‌تر به متقاضی برس. شروع کن؛ KARYABMASHIN.IR."


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


def _audio_stream_count(path: Path) -> int:
    try:
        data = probe(path)
    except Exception:
        return 0
    streams = data.get("streams") if isinstance(data, dict) else []
    return sum(1 for item in streams or [] if isinstance(item, dict) and item.get("codec_type") == "audio")


def _video_duration(path: Path) -> float:
    try:
        return float(duration_seconds(probe(path)))
    except Exception:
        return 0.0


def _write_pcm(path: Path, samples: list[float], sample_rate: int = 48000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        payload = bytearray()
        for sample in samples:
            value = int(max(-1.0, min(1.0, sample)) * 32767)
            payload += int(value).to_bytes(2, byteorder="little", signed=True)
        handle.writeframes(bytes(payload))


def _generate_sfx(public_dir: Path) -> None:
    sr = 48000
    impact: list[float] = []
    for i in range(int(sr * 0.72)):
        t = i / sr
        env = math.exp(-5.3 * t)
        sample = (math.sin(2 * math.pi * 72 * t) * 0.74 + math.sin(2 * math.pi * 121 * t) * 0.22) * env
        impact.append(sample)
    _write_pcm(public_dir / "rc7-impact.wav", impact, sr)

    rng = random.Random(1317)
    whoosh: list[float] = []
    total = int(sr * 0.55)
    for i in range(total):
        p = i / max(1, total - 1)
        env = math.sin(math.pi * p) ** 1.7
        carrier = math.sin(2 * math.pi * (180 + 520 * p) * (i / sr)) * 0.18
        noise = (rng.random() * 2 - 1) * 0.35
        whoosh.append((carrier + noise) * env)
    _write_pcm(public_dir / "rc7-whoosh.wav", whoosh, sr)

    click: list[float] = []
    for i in range(int(sr * 0.16)):
        t = i / sr
        env = math.exp(-26 * t)
        click.append((math.sin(2 * math.pi * 980 * t) * 0.55 + math.sin(2 * math.pi * 1540 * t) * 0.18) * env)
    _write_pcm(public_dir / "rc7-click.wav", click, sr)


def _build_props(*, source_sha: str, website_sha: str, logo_url: str, narration_url: str, source_critic: dict[str, Any]) -> dict[str, Any]:
    return {
        "templateId": "KBM-V03-MACHINE-REVIEW",
        "title": "کاریاب ماشین",
        "subtitle": "ماشینت را سریع‌تر در بازار تخصصی دیده کن",
        "cta": "همین حالا آگهی ماشینت را در KARYABMASHIN.IR ثبت کن.",
        "accent": "#F4B400",
        "background": "#071827",
        "media": "rc7-source.mp4",
        "narration": narration_url,
        "narrationVolume": 1,
        "assets": [
            {
                "id": "website-walkthrough",
                "kind": "video",
                "src": "rc7-website.mp4",
                "provider": "karyabmashin-live-site",
                "sourceUrl": "https://karyabmashin.ir/",
                "license": "first-party-site-capture",
            }
        ],
        "captionPolicy": "single-lane",
        "brand": {
            "logoSrc": logo_url,
            "requireLogo": True,
            "watermark": True,
            "logoReveal": False,
            "endCard": True,
            "site": "KARYABMASHIN.IR",
            "name": "کاریاب ماشین",
            "persistentBug": False,
            "endCardRequired": True,
            "prominence": "strong",
        },
        "criticPolish": {
            "enabled": True,
            "mode": "website-20s",
            "sourceVideoSha256": source_sha,
            "sourceCriticOverall": float(source_critic.get("overall") or 0),
            "authority": AUTHORITY,
        },
        "editorial": {
            "package": PACKAGE,
            "version": VERSION,
            "cupaiCritic": source_critic,
            "repairPass": 4,
            "repairAuthority": AUTHORITY,
            "maxUnchangedSeconds": 2.35,
        },
        "soundDesign": {
            "targetLufs": -14,
            "truePeakDb": -1.0,
            "voicePriority": True,
            "cues": [
                {"atSeconds": 0.0, "kind": "impact", "gainDb": -11},
                {"atSeconds": 2.3, "kind": "whoosh", "gainDb": -16},
                {"atSeconds": 7.2, "kind": "whoosh", "gainDb": -14},
                {"atSeconds": 7.6, "kind": "browser-click", "gainDb": -15},
                {"atSeconds": 16.35, "kind": "cta-impact", "gainDb": -13},
            ],
        },
        "muted": True,
        "volume": 0,
        "durationInFrames": TARGET_FRAMES,
        "rc7": {
            "websiteVideoSha256": website_sha,
            "websiteCapture": True,
            "websitePublicPages": ["https://karyabmashin.ir/", "https://karyabmashin.ir/ads/"],
            "sourceAudioMuted": True,
            "legacyCornerBadgeMasked": True,
            "cinematicEffects": ["controlled-push-in", "kinetic-caption", "brand-masthead", "light-sweep-transition", "browser-frame", "click-pulse", "impact-sfx", "whoosh-sfx", "clean-end-card"],
        },
    }


def _blockers(critic: dict[str, Any], output: Path, threshold: float, *, voice_manifest: dict[str, Any], audio_streams: int, website_duration: float) -> list[str]:
    blockers: list[str] = []
    if not output.is_file():
        blockers.append("OUTPUT_MISSING")
    duration = _video_duration(output)
    if not (19.90 <= duration <= 20.20):
        blockers.append("DURATION_NOT_20S")
    if not (8.7 <= website_duration <= 9.3):
        blockers.append("WEBSITE_WALKTHROUGH_DURATION_INVALID")
    if voice_manifest.get("complete") is not True or voice_manifest.get("durationFit") is not True:
        blockers.append("DYNAMIC_NARRATION_NOT_READY")
    if int(voice_manifest.get("takeCount") or 0) != 1:
        blockers.append("NARRATION_TRACK_COUNT_MISMATCH")
    if audio_streams != 1:
        blockers.append("OUTPUT_AUDIO_STREAM_COUNT_MISMATCH")
    if critic.get("criticComplete") is not True:
        blockers.append("CRITIC_INCOMPLETE")
        return blockers
    overall = float(critic.get("overall") or 0)
    if overall < threshold:
        blockers.append("CRITIC_BELOW_THRESHOLD")
    if critic.get("publishReady") is not True:
        blockers.append("CRITIC_NOT_PUBLISH_READY")
    if float(critic.get("captionReadability") or 0) < 7.7:
        blockers.append("CAPTION_READABILITY_BELOW_RC7_FLOOR")
    if float(critic.get("ctaStrength") or 0) < 7.8:
        blockers.append("CTA_BELOW_RC7_FLOOR")
    if float(critic.get("brandVisibility") or 0) < 7.8:
        blockers.append("BRAND_BELOW_RC7_FLOOR")
    if float(critic.get("hook") or 0) < 7.8:
        blockers.append("HOOK_BELOW_RC7_FLOOR")
    if float(critic.get("audioEnergy") or 0) < 7.8:
        blockers.append("AUDIO_ENERGY_BELOW_RC7_FLOOR")
    return blockers


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the rc7 20-second cinematic Karyab Mashin conversion reel with a real first-party website walkthrough and dynamic single-voice narration.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--website", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--candidate", default=CANDIDATE)
    parser.add_argument("--source-run-id", default=os.environ.get("SOURCE_RUN_ID", ""))
    parser.add_argument("--source-artifact-id", default=os.environ.get("SOURCE_ARTIFACT_ID", ""))
    parser.add_argument("--source-artifact-digest", default=os.environ.get("SOURCE_ARTIFACT_DIGEST", ""))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    video = Path(args.video).expanduser().resolve()
    website = Path(args.website).expanduser().resolve()
    work = Path(args.work).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    report_path = work / "package13-1-report.json"
    report = _read_json(report_path, {})
    source_critic = _read_json(work / "package13-1-cupai-critic-rc6.json", {})
    if not source_critic:
        source_critic = _read_json(work / "package13-1-cupai-critic.json", {})

    if not isinstance(report, dict) or not report:
        raise SystemExit("Package 13.1.1 rc6 report is missing")
    if report.get("package") != PACKAGE or report.get("version") != VERSION or report.get("pipelineMode") != "v41":
        raise SystemExit("Source report is not the Package 13.1.1 v41 contract")
    if report.get("candidate") != SOURCE_EXPECTED_CANDIDATE or report.get("gatePass") is not True:
        raise SystemExit("A release-ready rc6 source is required before rc7")
    if not isinstance(source_critic, dict) or source_critic.get("criticComplete") is not True or source_critic.get("publishReady") is not True:
        raise SystemExit("A complete publish-ready rc6 critic is required before rc7")
    if not video.is_file() or not website.is_file():
        raise SystemExit("rc6 source MP4 and real website walkthrough MP4 are required")
    if not enabled():
        raise SystemExit("CupAI critic is not configured for rc7")

    source_sha = _sha256(video)
    website_sha = _sha256(website)
    website_duration = _video_duration(website)
    if website_duration <= 0:
        raise SystemExit("Website walkthrough is not decodable")

    public_dir = root / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    public_source = public_dir / "rc7-source.mp4"
    public_website = public_dir / "rc7-website.mp4"
    shutil.copy2(video, public_source)
    shutil.copy2(website, public_website)
    if _sha256(public_source) != source_sha or _sha256(public_website) != website_sha:
        raise SystemExit("rc7 public media copy failed hash verification")
    _generate_sfx(public_dir)

    narration_voice = os.environ.get("KBM_RC7_NARRATION_VOICE", "onyx").strip() or "onyx"
    voice_manifest = direct_voice(NARRATION_SCRIPT, work, voice=narration_voice, max_seconds=20.0, maximum=False)
    narration_path = Path(str(voice_manifest.get("selectedPath") or ""))
    if voice_manifest.get("complete") is not True or voice_manifest.get("durationFit") is not True or not narration_path.is_file():
        evidence = {
            "candidate": args.candidate,
            "authority": AUTHORITY,
            "releaseReady": False,
            "blockers": ["DYNAMIC_NARRATION_NOT_READY"],
            "voiceManifest": voice_manifest,
        }
        _write_json(work / "package13-1-rc7-evidence.json", evidence)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 65

    public_narration = public_dir / "rc7-narration.mp3"
    shutil.copy2(narration_path, public_narration)
    logo_url = os.environ.get("KBM_RC7_BRAND_LOGO_URL", "").strip() or DEFAULT_LOGO_URL
    props = _build_props(source_sha=source_sha, website_sha=website_sha, logo_url=logo_url, narration_url="rc7-narration.mp3", source_critic=source_critic)
    props_path = work / "package13-1-rc7-render-props.json"
    _write_json(props_path, props)

    renderer, render_error = render_with_fallback(
        root=root,
        source=video,
        props_path=props_path,
        template="KBM-V03-MACHINE-REVIEW",
        output=output,
        duration_frames=TARGET_FRAMES,
        allow_remotion=True,
    )
    if renderer.get("fallback") is True or not output.is_file():
        evidence = {
            "candidate": args.candidate,
            "authority": AUTHORITY,
            "releaseReady": False,
            "blockers": ["RC7_REMOTION_RENDER_NOT_EXECUTED"],
            "renderError": render_error,
            "renderer": renderer,
        }
        _write_json(work / "package13-1-rc7-evidence.json", evidence)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 64

    output_sha = _sha256(output)
    audio_streams = _audio_stream_count(output)
    critic = critique_final(output, work)
    _write_json(work / "package13-1-cupai-critic-rc7.json", critic)
    _write_json(work / "package13-1-cupai-critic.json", critic)
    threshold = float(os.environ.get("KBM_PACKAGE131_CRITIC_THRESHOLD", str(THRESHOLD_DEFAULT)) or THRESHOLD_DEFAULT)
    blockers = _blockers(critic, output, threshold, voice_manifest=voice_manifest, audio_streams=audio_streams, website_duration=website_duration)
    release_ready = not blockers

    source_overall = float(source_critic.get("overall") or 0)
    states = report.get("states") if isinstance(report.get("states"), list) else []
    states.append({
        "stage": "cinematic-website-conversion-20s-rc7",
        "state": "PASS" if release_ready else "BLOCKED",
        "authority": AUTHORITY,
        "sourceOverall": source_overall,
        "finalOverall": critic.get("overall"),
        "scoreDelta": round(float(critic.get("overall") or 0) - source_overall, 2),
        "renderExecuted": True,
        "renderMode": "20s-cinematic-first-party-website",
        "websiteCapture": True,
        "sourceAudioMuted": True,
        "narrationTrackCount": 1,
        "outputAudioStreamCount": audio_streams,
        "blockers": blockers,
    })

    if isinstance(report.get("campaign"), dict):
        report["campaign"]["voiceoverScript"] = NARRATION_SCRIPT
        report["campaign"]["cta"] = "همین حالا آگهی ماشینت را در KARYABMASHIN.IR ثبت کن."
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
        "targetSeconds": TARGET_SECONDS,
        "websiteCapture": True,
        "websiteVideoSha256": website_sha,
        "sourceVideoSha256": source_sha,
        "outputVideoSha256": output_sha,
        "sourceAudioMuted": True,
        "narrationTrackCount": 1,
        "outputAudioStreamCount": audio_streams,
        "legacyCornerBadgeMasked": True,
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
        "sourceVideoSha256": source_sha,
        "websiteVideoSha256": website_sha,
        "outputVideoSha256": output_sha,
        "videoChanged": output_sha != source_sha,
        "targetSeconds": TARGET_SECONDS,
        "outputDurationSeconds": round(_video_duration(output), 3),
        "websiteWalkthroughDurationSeconds": round(website_duration, 3),
        "websiteCapture": True,
        "websitePages": ["https://karyabmashin.ir/", "https://karyabmashin.ir/ads/"],
        "legacyCornerBadgeMasked": True,
        "sourceAudioMuted": True,
        "dynamicNarration": True,
        "narrationVoice": narration_voice,
        "narrationTrackCount": 1,
        "narrationDuration": voice_manifest.get("selectedDuration"),
        "narrationDurationFit": voice_manifest.get("durationFit") is True,
        "outputAudioStreamCount": audio_streams,
        "brandLogoSource": logo_url,
        "brandLogoAuthority": "user-confirmed-site-logo",
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
    _write_json(work / "package13-1-rc7-evidence.json", evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if release_ready else 63


if __name__ == "__main__":
    raise SystemExit(main())
