#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from ingest import audio_present, duration_seconds, probe, require

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    print("RUN:", " ".join(command))
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def ffmpeg_fallback(source: Path, output: Path, *, max_seconds: float | None = None) -> dict[str, Any]:
    data = probe(source)
    duration = duration_seconds(data)
    if duration <= 0:
        raise RuntimeError("FFmpeg fallback source has invalid duration")
    if max_seconds and max_seconds > 0:
        duration = min(duration, max_seconds)
    ffmpeg = require("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-y", "-i", str(source), "-t", f"{duration:.3f}", "-map", "0:v:0"]
    if audio_present(data):
        command += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "192k"]
    else:
        command += ["-an"]
    command += [
        "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(output),
    ]
    _run(command)
    return {"renderer": "ffmpeg", "fallback": True, "output": str(output), "releaseEligible": False}


def render(
    *,
    root: Path,
    source: Path,
    props_path: Path,
    template: str,
    output: Path,
    duration_frames: int,
    allow_remotion: bool = True,
    require_remotion: bool = False,
) -> tuple[dict[str, Any], str | None]:
    remotion_error: str | None = None
    if allow_remotion:
        node = shutil.which("node")
        render_script = root / "scripts" / "render.mjs"
        if node and render_script.is_file():
            try:
                _run([
                    node,
                    str(render_script),
                    "--template", template,
                    "--input", str(props_path),
                    "--out", str(output),
                    "--duration-frames", str(duration_frames),
                ], cwd=root)
                return {"renderer": "remotion", "fallback": False, "output": str(output), "releaseEligible": True}, None
            except subprocess.CalledProcessError as exc:
                remotion_error = f"Remotion exited with code {exc.returncode}"
        else:
            remotion_error = "Node or Remotion render script is unavailable"

    if require_remotion:
        raise RuntimeError(f"CAMP_REMOTION_RENDER_REQUIRED: {remotion_error or 'Remotion render unavailable'}")

    report = ffmpeg_fallback(source, output, max_seconds=duration_frames / 30.0)
    return report, remotion_error
