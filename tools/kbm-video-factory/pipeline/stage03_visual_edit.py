#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

PACKAGE = "KBM-VIDEO-FACTORY-66377-STAGE03-VISUAL-EDIT-SYNC-01"


def require(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Missing executable: {name}")
    return path


def probe(path: Path) -> dict[str, Any]:
    ffprobe = require("ffprobe")
    out = subprocess.check_output([
        ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ], text=True)
    return json.loads(out)


def duration(data: dict[str, Any]) -> float:
    return float((data.get("format") or {}).get("duration") or 0.0)


def has_audio(data: dict[str, Any]) -> bool:
    return any(s.get("codec_type") == "audio" for s in data.get("streams", []))


def fps_value(stream: dict[str, Any]) -> float:
    value = str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1")
    a, b = value.split("/", 1)
    return float(a) / float(b or 1)


def effect_filter(name: str) -> str:
    if name == "punch-zoom":
        return "zoompan=z='min(1.0+0.0035*on,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30"
    if name == "push":
        return "scale=1188:2112,crop=1080:1920:54:96"
    if name == "slow-push":
        return "zoompan=z='min(1.0+0.0012*on,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30"
    return "null"


def build(config: dict[str, Any], source: Path, voice: Path, output: Path, report_path: Path) -> dict[str, Any]:
    ffmpeg = require("ffmpeg")
    source_meta = probe(source)
    voice_meta = probe(voice)
    source_duration = duration(source_meta)
    voice_duration = duration(voice_meta)
    source_audio = has_audio(source_meta)

    target = config["target"]
    fps = int(target.get("fps", 30))
    width = int(target.get("width", 1080))
    height = int(target.get("height", 1920))
    target_duration = float(target["durationSeconds"])
    source_volume = float(target.get("sourceAudioVolume", 0.16))
    voice_volume = float(target.get("voiceVolume", 1.0))

    shots = config.get("shots") or []
    if not shots:
        raise RuntimeError("No shots configured")

    latest_source = max(float(seg["to"]) for shot in shots for seg in shot.get("segments", []))
    if source_duration + 0.05 < latest_source:
        raise RuntimeError(f"Source too short: {source_duration:.3f}s < required {latest_source:.3f}s")
    if abs(voice_duration - target_duration) > 1.0:
        raise RuntimeError(f"Voice duration {voice_duration:.3f}s is too far from target {target_duration:.3f}s")

    filters: list[str] = []
    final_video_labels: list[str] = []
    final_audio_labels: list[str] = []
    shot_report: list[dict[str, Any]] = []
    cut_times: list[float] = []
    timeline_cursor = 0.0

    for si, shot in enumerate(shots):
        segment_v: list[str] = []
        segment_a: list[str] = []
        computed = 0.0
        for pi, seg in enumerate(shot.get("segments") or []):
            start = float(seg["from"])
            end = float(seg["to"])
            speed = float(seg.get("speed", 1.0))
            if end <= start or speed <= 0:
                raise RuntimeError(f"Invalid segment in {shot.get('id')}")
            computed += (end - start) / speed
            vlabel = f"v{si}_{pi}"
            base = (
                f"[0:v]trim=start={start:.6f}:end={end:.6f},"
                f"setpts=(PTS-STARTPTS)/{speed:.8f},"
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1,fps={fps}"
            )
            filters.append(base + f"[{vlabel}]")
            segment_v.append(f"[{vlabel}]")
            if source_audio:
                alabel = f"a{si}_{pi}"
                filters.append(
                    f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS,"
                    f"atempo={speed:.8f}[{alabel}]"
                )
                segment_a.append(f"[{alabel}]")

        raw_v = f"sv{si}"
        if len(segment_v) == 1:
            filters.append(f"{segment_v[0]}null[{raw_v}]")
        else:
            filters.append("".join(segment_v) + f"concat=n={len(segment_v)}:v=1:a=0[{raw_v}]")

        freeze = float(shot.get("freezeTailSeconds", 0.0) or 0.0)
        shot_duration = computed + freeze
        effected_v = f"ev{si}"
        effect = str(shot.get("effect") or "clean")
        vf = effect_filter(effect)
        if freeze > 0:
            filters.append(f"[{raw_v}]{vf},tpad=stop_mode=clone:stop_duration={freeze:.6f},trim=duration={shot_duration:.6f}[{effected_v}]")
        else:
            filters.append(f"[{raw_v}]{vf},trim=duration={shot_duration:.6f}[{effected_v}]")
        final_video_labels.append(f"[{effected_v}]")

        if source_audio:
            raw_a = f"sa{si}"
            if len(segment_a) == 1:
                filters.append(f"{segment_a[0]}anull[{raw_a}]")
            else:
                filters.append("".join(segment_a) + f"concat=n={len(segment_a)}:v=0:a=1[{raw_a}]")
            final_a = f"ea{si}"
            if freeze > 0:
                filters.append(f"[{raw_a}]apad=pad_dur={freeze:.6f},atrim=duration={shot_duration:.6f}[{final_a}]")
            else:
                filters.append(f"[{raw_a}]atrim=duration={shot_duration:.6f}[{final_a}]")
            final_audio_labels.append(f"[{final_a}]")

        start_out = timeline_cursor
        timeline_cursor += shot_duration
        if si:
            cut_times.append(round(start_out, 3))
        shot_report.append({
            "id": shot.get("id"),
            "purpose": shot.get("purpose"),
            "effect": effect,
            "fromOutputSeconds": round(start_out, 3),
            "toOutputSeconds": round(timeline_cursor, 3),
            "durationSeconds": round(shot_duration, 3),
            "freezeTailSeconds": round(freeze, 3),
            "segments": shot.get("segments") or [],
        })

    visual_label = "vcat"
    filters.append("".join(final_video_labels) + f"concat=n={len(shots)}:v=1:a=0[{visual_label}]")

    if source_audio:
        source_cat = "acat"
        filters.append("".join(final_audio_labels) + f"concat=n={len(shots)}:v=0:a=1[{source_cat}]")
        filters.append(f"[{source_cat}]volume={source_volume:.4f}[sourcequiet]")
    filters.append(
        f"[1:a]atrim=start=0:end={target_duration:.6f},asetpts=PTS-STARTPTS,"
        f"volume={voice_volume:.4f}[voice]"
    )
    if source_audio:
        filters.append("[sourcequiet][voice]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95[aout]")
    else:
        filters.append("[voice]alimiter=limit=0.95[aout]")

    filters.append(f"[{visual_label}]trim=duration={target_duration:.6f},setpts=PTS-STARTPTS[vout]")

    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-i", str(voice),
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]",
        "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest", str(output)
    ]
    subprocess.run(cmd, check=True)

    out_meta = probe(output)
    video_stream = next(s for s in out_meta["streams"] if s.get("codec_type") == "video")
    report = {
        "package": PACKAGE,
        "version": config.get("version"),
        "source": str(source),
        "voice": str(voice),
        "output": str(output),
        "targetDurationSeconds": target_duration,
        "plannedDurationSeconds": round(timeline_cursor, 3),
        "voiceDurationSeconds": round(voice_duration, 3),
        "outputDurationSeconds": round(duration(out_meta), 3),
        "syncDeltaSeconds": round(abs(duration(out_meta) - voice_duration), 3),
        "jumpCutTimesSeconds": cut_times,
        "shots": shot_report,
        "outputVideo": {
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "codec": video_stream.get("codec_name"),
            "pixFmt": video_stream.get("pix_fmt"),
            "fps": round(fps_value(video_stream), 3),
        },
        "sourceAudioMixed": source_audio,
        "sourceAudioVolume": source_volume if source_audio else 0,
        "voiceVolume": voice_volume,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="KBM 66377 Stage 03 deterministic visual edit + voice sync")
    parser.add_argument("--input", required=True)
    parser.add_argument("--voice", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    report = build(
        config,
        Path(args.input).expanduser().resolve(),
        Path(args.voice).expanduser().resolve(),
        Path(args.output).expanduser().resolve(),
        Path(args.report).expanduser().resolve(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
