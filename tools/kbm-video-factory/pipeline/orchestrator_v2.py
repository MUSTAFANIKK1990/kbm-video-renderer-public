#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from audio_lanes import mix_audio_lanes, parse_sfx
from caption_aligner import align_script
from captions import convert
from persian_asr_quality import transcribe_media, write_pronunciation_review
from creative_audio import generate_from_plan as generate_creative_audio
from creative_director import build_brief
from effect_router import build_effect_plan
from fallback_policy import PACKAGE, VERSION, StageState, failed_state, fallback_state, pass_state, warning_state
from ingest import audio_present, duration_seconds, probe
from input_normalizer import normalize_input, validate_video
from quality_control import inspect_output
from render_router import render as render_with_fallback
from rough_cut import process as rough_cut_process
from shot_composer import compose_shots
from timeline_planner import build_timeline
from visual_quality import process as visual_smart_cut_process
from voiceover_adapter import GATEWAY_URL_ENV, synthesize_avalai_gateway, synthesize_piper

TEMPLATES = {
    "KBM-V01-INFOGRAPHIC",
    "KBM-V02-PRESENTER-UI",
    "KBM-V03-MACHINE-REVIEW",
    "KBM-V04-MOTION-POSTER",
    "KBM-V05-TECHNICAL-VFX",
    "KBM-V06-STORY-REVEAL",
}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _error(exc: BaseException) -> str:
    return str(exc)[-1000:]


def _newest_transcript(directory: Path, preferred_stem: str) -> Path:
    preferred = directory / f"{preferred_stem}.json"
    if preferred.exists():
        return preferred
    candidates = [path for path in directory.glob("*.json") if path.name != "adapter-report.json"]
    if not candidates:
        raise RuntimeError("WhisperX did not produce a JSON transcript")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _run(command: list[str]) -> None:
    print("RUN:", " ".join(command))
    subprocess.run(command, check=True)


