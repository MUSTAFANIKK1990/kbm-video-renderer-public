#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from ingest import audio_present, duration_seconds, probe, video_stream

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"


def _fps(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        left, right = value.split("/", 1)
        try:
            return float(left) / float(right)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def inspect_output(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size < 1024:
        raise RuntimeError("Rendered MP4 is missing or too small")
    data = probe(path)
    stream = video_stream(data)
    duration = duration_seconds(data)
    checks = {
        "width1080": int(stream.get("width") or 0) == 1080,
        "height1920": int(stream.get("height") or 0) == 1920,
        "h264": stream.get("codec_name") == "h264",
        "yuv420p": stream.get("pix_fmt") in {"yuv420p", "yuvj420p"},
        "fps30": abs(_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate")) - 30.0) <= 0.2,
        "positiveDuration": duration > 0,
    }
    return {
        "package": PACKAGE,
        "path": str(path),
        "bytes": path.stat().st_size,
        "durationSeconds": round(duration, 3),
        "audioPresent": audio_present(data),
        "checks": checks,
        "pass": all(checks.values()),
        "warnings": [name for name, passed in checks.items() if not passed],
    }
