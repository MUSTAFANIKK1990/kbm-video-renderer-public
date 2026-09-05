#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"


def build_timeline(brief: dict[str, Any], *, duration_seconds: float, fps: int = 30) -> dict[str, Any]:
    duration = max(0.1, duration_seconds)
    segments: list[dict[str, Any]] = []
    for index, overlay in enumerate(brief.get("overlays", []) or []):
        start = float(overlay.get("fromSeconds") if overlay.get("fromSeconds") is not None else float(overlay.get("from", 0)) / fps)
        end = float(overlay.get("toSeconds") if overlay.get("toSeconds") is not None else float(overlay.get("to", 0)) / fps)
        start = max(0.0, min(duration, start))
        end = max(start, min(duration, end))
        if end <= start:
            continue
        segments.append({
            "id": f"scene-{index + 1:02d}",
            "fromSeconds": round(start, 3),
            "toSeconds": round(end, 3),
            "durationSeconds": round(end - start, 3),
            "purpose": str(overlay.get("kind") or "point"),
            "text": str(overlay.get("text") or ""),
        })

    if not segments:
        weights = [("hook", 0.12), ("setup", 0.18), ("point", 0.20), ("point", 0.20), ("result", 0.15), ("cta", 0.15)]
        cursor = 0.0
        for index, (purpose, weight) in enumerate(weights):
            end = duration if index == len(weights) - 1 else min(duration, cursor + duration * weight)
            segments.append({
                "id": f"scene-{index + 1:02d}",
                "fromSeconds": round(cursor, 3),
                "toSeconds": round(end, 3),
                "durationSeconds": round(max(0.0, end - cursor), 3),
                "purpose": purpose,
                "text": "",
            })
            cursor = end

    return {
        "package": PACKAGE,
        "durationSeconds": round(duration, 3),
        "fps": fps,
        "segments": segments,
    }
