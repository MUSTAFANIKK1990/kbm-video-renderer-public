#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ingest import audio_present, duration_seconds, probe, require

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"


def _video_filter(index: int) -> str:
    mode = index % 6
    if mode == 0:
        return "scale=1080:1920,setsar=1"
    if mode == 1:
        return "scale=1188:2112,crop=1080:1920:54:96,setsar=1"
    if mode == 2:
        return "scale=1242:2208,crop=1080:1920:32:144,setsar=1"
    if mode == 3:
        return "scale=1242:2208,crop=1080:1920:130:144,setsar=1"
    if mode == 4:
        return "scale=1166:2073,crop=1080:1920:43:75,eq=contrast=1.04:saturation=1.06,setsar=1"
    return "scale=1080:1920,eq=contrast=1.03:saturation=1.04,setsar=1"


def compose_shots(source: Path, output: Path, report_path: Path, *, max_shots: int = 6) -> dict[str, Any]:
    data = probe(source)
    duration = duration_seconds(data)
    if duration <= 0:
        raise RuntimeError("Shot composer requires positive duration")
    has_audio = audio_present(data)
    shot_count = max(1, min(max_shots, int(duration // 1.2) or 1))
    shot_duration = duration / shot_count
    filters: list[str] = []
    concat_inputs: list[str] = []
    shots: list[dict[str, Any]] = []

    for index in range(shot_count):
        start = index * shot_duration
        end = duration if index == shot_count - 1 else (index + 1) * shot_duration
        filters.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,{_video_filter(index)}[v{index}]")
        if has_audio:
            filters.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{index}]")
            concat_inputs.append(f"[v{index}][a{index}]")
        else:
            concat_inputs.append(f"[v{index}]")
        shots.append({
            "id": f"shot-{index + 1:02d}",
            "fromSeconds": round(start, 3),
            "toSeconds": round(end, 3),
            "style": _video_filter(index),
        })

    if has_audio:
        filters.append(f"{''.join(concat_inputs)}concat=n={shot_count}:v=1:a=1[vout][aout]")
    else:
        filters.append(f"{''.join(concat_inputs)}concat=n={shot_count}:v=1:a=0[vout]")

    ffmpeg = require("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-y", "-i", str(source), "-filter_complex", ";".join(filters), "-map", "[vout]"]
    if has_audio:
        command += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    else:
        command += ["-an"]
    command += [
        "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(output),
    ]
    print("RUN:", " ".join(command))
    subprocess.run(command, check=True)
    report = {
        "package": PACKAGE,
        "source": str(source),
        "output": str(output),
        "durationSeconds": round(duration_seconds(probe(output)), 3),
        "audioPresent": has_audio,
        "shotCount": shot_count,
        "shots": shots,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
