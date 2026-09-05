#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any


def require(binary: str) -> str:
    resolved = shutil.which(binary)
    if not resolved:
        raise RuntimeError(f"Missing executable on PATH: {binary}")
    return resolved


def probe(path: Path) -> dict[str, Any]:
    ffprobe = require("ffprobe")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def video_stream(data: dict[str, Any]) -> dict[str, Any]:
    for stream in data.get("streams", []) or []:
        if stream.get("codec_type") == "video":
            return stream
    raise RuntimeError("Input does not contain a video stream")


def audio_present(data: dict[str, Any]) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in data.get("streams", []) or [])


def duration_seconds(data: dict[str, Any]) -> float:
    raw = (data.get("format") or {}).get("duration")
    if raw is None:
        return 0.0
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return 0.0


def choose_fit(width: int, height: int, requested: str) -> str:
    if requested != "auto":
        return requested
    if width <= 0 or height <= 0:
        return "cover"
    aspect = width / height
    return "cover" if aspect <= 0.8 else "blurred-bg"


def filter_args(fit: str) -> tuple[list[str], list[str]]:
    if fit == "contain":
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=#0B1F33,setsar=1"
        )
        return ["-vf", vf], ["-map", "0:v:0"]

    if fit == "blurred-bg":
        complex_filter = (
            "[0:v]split=2[bgsrc][fgsrc];"
            "[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=24:4[bg];"
            "[fgsrc]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
        )
        return ["-filter_complex", complex_filter], ["-map", "[v]"]

    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    return ["-vf", vf], ["-map", "0:v:0"]


def ingest(
    source: Path,
    output: Path,
    metadata_path: Path,
    *,
    fps: int = 30,
    fit: str = "auto",
    max_seconds: float = 60.0,
) -> dict[str, Any]:
    ffmpeg = require("ffmpeg")
    source_probe = probe(source)
    stream = video_stream(source_probe)
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    selected_fit = choose_fit(width, height, fit)
    source_duration = duration_seconds(source_probe)
    target_duration = source_duration
    if max_seconds > 0 and source_duration > 0:
        target_duration = min(source_duration, max_seconds)

    filters, video_map = filter_args(selected_fit)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    command = [ffmpeg, "-y", "-i", str(source)]
    if target_duration > 0:
        command += ["-t", f"{target_duration:.3f}"]
    command += filters
    command += video_map
    command += ["-map", "0:a?", "-r", str(fps)]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output),
    ]

    print("RUN:", " ".join(command))
    subprocess.run(command, check=True)

    normalized_probe = probe(output)
    normalized_duration = duration_seconds(normalized_probe)
    duration_frames = max(1, min(1800, int(math.ceil(normalized_duration * fps))))
    result = {
        "source": str(source),
        "output": str(output),
        "fitMode": selected_fit,
        "fps": fps,
        "durationSeconds": normalized_duration,
        "durationInFrames": duration_frames,
        "audioPresent": audio_present(source_probe),
        "sourceVideo": {
            "codec": stream.get("codec_name"),
            "width": width,
            "height": height,
            "frameRate": stream.get("r_frame_rate"),
            "durationSeconds": source_duration,
        },
    }
    metadata_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize real footage for KBM vertical reels")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--fit", choices=["auto", "cover", "contain", "blurred-bg"], default="auto")
    parser.add_argument("--max-seconds", type=float, default=60.0)
    args = parser.parse_args()

    try:
        result = ingest(
            Path(args.input).expanduser().resolve(),
            Path(args.output).expanduser().resolve(),
            Path(args.metadata).expanduser().resolve(),
            fps=max(1, args.fps),
            fit=args.fit,
            max_seconds=max(0.0, args.max_seconds),
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"INGEST FAILED: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
