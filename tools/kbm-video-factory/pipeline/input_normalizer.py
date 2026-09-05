#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ingest import duration_seconds, ingest, probe, video_stream

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"


def validate_video(source: Path) -> dict[str, Any]:
    if not source.is_file() or source.stat().st_size < 1:
        raise RuntimeError("Input video file is missing or empty")
    data = probe(source)
    stream = video_stream(data)
    duration = duration_seconds(data)
    if duration <= 0:
        raise RuntimeError("Input video duration is zero or unavailable")
    return {
        "source": str(source),
        "durationSeconds": round(duration, 3),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "codec": stream.get("codec_name"),
    }


def normalize_input(
    source: Path,
    output: Path,
    report_path: Path,
    *,
    fit: str = "auto",
    fps: int = 30,
    max_seconds: float = 60.0,
) -> dict[str, Any]:
    source_meta = validate_video(source)
    result = ingest(source, output, report_path, fps=fps, fit=fit, max_seconds=max_seconds)
    result["package"] = PACKAGE
    result["sourceValidation"] = source_meta
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
