#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PACKAGE = "KBM-VIDEO-FACTORY-CREATIVE-REEL-TEXT-TTS-MUSIC-SFX-05"


def load_presets(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise RuntimeError("Creative preset file must contain a non-empty object")
    return data


def _scaled_seconds(value: float, scale: float, duration: float) -> float:
    return max(0.0, min(duration, value * scale))


def build_plan(
    preset_id: str,
    *,
    duration_seconds: float,
    fps: int = 30,
    presets_path: Path | None = None,
) -> dict[str, Any]:
    if duration_seconds <= 0:
        raise RuntimeError("Creative plan requires a positive media duration")
    if fps <= 0:
        raise RuntimeError("Creative plan requires positive FPS")

    root = Path(__file__).resolve().parents[1]
    presets_path = presets_path or root / "config" / "creative-presets.json"
    presets = load_presets(presets_path)
    preset = presets.get(preset_id)
    if not isinstance(preset, dict):
        raise RuntimeError(f"Unknown creative preset: {preset_id}")

    reference_duration = float(preset.get("referenceDurationSeconds") or duration_seconds)
    if reference_duration <= 0:
        reference_duration = duration_seconds
    scale = duration_seconds / reference_duration

    overlays: list[dict[str, Any]] = []
    for raw in preset.get("overlays", []) or []:
        if not isinstance(raw, dict):
            continue
        start = _scaled_seconds(float(raw.get("fromSeconds") or 0.0), scale, duration_seconds)
        end = _scaled_seconds(float(raw.get("toSeconds") or 0.0), scale, duration_seconds)
        if end <= start:
            continue
        overlays.append(
            {
                "from": int(round(start * fps)),
                "to": max(int(round(start * fps)) + 1, int(round(end * fps))),
                "fromSeconds": round(start, 3),
                "toSeconds": round(end, 3),
                "kind": str(raw.get("kind") or "point"),
                "eyebrow": str(raw.get("eyebrow") or ""),
                "text": str(raw.get("text") or ""),
                "accentText": str(raw.get("accentText") or ""),
                "position": str(raw.get("position") or "bottom"),
            }
        )

    sfx_cues: list[dict[str, Any]] = []
    for raw in preset.get("sfxCues", []) or []:
        if not isinstance(raw, dict):
            continue
        at_seconds = _scaled_seconds(float(raw.get("atSeconds") or 0.0), scale, duration_seconds)
        sfx_cues.append(
            {
                "atSeconds": round(at_seconds, 3),
                "type": str(raw.get("type") or "hit"),
                "volume": max(0.0, min(2.0, float(raw.get("volume") or 0.75))),
            }
        )

    return {
        "package": PACKAGE,
        "presetId": preset_id,
        "subject": preset.get("subject"),
        "language": preset.get("language", "fa-IR"),
        "durationSeconds": round(duration_seconds, 3),
        "fps": fps,
        "title": str(preset.get("title") or ""),
        "subtitle": str(preset.get("subtitle") or ""),
        "cta": str(preset.get("cta") or ""),
        "voiceoverScript": str(preset.get("voiceoverScript") or ""),
        "musicProfile": str(preset.get("musicProfile") or ""),
        "overlays": overlays,
        "sfxCues": sfx_cues,
        "timingScale": round(scale, 5),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a duration-aware KBM creative reel plan")
    parser.add_argument("--preset", required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--presets", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        plan = build_plan(
            args.preset,
            duration_seconds=args.duration,
            fps=args.fps,
            presets_path=Path(args.presets).expanduser().resolve() if args.presets else None,
        )
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"CREATIVE PLAN FAILED: {exc}")
        return 1

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