def _extend_caption_tail(captions: list[dict[str, Any]], duration_seconds: float, fps: int = 30) -> list[dict[str, Any]]:
    if not captions or duration_seconds <= 0:
        return captions
    output = [dict(item) for item in captions]
    target_frame = max(int(round(duration_seconds * fps)), int(output[-1].get("to") or 0) + 1)
    output[-1]["to"] = target_frame
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="KBM Package 09 smart non-blocking raw-footage editor")
    parser.add_argument("--input", required=True)
    parser.add_argument("--creative-preset", default=None)
    parser.add_argument("--template", default="KBM-V03-MACHINE-REVIEW", choices=sorted(TEMPLATES))
    parser.add_argument("--title", default="")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--cta", default="")
    parser.add_argument("--job", default="kbm-smart-editor")
    parser.add_argument("--fit", choices=["auto", "cover", "contain", "blurred-bg"], default="auto")
    parser.add_argument("--max-seconds", type=float, default=60.0)
    parser.add_argument("--voiceover-script", default=None)
    parser.add_argument("--voiceover-audio", default=None)
    parser.add_argument("--avalai-gateway-url", default=None)
    parser.add_argument("--avalai-voice", default="alloy")
    parser.add_argument("--avalai-timeout", type=float, default=120.0)
    parser.add_argument("--avalai-attempts", type=int, default=2)
    parser.add_argument("--piper-model", default=None)
    parser.add_argument("--piper-config", default=None)
    parser.add_argument("--music", default=None)
    parser.add_argument("--music-volume", type=float, default=0.12)
    parser.add_argument("--source-duck-volume", type=float, default=0.22)
    parser.add_argument("--skip-rough-cut", action="store_true")
    parser.add_argument("--skip-visual-smart-cut", action="store_true")
    parser.add_argument("--skip-shot-composer", action="store_true")
    parser.add_argument("--skip-transcribe", action="store_true")
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.template not in TEMPLATES:
        print(f"Unknown template: {args.template}", file=sys.stderr)
        return 2

    source = Path(args.input).expanduser().resolve()
    root = Path(__file__).resolve().parents[1]
    job = "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in args.job).strip("-")[:80] or "kbm-smart-editor"
    workdir = root / "work" / job
    public_job = root / "public" / "generated" / job
    output = Path(args.output).expanduser().resolve() if args.output else root / "out" / f"{job}.mp4"
    workdir.mkdir(parents=True, exist_ok=True)
    public_job.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    states: list[StageState] = []
    report: dict[str, Any] = {
        "package": PACKAGE,
        "version": VERSION,
        "job": job,
        "source": str(source),
        "states": [],
        "rendered": False,
    }

    try:
        source_validation = validate_video(source)
        states.append(pass_state("input-video-stream", details=source_validation))
    except Exception as exc:
        states.append(failed_state("input-video-stream", _error(exc)))
        report["states"] = [item.as_dict() for item in states]
        _write(workdir / "job-report.json", report)
        return 2

    normalized = workdir / "normalized.mp4"
    normalized_report = workdir / "normalized-media.json"
    try:
        media_meta = normalize_input(source, normalized, normalized_report, fit=args.fit, fps=30, max_seconds=max(0.1, min(90.0, args.max_seconds)))
        states.append(pass_state("normalize", details={"fit": media_meta.get("fitMode")}))
    except Exception as exc:
        states.append(failed_state("input-decode", _error(exc)))
        report["states"] = [item.as_dict() for item in states]
        _write(workdir / "job-report.json", report)
        return 3

    effective = normalized

    if args.skip_rough_cut:
        states.append(warning_state("rough-cut", "Stage disabled by request"))
    else:
        try:
            rough_media = workdir / "rough-cut.mp4"
            rough_report = rough_cut_process(effective, rough_media, workdir / "rough-cut-report.json", scene_threshold=0.32, silence_db=-40.0, min_silence=0.55, silence_padding=0.12, scene_snap=0.35, audio_cleanup=True)
            effective = rough_media
            states.append(pass_state("rough-cut", details={"removedSeconds": rough_report.get("removedSeconds")}))
        except Exception as exc:
            states.append(fallback_state("rough-cut", _error(exc), "normalized-video"))

    if args.skip_visual_smart_cut:
        states.append(warning_state("visual-smart-cut", "Stage disabled by request"))
    else:
        try:
            visual_media = workdir / "visual-smart-cut.mp4"
            visual_report = visual_smart_cut_process(effective, visual_media, workdir / "visual-smart-cut-report.json", sample_fps=2.0, window=2.5, scene_threshold=0.22, target_ratio=0.65, target_seconds=None, min_score=0.35, min_clip=1.2)
            effective = visual_media
            states.append(pass_state("visual-smart-cut", details={"selectedSeconds": visual_report.get("selectedSeconds")}))
        except Exception as exc:
            states.append(fallback_state("visual-smart-cut", _error(exc), "previous-video"))

    edited_duration = duration_seconds(probe(effective))
    brief, brief_fallback, brief_reason = build_brief(args.creative_preset, duration_seconds=edited_duration, fps=30, title=args.title)
    if args.voiceover_script:
        brief["voiceoverScript"] = args.voiceover_script
    _write(workdir / "creative-brief.json", brief)
    if brief_fallback:
        states.append(fallback_state("creative-director", brief_reason or "Preset fallback", "package09-safe-default"))
    else:
        states.append(pass_state("creative-director", details={"preset": brief.get("presetId")}))

    timeline = build_timeline(brief, duration_seconds=edited_duration, fps=30)
    _write(workdir / "timeline.json", timeline)
    states.append(pass_state("timeline-planner", details={"scenes": len(timeline.get("segments", []))}))

    if args.skip_shot_composer:
        states.append(warning_state("shot-composer", "Stage disabled by request"))
    else:
        try:
            shot_media = workdir / "shot-composed.mp4"
            shot_report = compose_shots(effective, shot_media, workdir / "shot-plan.json")
            effective = shot_media
            edited_duration = duration_seconds(probe(effective))
            states.append(pass_state("shot-composer", details={"shotCount": shot_report.get("shotCount")}))
        except Exception as exc:
            states.append(fallback_state("shot-composer", _error(exc), "previous-video"))

    effect_plan = build_effect_plan(timeline)
    _write(workdir / "effect-plan.json", effect_plan)
    states.append(pass_state("effect-router", details={"cues": len(effect_plan.get("cues", []))}))

    voiceover_script = str(brief.get("voiceoverScript") or "").strip()
    voiceover_path: Path | None = None
    voiceover_report: dict[str, Any] | None = None
    if args.voiceover_audio:
        candidate = Path(args.voiceover_audio).expanduser().resolve()
        if candidate.is_file():
            voiceover_path = candidate
            states.append(pass_state("voiceover", details={"engine": "provided"}))
        else:
            states.append(fallback_state("voiceover", "Provided voiceover file not found", "script-only"))
    else:
        gateway_url = args.avalai_gateway_url or os.environ.get(GATEWAY_URL_ENV, "")
        if gateway_url and voiceover_script:
            try:
                voiceover_path = workdir / "voiceover.mp3"
                voiceover_report = synthesize_avalai_gateway(voiceover_script, voiceover_path, gateway_url=gateway_url, voice=args.avalai_voice, timeout_seconds=args.avalai_timeout, attempts=max(1, args.avalai_attempts))
                states.append(pass_state("voiceover", details={"engine": "avalai-gateway"}))
            except Exception as gateway_exc:
                if args.piper_model:
                    try:
                        voiceover_path = workdir / "voiceover.wav"
                        voiceover_report = synthesize_piper(voiceover_script, voiceover_path, model=Path(args.piper_model).expanduser().resolve(), config=Path(args.piper_config).expanduser().resolve() if args.piper_config else None)
                        states.append(fallback_state("voiceover", _error(gateway_exc), "piper", details={"engine": "piper"}))
                    except Exception as piper_exc:
                        voiceover_path = None
                        states.append(fallback_state("voiceover", f"Gateway: {_error(gateway_exc)} | Piper: {_error(piper_exc)}", "script-only"))
                else:
                    states.append(fallback_state("voiceover", _error(gateway_exc), "script-only"))
        elif voiceover_script:
            states.append(fallback_state("voiceover", "No TTS provider configured", "script-only"))
        else:
            states.append(warning_state("voiceover", "No narration script"))

    if voiceover_report is not None:
        _write(workdir / "voice-report.json", voiceover_report)

    generated_music: Path | None = None
    generated_sfx = []
    try:
        creative_audio_report = generate_creative_audio(brief, workdir / "creative-audio")
        generated_music = Path(str(creative_audio_report["music"])).resolve()
        for cue in creative_audio_report.get("sfx", []) or []:
            try:
                generated_sfx.append(parse_sfx(f"{cue['path']}@{cue['atSeconds']}@{cue['volume']}"))
            except Exception as cue_exc:
                states.append(warning_state("creative-audio", f"Skipped one SFX cue: {_error(cue_exc)}"))
        states.append(pass_state("creative-audio", details={"sfx": len(generated_sfx)}))
    except Exception as exc:
        states.append(fallback_state("creative-audio", _error(exc), "no-generated-music-or-sfx"))

    selected_music = Path(args.music).expanduser().resolve() if args.music else generated_music
    if selected_music and not selected_music.exists():
        states.append(warning_state("audio-mix", "Selected music file is missing; continuing without it"))
        selected_music = None

    try:
        if selected_music or generated_sfx or voiceover_path:
            mixed = workdir / "audio-mix.mp4"
            audio_report = mix_audio_lanes(effective, mixed, workdir / "audio-report.json", music=selected_music, music_volume=max(0.0, min(1.0, args.music_volume)), sfx=generated_sfx, voiceover=voiceover_path, voiceover_volume=1.0, source_duck_volume=max(0.0, min(1.0, args.source_duck_volume)))
            effective = mixed
            states.append(pass_state("audio-mix", details={"audioPresent": audio_report.get("audioPresent")}))
        else:
            states.append(warning_state("audio-mix", "No additional audio lanes; using source audio state"))
    except Exception as exc:
        states.append(fallback_state("audio-mix", _error(exc), "unmixed-video"))

    captions: list[dict[str, Any]] = []
    strict_persian_asr = os.environ.get("KBM_PERSIAN_QUALITY_GATE", "").strip() == "1"
    caption_duration = duration_seconds(probe(voiceover_path)) if voiceover_path else duration_seconds(probe(effective))
    if strict_persian_asr:
        try:
            if args.skip_transcribe:
                raise RuntimeError("Strict Persian quality mode forbids --skip-transcribe")
            if not voiceover_script or not voiceover_path:
                raise RuntimeError("Strict Persian quality mode requires a script and rendered voice file")
            voice_asr = transcribe_media(
                voiceover_path,
                workdir / "package13-1-voice-asr.json",
                output_dir=workdir / "package13-1-voice-whisperx",
            )
            voice_pronunciation = write_pronunciation_review(
                workdir / "package13-1-pronunciation-review.json",
                voiceover_script,
                voice_asr,
            )
            if voice_pronunciation.get("pass") is not True:
                raise RuntimeError("Persian pronunciation lexicon review failed")
            captions = convert(voice_asr, fps=30, max_words=5, max_chars=42, gap_seconds=0.65)
            captions = _extend_caption_tail(captions, caption_duration + 0.5, fps=30)
            if not captions or not all(
                isinstance(item.get("words"), list) and item.get("words")
                for item in captions
            ):
                raise RuntimeError("Strict Persian captions have no word-level timing")
            states.append(pass_state(
                "persian-voice-asr",
                details={"source": "rendered-voice", "count": len(captions)},
            ))
        except Exception as exc:
            states.append(failed_state("persian-voice-asr", _error(exc)))
            report.update({"states": [item.as_dict() for item in states], "rendered": False})
            _write(workdir / "job-report.json", report)
            return 8
    elif voiceover_script:
        try:
            captions = align_script(voiceover_script, duration_seconds=caption_duration, fps=30)
            states.append(pass_state("caption-aligner", details={"source": "script", "count": len(captions)}))
        except Exception as exc:
            states.append(fallback_state("caption-aligner", _error(exc), "whisperx-or-empty"))

    if not strict_persian_asr and not captions and not args.skip_transcribe and audio_present(probe(effective)):
        transcript_dir = workdir / "whisperx"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        try:
            adapter = Path(__file__).with_name("whisperx_adapter.py")
            _run([sys.executable, str(adapter), "--input", str(effective), "--output-dir", str(transcript_dir), "--language", "fa"])
            transcript_path = _newest_transcript(transcript_dir, effective.stem)
            transcript_data = json.loads(transcript_path.read_text(encoding="utf-8"))
            captions = convert(transcript_data, fps=30, max_words=5, max_chars=42, gap_seconds=0.65)
            states.append(pass_state("whisperx", details={"count": len(captions)}))
        except Exception as exc:
            states.append(fallback_state("whisperx", _error(exc), "no-captions"))
    elif not strict_persian_asr and not captions and args.skip_transcribe:
        states.append(warning_state("whisperx", "Stage disabled by request"))

    _write(workdir / "captions.json", captions)

    public_media = public_job / "media.mp4"
    shutil.copy2(effective, public_media)
    media_data = probe(public_media)
    duration = duration_seconds(media_data)
    duration_frames = max(1, min(2700, int(round(duration * 30))))
    props = {
        "templateId": args.template,
        "title": args.title or str(brief.get("title") or "کاریاب ماشین"),
        "subtitle": args.subtitle or str(brief.get("subtitle") or "") or None,
        "cta": args.cta or str(brief.get("cta") or "مشاهده در کاریاب ماشین"),
        "media": f"generated/{job}/media.mp4",
        "captions": captions,
        "overlays": brief.get("overlays", []),
        "muted": bool(args.mute) or not audio_present(media_data),
        "volume": 1.0,
        "durationInFrames": duration_frames,
        "introFrames": min(150, max(60, duration_frames // 5)),
    }
    if strict_persian_asr:
        props["captionAuthority"] = {
            "authority": "KBM-PERSIAN-ASR-PRONUNCIATION-AUTHORITY-01",
            "source": "whisperx-rendered-voice",
            "evidence": "package13-1-voice-asr.json",
            "wordTiming": True,
            "syntheticAlignment": False,
        }
    props_path = workdir / "render-props.json"
    _write(props_path, props)

    if args.no_render:
        states.append(warning_state("render", "Render disabled by request"))
        report.update({"effectiveSource": str(effective), "creativeBrief": str(workdir / "creative-brief.json"), "timeline": str(workdir / "timeline.json"), "effectPlan": str(workdir / "effect-plan.json"), "captions": str(workdir / "captions.json"), "props": str(props_path), "output": str(output), "states": [item.as_dict() for item in states]})
        _write(workdir / "job-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    try:
        render_report, remotion_error = render_with_fallback(root=root, source=effective, props_path=props_path, template=args.template, output=output, duration_frames=duration_frames, allow_remotion=True)
        if render_report.get("fallback"):
            states.append(fallback_state("remotion-render", remotion_error or "Remotion unavailable", "ffmpeg-renderer"))
        else:
            states.append(pass_state("remotion-render", details={"renderer": "remotion"}))
        report["rendered"] = True
        report["renderer"] = render_report
    except Exception as exc:
        states.append(failed_state("render-all", _error(exc)))
        report["states"] = [item.as_dict() for item in states]
        _write(workdir / "job-report.json", report)
        return 12

    try:
        qc = inspect_output(output)
        _write(workdir / "qc-report.json", qc)
        if qc["pass"]:
            states.append(pass_state("quality-control"))
        else:
            states.append(warning_state("quality-control", "Output is playable but one or more target checks differ", details={"warnings": qc["warnings"]}))
        report["qc"] = qc
    except Exception as exc:
        states.append(failed_state("render-all", f"QC could not validate output: {_error(exc)}"))
        report["states"] = [item.as_dict() for item in states]
        _write(workdir / "job-report.json", report)
        return 13

    report.update({"effectiveSource": str(effective), "creativeBrief": str(workdir / "creative-brief.json"), "timeline": str(workdir / "timeline.json"), "effectPlan": str(workdir / "effect-plan.json"), "captions": str(workdir / "captions.json"), "props": str(props_path), "output": str(output), "states": [item.as_dict() for item in states]})
    _write(workdir / "job-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
