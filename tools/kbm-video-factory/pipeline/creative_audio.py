#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from ingest import require

PACKAGE = "KBM-VIDEO-FACTORY-CREATIVE-REEL-TEXT-TTS-MUSIC-SFX-05"
SUPPORTED_SFX = {"hit", "whoosh", "tick", "rise"}


def _run(command: list[str]) -> None:
    print("RUN:", " ".join(command))
    subprocess.run(command, check=True)


def generate_music(output: Path, duration: float, profile: str = "industrial-corporate-105") -> Path:
    if duration <= 0:
        raise RuntimeError("Music duration must be positive")
    ffmpeg = require("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic, rights-clean fallback bed generated entirely with FFmpeg.
    # It is intentionally simple and replaceable by a licensed production track.
    filter_complex = (
        "[0:a]volume=0.12,lowpass=f=180[bass];"
        "[1:a]volume=0.055,highpass=f=180,lowpass=f=1200[mid];"
        "[2:a]volume=0.035,highpass=f=1200,lowpass=f=7000[top];"
        "[bass][mid][top]amix=inputs=3:normalize=0,"
        "aecho=0.8:0.35:90:0.12,alimiter=limit=0.85[aout]"
    )
    command = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=55:sample_rate=48000",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=220:sample_rate=48000",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=48000",
        "-filter_complex",
        filter_complex,
        "-map",
        "[aout]",
        "-t",
        f"{duration:.3f}",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    _run(command)
    return output


def generate_sfx(output: Path, kind: str) -> Path:
    if kind not in SUPPORTED_SFX:
        raise RuntimeError(f"Unsupported generated SFX type: {kind}")
    ffmpeg = require("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)

    if kind == "hit":
        duration = 0.22
        source = "sine=frequency=82:sample_rate=48000"
        af = "volume=0.7,afade=t=out:st=0.03:d=0.19,alimiter=limit=0.9"
    elif kind == "tick":
        duration = 0.10
        source = "sine=frequency=1450:sample_rate=48000"
        af = "volume=0.45,afade=t=out:st=0.01:d=0.09"
    elif kind == "whoosh":
        duration = 0.36
        source = "anoisesrc=color=pink:sample_rate=48000"
        af = "highpass=f=500,lowpass=f=6000,volume=0.22,afade=t=in:d=0.08,afade=t=out:st=0.20:d=0.16"
    else:
        duration = 0.55
        source = "anoisesrc=color=white:sample_rate=48000"
        af = "highpass=f=900,lowpass=f=8500,volume=0.12,afade=t=in:d=0.42,afade=t=out:st=0.46:d=0.09"

    command = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        source,
        "-t",
        f"{duration:.3f}",
        "-af",
        af,
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    _run(command)
    return output


def generate_from_plan(plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    duration = float(plan.get("durationSeconds") or 0.0)
    if duration <= 0:
        raise RuntimeError("Creative audio plan has no valid duration")
    output_dir.mkdir(parents=True, exist_ok=True)
    music = generate_music(output_dir / "creative-music.wav", duration, str(plan.get("musicProfile") or ""))

    sfx: list[dict[str, Any]] = []
    cache: dict[str, Path] = {}
    for index, cue in enumerate(plan.get("sfxCues", []) or []):
        kind = str(cue.get("type") or "hit")
        if kind not in cache:
            cache[kind] = generate_sfx(output_dir / f"sfx-{kind}.wav", kind)
        sfx.append(
            {
                "path": str(cache[kind]),
                "atSeconds": float(cue.get("atSeconds") or 0.0),
                "volume": float(cue.get("volume") or 0.75),
                "type": kind,
                "order": index,
            }
        )

    report = {
        "package": PACKAGE,
        "status": "generated",
        "music": str(music),
        "musicProfile": plan.get("musicProfile"),
        "sfx": sfx,
        "note": "FFmpeg-generated audio is a deterministic rights-clean fallback and may be replaced by licensed production audio.",
    }
    (output_dir / "creative-audio-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic KBM creative music/SFX from a creative plan")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        result = generate_from_plan(plan, Path(args.output_dir).expanduser().resolve())
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"CREATIVE AUDIO FAILED: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
