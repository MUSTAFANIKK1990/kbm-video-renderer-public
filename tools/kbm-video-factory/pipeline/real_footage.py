#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from audio_lanes import mix_audio_lanes, parse_sfx
from captions import convert
from creative_audio import generate_from_plan as generate_creative_audio
from creative_plan import build_plan as build_creative_plan
from ingest import duration_seconds, ingest, probe
from rough_cut import process as rough_cut_process
from visual_quality import process as visual_smart_cut_process
from voiceover_adapter import GATEWAY_URL_ENV, synthesize_avalai_gateway, synthesize_piper

PACKAGE = "KBM-VIDEO-FACTORY-CLOUDFLARE-CONTAINER-ANDROID-RUNNER-07"

TEMPLATES = {
    "KBM-V01-INFOGRAPHIC",
    "KBM-V02-PRESENTER-UI",
    "KBM-V03-MACHINE-REVIEW",
    "KBM-V04-MOTION-POSTER",
    "KBM-V05-TECHNICAL-VFX",
    "KBM-V06-STORY-REVEAL",
}


def safe_job_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    if not cleaned:
        raise ValueError("Job id must contain at least one ASCII letter, number, _ or -")
    return cleaned[:80]


def newest_transcript(directory: Path, preferred_stem: str) -> Path:
    preferred = directory / f"{preferred_stem}.json"
    if preferred.exists():
        return preferred
    candidates = [path for path in directory.glob("*.json") if path.name != "adapter-report.json"]
    if not candidates:
        raise RuntimeError("WhisperX did not produce a JSON transcript")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("RUN:", " ".join(command))
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Real footage -> Package 03 rough cut/audio cleanup -> Package 04 visual smart cut -> "
            "Package 05 creative overlays/voiceover/music/SFX -> normalize -> WhisperX -> Remotion reel"
        )
    )
    parser.add_argument("--input", required=True, help="Raw camera or reference footage")
    parser.add_argument("--title", default="")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--cta", default="")
    parser.add_argument("--template", default="KBM-V03-MACHINE-REVIEW", choices=sorted(TEMPLATES))
    parser.add_argument("--job", default="kbm-real-footage")
    parser.add_argument("--fit", choices=["auto", "cover", "contain", "blurred-bg"], default="auto")
    parser.add_argument("--max-seconds", type=float, default=60.0)
    parser.add_argument("--transcript", default=None, help="Use an existing WhisperX JSON instead of running WhisperX")
    parser.add_argument("--skip-transcribe", action="store_true")

    parser.add_argument("--skip-rough-cut", action="store_true")
    parser.add_argument("--scene-threshold", type=float, default=0.32)
    parser.add_argument("--silence-db", type=float, default=-40.0)
    parser.add_argument("--min-silence", type=float, default=0.55)
    parser.add_argument("--silence-padding", type=float, default=0.12)
    parser.add_argument("--scene-snap", type=float, default=0.35)
    parser.add_argument("--no-audio-cleanup", action="store_true")

    parser.add_argument("--skip-visual-smart-cut", action="store_true")
    parser.add_argument("--visual-sample-fps", type=float, default=2.0)
    parser.add_argument("--visual-window", type=float, default=2.5)
    parser.add_argument("--visual-scene-threshold", type=float, default=0.22)
    parser.add_argument("--visual-target-ratio", type=float, default=0.65)
    parser.add_argument("--visual-target-seconds", type=float, default=None)
    parser.add_argument("--visual-min-score", type=float, default=0.35)
    parser.add_argument("--visual-min-clip", type=float, default=1.2)

    parser.add_argument("--creative-preset", default=None, help="Creative preset id from config/creative-presets.json")
    parser.add_argument("--creative-audio", choices=["generated", "off"], default="generated")
    parser.add_argument("--voiceover-script", default=None, help="Override or supply voiceover script text")
    parser.add_argument("--voiceover-audio", default=None, help="Use an existing narration audio file")
    parser.add_argument(
        "--avalai-gateway-url",
        default=None,
        help=f"AvalAI Gateway base URL or /v1/tts endpoint; defaults to {GATEWAY_URL_ENV}",
    )
    parser.add_argument("--avalai-voice", default="alloy", help="Gateway voice id; default: alloy")
    parser.add_argument("--avalai-timeout", type=float, default=120.0)
    parser.add_argument("--avalai-attempts", type=int, default=2)
    parser.add_argument("--piper-model", default=None, help="Optional user-supplied Piper model for TTS")
    parser.add_argument("--piper-config", default=None, help="Optional Piper model config")
    parser.add_argument("--voiceover-volume", type=float, default=1.0)
    parser.add_argument("--source-duck-volume", type=float, default=0.22)

    parser.add_argument("--music", default=None, help="Optional licensed background music file; overrides generated bed")
    parser.add_argument("--music-volume", type=float, default=0.12)
    parser.add_argument(
        "--sfx",
        action="append",
        default=[],
        help="Optional SFX lane: PATH@SECONDS or PATH@SECONDS@VOLUME; repeatable",
    )
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--no-render", action="store_true", help="Prepare media/props only")
    parser.add_argument("--output", default=None, help="Final MP4 path")
    args = parser.parse_args()

    if args.template not in TEMPLATES:
        print(f"Unknown template: {args.template}", file=sys.stderr)
        return 2

    try:
        job = safe_job_id(args.job)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        print(f"Input not found: {source}", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    workdir = root / "work" / job
    public_job = root / "public" / "generated" / job
    out_path = Path(args.output).expanduser().resolve() if args.output else root / "out" / f"{job}.mp4"
    workdir.mkdir(parents=True, exist_ok=True)
    public_job.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    effective_source = source
    rough_cut_report: dict[str, Any] | None = None
    rough_cut_status = "disabled" if args.skip_rough_cut else "pending"

    if not args.skip_rough_cut:
        rough_cut_media = workdir / "rough-cut.mp4"
        rough_cut_report_path = workdir / "rough-cut-report.json"
        try:
            rough_cut_report = rough_cut_process(
                source,
                rough_cut_media,
                rough_cut_report_path,
                scene_threshold=max(0.01, min(0.99, args.scene_threshold)),
                silence_db=min(-1.0, args.silence_db),
                min_silence=max(0.1, args.min_silence),
                silence_padding=max(0.0, args.silence_padding),
                scene_snap=max(0.0, args.scene_snap),
                audio_cleanup=not args.no_audio_cleanup,
            )
            effective_source = rough_cut_media
            rough_cut_status = "generated"
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Rough-cut stage failed: {exc}", file=sys.stderr)
            return 3

    visual_smart_cut_report: dict[str, Any] | None = None
    visual_smart_cut_status = "disabled" if args.skip_visual_smart_cut else "pending"
    if not args.skip_visual_smart_cut:
        visual_media = workdir / "visual-smart-cut.mp4"
        visual_report_path = workdir / "visual-smart-cut-report.json"
        try:
            visual_smart_cut_report = visual_smart_cut_process(
                effective_source,
                visual_media,
                visual_report_path,
                sample_fps=max(0.5, min(6.0, args.visual_sample_fps)),
                window=max(1.2, min(8.0, args.visual_window)),
                scene_threshold=max(0.01, min(0.99, args.visual_scene_threshold)),
                target_ratio=max(0.15, min(1.0, args.visual_target_ratio)),
                target_seconds=max(0.5, args.visual_target_seconds) if args.visual_target_seconds else None,
                min_score=max(0.0, min(1.0, args.visual_min_score)),
                min_clip=max(0.5, min(4.0, args.visual_min_clip)),
            )
            effective_source = visual_media
            visual_smart_cut_status = "generated"
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Visual smart-cut stage failed: {exc}", file=sys.stderr)
            return 4

    creative_plan: dict[str, Any] | None = None
    creative_plan_status = "disabled"
    creative_audio_report: dict[str, Any] | None = None
    creative_audio_status = "disabled"
    generated_music: Path | None = None
    generated_sfx = []

    if args.creative_preset:
        try:
            edited_duration = duration_seconds(probe(effective_source))
            creative_plan = build_creative_plan(
                args.creative_preset,
                duration_seconds=edited_duration,
                fps=30,
            )
            creative_plan_path = workdir / "creative-plan.json"
            creative_plan_path.write_text(json.dumps(creative_plan, ensure_ascii=False, indent=2), encoding="utf-8")
            creative_plan_status = "generated"

            if args.creative_audio == "generated":
                creative_audio_report = generate_creative_audio(creative_plan, workdir / "creative-audio")
                creative_audio_status = "generated"
                generated_music = Path(str(creative_audio_report["music"])).resolve()
                for cue in creative_audio_report.get("sfx", []) or []:
                    generated_sfx.append(
                        parse_sfx(f"{cue['path']}@{cue['atSeconds']}@{cue['volume']}")
                    )
        except (RuntimeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            print(f"Creative plan/audio stage failed: {exc}", file=sys.stderr)
            return 5

    voiceover_script = args.voiceover_script or (
        str(creative_plan.get("voiceoverScript") or "") if creative_plan else ""
    )
    voiceover_path: Path | None = None
    voiceover_status = "disabled"
    voiceover_report: dict[str, Any] | None = None
    gateway_url = args.avalai_gateway_url or os.environ.get(GATEWAY_URL_ENV, "")

    if args.voiceover_audio:
        voiceover_path = Path(args.voiceover_audio).expanduser().resolve()
        if not voiceover_path.exists():
            print(f"Voiceover audio not found: {voiceover_path}", file=sys.stderr)
            return 6
        voiceover_status = "provided"
    elif gateway_url:
        if not voiceover_script.strip():
            print("AvalAI Gateway TTS requested but voiceover script is empty", file=sys.stderr)
            return 6
        try:
            voiceover_path = workdir / "voiceover.mp3"
            voiceover_report = synthesize_avalai_gateway(
                voiceover_script,
                voiceover_path,
                gateway_url=gateway_url,
                voice=args.avalai_voice,
                timeout_seconds=args.avalai_timeout,
                attempts=args.avalai_attempts,
            )
            voiceover_status = "generated"
        except RuntimeError as gateway_exc:
            if not args.piper_model:
                print(f"Voiceover stage failed: {gateway_exc}", file=sys.stderr)
                return 6
            print(f"AvalAI Gateway failed; falling back to Piper: {gateway_exc}", file=sys.stderr)
            try:
                voiceover_path = workdir / "voiceover.wav"
                piper_report = synthesize_piper(
                    voiceover_script,
                    voiceover_path,
                    model=Path(args.piper_model),
                    config=Path(args.piper_config) if args.piper_config else None,
                )
                voiceover_report = {
                    "engine": "piper",
                    "fallbackFrom": "avalai-gateway",
                    "fallbackReason": str(gateway_exc),
                    "result": piper_report,
                }
                voiceover_status = "generated-fallback"
            except (RuntimeError, subprocess.CalledProcessError) as piper_exc:
                print(f"Voiceover fallback failed: {piper_exc}", file=sys.stderr)
                return 6
        (workdir / "voiceover-report.json").write_text(
            json.dumps(voiceover_report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    elif args.piper_model:
        if not voiceover_script.strip():
            print("Piper TTS requested but voiceover script is empty", file=sys.stderr)
            return 6
        try:
            voiceover_path = workdir / "voiceover.wav"
            voiceover_report = synthesize_piper(
                voiceover_script,
                voiceover_path,
                model=Path(args.piper_model),
                config=Path(args.piper_config) if args.piper_config else None,
            )
            (workdir / "voiceover-report.json").write_text(
                json.dumps(voiceover_report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            voiceover_status = "generated"
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Voiceover stage failed: {exc}", file=sys.stderr)
            return 6
    elif voiceover_script.strip():
        voiceover_status = "script-only"

    audio_lanes_report: dict[str, Any] | None = None
    audio_lanes_status = "disabled"
    selected_music = Path(args.music).expanduser().resolve() if args.music else generated_music
    selected_sfx = list(generated_sfx)
    try:
        selected_sfx.extend(parse_sfx(value) for value in args.sfx)
    except (ValueError, RuntimeError) as exc:
        print(f"SFX configuration failed: {exc}", file=sys.stderr)
        return 7

    if selected_music or selected_sfx or voiceover_path:
        audio_lanes_media = workdir / "audio-lanes.mp4"
        audio_lanes_report_path = workdir / "audio-lanes-report.json"
        try:
            audio_lanes_report = mix_audio_lanes(
                effective_source,
                audio_lanes_media,
                audio_lanes_report_path,
                music=selected_music,
                music_volume=args.music_volume,
                sfx=selected_sfx,
                voiceover=voiceover_path,
                voiceover_volume=args.voiceover_volume,
                source_duck_volume=args.source_duck_volume,
            )
            effective_source = audio_lanes_media
            audio_lanes_status = "generated"
        except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"Audio-lanes stage failed: {exc}", file=sys.stderr)
            return 7

    normalized = public_job / "media.mp4"
    media_meta_path = workdir / "media.json"

    try:
        media_meta = ingest(
            effective_source,
            normalized,
            media_meta_path,
            fps=30,
            fit=args.fit,
            max_seconds=max(0.0, min(60.0, args.max_seconds)),
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Real-footage ingest failed: {exc}", file=sys.stderr)
        return 8

    transcript_path: Path | None = None
    captions: list[dict[str, Any]] = []
    transcript_status = "disabled"

    if args.transcript:
        transcript_path = Path(args.transcript).expanduser().resolve()
        if not transcript_path.exists():
            print(f"Transcript not found: {transcript_path}", file=sys.stderr)
            return 9
        transcript_status = "provided"
    elif not args.skip_transcribe and bool(media_meta.get("audioPresent")):
        transcript_dir = workdir / "whisperx"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        adapter = Path(__file__).with_name("whisperx_adapter.py")
        try:
            run(
                [
                    sys.executable,
                    str(adapter),
                    "--input",
                    str(normalized),
                    "--output-dir",
                    str(transcript_dir),
                    "--language",
                    "fa",
                ]
            )
            transcript_path = newest_transcript(transcript_dir, normalized.stem)
            transcript_status = "generated"
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"WhisperX stage failed: {exc}", file=sys.stderr)
            return 10
    elif not media_meta.get("audioPresent"):
        transcript_status = "no-audio"

    if transcript_path:
        transcript_data = json.loads(transcript_path.read_text(encoding="utf-8"))
        captions = convert(transcript_data, fps=30, max_words=5, max_chars=42, gap_seconds=0.65)

    captions_path = workdir / "captions.json"
    captions_path.write_text(json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8")

    duration_frames = int(media_meta.get("durationInFrames") or 1)
    resolved_title = args.title or (str(creative_plan.get("title") or "") if creative_plan else "کاریاب ماشین")
    resolved_subtitle = args.subtitle or (str(creative_plan.get("subtitle") or "") if creative_plan else "")
    resolved_cta = args.cta or (str(creative_plan.get("cta") or "") if creative_plan else "مشاهده در کاریاب ماشین")
    props = {
        "templateId": args.template,
        "title": resolved_title,
        "subtitle": resolved_subtitle or None,
        "cta": resolved_cta,
        "media": f"generated/{job}/media.mp4",
        "captions": captions,
        "overlays": creative_plan.get("overlays", []) if creative_plan else [],
        "muted": bool(args.mute) or not bool(media_meta.get("audioPresent")),
        "volume": 1.0,
        "durationInFrames": duration_frames,
        "introFrames": min(150, max(75, duration_frames // 5)),
    }
    props_path = workdir / "render-props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "package": PACKAGE,
        "job": job,
        "source": str(source),
        "effectiveSource": str(effective_source),
        "roughCutStatus": rough_cut_status,
        "roughCut": rough_cut_report,
        "visualSmartCutStatus": visual_smart_cut_status,
        "visualSmartCut": visual_smart_cut_report,
        "creativePlanStatus": creative_plan_status,
        "creativePlan": creative_plan,
        "creativeAudioStatus": creative_audio_status,
        "creativeAudio": creative_audio_report,
        "voiceoverStatus": voiceover_status,
        "voiceoverScript": voiceover_script or None,
        "voiceover": voiceover_report or (str(voiceover_path) if voiceover_path else None),
        "audioLanesStatus": audio_lanes_status,
        "audioLanes": audio_lanes_report,
        "normalizedMedia": str(normalized),
        "media": media_meta,
        "transcriptStatus": transcript_status,
        "transcript": str(transcript_path) if transcript_path else None,
        "captionCount": len(captions),
        "props": str(props_path),
        "output": str(out_path),
        "rendered": False,
    }

    if not args.no_render:
        node = shutil.which("node")
        if not node:
            print("Missing executable on PATH: node", file=sys.stderr)
            return 11
        render_script = root / "scripts" / "render.mjs"
        try:
            run(
                [
                    node,
                    str(render_script),
                    "--template",
                    args.template,
                    "--input",
                    str(props_path),
                    "--out",
                    str(out_path),
                    "--duration-frames",
                    str(duration_frames),
                ],
                cwd=root,
            )
            report["rendered"] = True
        except subprocess.CalledProcessError as exc:
            report["renderError"] = str(exc)
            (workdir / "job-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return 12

    report_path = workdir / "job-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
