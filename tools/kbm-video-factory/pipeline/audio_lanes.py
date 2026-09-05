#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingest import audio_present, duration_seconds, probe, require

PACKAGE = "KBM-VIDEO-FACTORY-CREATIVE-REEL-TEXT-TTS-MUSIC-SFX-05"


@dataclass(frozen=True)
class SfxSpec:
    path: Path
    at_seconds: float
    volume: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "atSeconds": round(self.at_seconds, 3),
            "volume": round(self.volume, 3),
        }


def parse_sfx(value: str) -> SfxSpec:
    parts = value.rsplit("@", 2)
    if len(parts) < 2:
        raise ValueError("SFX must be PATH@SECONDS or PATH@SECONDS@VOLUME")
    path = Path(parts[0]).expanduser().resolve()
    at_seconds = float(parts[1])
    volume = float(parts[2]) if len(parts) == 3 else 0.75
    if at_seconds < 0:
        raise ValueError("SFX timestamp cannot be negative")
    if not 0 <= volume <= 2:
        raise ValueError("SFX volume must be between 0 and 2")
    if not path.exists():
        raise ValueError(f"SFX file not found: {path}")
    return SfxSpec(path=path, at_seconds=at_seconds, volume=volume)


def _resolve_optional(path: Path | None, label: str) -> Path | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise RuntimeError(f"{label} file not found: {resolved}")
    return resolved


def mix_audio_lanes(
    source: Path,
    output: Path,
    report_path: Path,
    *,
    music: Path | None = None,
    music_volume: float = 0.12,
    sfx: list[SfxSpec] | None = None,
    voiceover: Path | None = None,
    voiceover_volume: float = 1.0,
    source_volume: float = 1.0,
    source_duck_volume: float = 0.22,
) -> dict[str, Any]:
    source_probe = probe(source)
    duration = duration_seconds(source_probe)
    if duration <= 0:
        raise RuntimeError("Input duration could not be determined")

    sfx = sfx or []
    music = _resolve_optional(music, "Music")
    voiceover = _resolve_optional(voiceover, "Voiceover")

    if not 0 <= music_volume <= 1:
        raise RuntimeError("Music volume must be between 0 and 1")
    if not 0 <= voiceover_volume <= 2:
        raise RuntimeError("Voiceover volume must be between 0 and 2")
    if not 0 <= source_volume <= 2:
        raise RuntimeError("Source volume must be between 0 and 2")
    if not 0 <= source_duck_volume <= 1:
        raise RuntimeError("Source duck volume must be between 0 and 1")

    if music is None and not sfx and voiceover is None:
        report = {
            "package": PACKAGE,
            "status": "disabled",
            "source": str(source),
            "output": str(source),
            "music": None,
            "voiceover": None,
            "sfx": [],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    ffmpeg = require("ffmpeg")
    command = [ffmpeg, "-y", "-i", str(source)]
    input_index = 1

    music_index: int | None = None
    if music is not None:
        music_index = input_index
        command += ["-stream_loop", "-1", "-i", str(music)]
        input_index += 1

    voiceover_index: int | None = None
    if voiceover is not None:
        voiceover_index = input_index
        command += ["-i", str(voiceover)]
        input_index += 1

    sfx_indexes: list[tuple[int, SfxSpec]] = []
    for spec in sfx:
        sfx_indexes.append((input_index, spec))
        command += ["-i", str(spec.path)]
        input_index += 1

    filters: list[str] = []
    mix_labels: list[str] = []
    has_source_audio = audio_present(source_probe)
    effective_source_volume = source_duck_volume if voiceover_index is not None else source_volume

    if has_source_audio:
        filters.append(
            f"[0:a]aresample=async=1:first_pts=0,volume={effective_source_volume:.3f}[dialogue]"
        )
        mix_labels.append("[dialogue]")

    if music_index is not None:
        filters.append(
            f"[{music_index}:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,"
            f"volume={music_volume:.3f}[music]"
        )
        mix_labels.append("[music]")

    if voiceover_index is not None:
        filters.append(
            f"[{voiceover_index}:a]aresample=48000,asetpts=PTS-STARTPTS,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11,volume={voiceover_volume:.3f}[voiceover]"
        )
        mix_labels.append("[voiceover]")

    for order, (index, spec) in enumerate(sfx_indexes):
        delay_ms = int(round(spec.at_seconds * 1000))
        label = f"sfx{order}"
        filters.append(
            f"[{index}:a]asetpts=PTS-STARTPTS,adelay={delay_ms}:all=1,"
            f"volume={spec.volume:.3f}[{label}]"
        )
        mix_labels.append(f"[{label}]")

    if not mix_labels:
        raise RuntimeError("No audio lanes available to mix")

    filters.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=longest:normalize=0,"
        f"atrim=duration={duration:.3f},alimiter=limit=0.95[aout]"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    command += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "0:v:0",
        "-map",
        "[aout]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-b:a",
        "192k",
        "-t",
        f"{duration:.3f}",
        "-movflags",
        "+faststart",
        str(output),
    ]

    print("RUN:", " ".join(command))
    subprocess.run(command, check=True)

    result_probe = probe(output)
    report = {
        "package": PACKAGE,
        "status": "generated",
        "source": str(source),
        "output": str(output),
        "durationSeconds": round(duration_seconds(result_probe), 3),
        "audioPresent": audio_present(result_probe),
        "sourceAudio": {
            "present": has_source_audio,
            "volume": round(effective_source_volume, 3),
            "duckedForVoiceover": voiceover_index is not None,
        },
        "music": {
            "path": str(music),
            "volume": round(music_volume, 3),
        }
        if music is not None
        else None,
        "voiceover": {
            "path": str(voiceover),
            "volume": round(voiceover_volume, 3),
        }
        if voiceover is not None
        else None,
        "sfx": [spec.as_dict() for spec in sfx],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Mix KBM dialogue, voiceover, music and timestamped SFX")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--music", default=None)
    parser.add_argument("--music-volume", type=float, default=0.12)
    parser.add_argument("--voiceover", default=None)
    parser.add_argument("--voiceover-volume", type=float, default=1.0)
    parser.add_argument("--source-volume", type=float, default=1.0)
    parser.add_argument("--source-duck-volume", type=float, default=0.22)
    parser.add_argument("--sfx", action="append", default=[])
    args = parser.parse_args()

    try:
        music = Path(args.music).expanduser().resolve() if args.music else None
        voiceover = Path(args.voiceover).expanduser().resolve() if args.voiceover else None
        sfx = [parse_sfx(value) for value in args.sfx]
        result = mix_audio_lanes(
            Path(args.input).expanduser().resolve(),
            Path(args.output).expanduser().resolve(),
            Path(args.report).expanduser().resolve(),
            music=music,
            music_volume=args.music_volume,
            sfx=sfx,
            voiceover=voiceover,
            voiceover_volume=args.voiceover_volume,
            source_volume=args.source_volume,
            source_duck_volume=args.source_duck_volume,
        )
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"AUDIO LANES FAILED: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
