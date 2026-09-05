#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingest import audio_present, duration_seconds, probe, require


@dataclass(frozen=True)
class Segment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def as_dict(self) -> dict[str, float]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
        }


def run_capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    print("RUN:", " ".join(command))
    return subprocess.run(command, check=True, capture_output=True, text=True)


def detect_scenes(source: Path, threshold: float = 0.32) -> list[float]:
    ffmpeg = require("ffmpeg")
    completed = run_capture(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(source),
            "-vf",
            f"select='gt(scene,{threshold:.3f})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    values: list[float] = []
    for match in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", completed.stderr):
        values.append(float(match.group(1)))
    return sorted(set(round(value, 3) for value in values if value > 0))


def detect_silences(source: Path, noise_db: float = -40.0, min_silence: float = 0.55) -> list[Segment]:
    data = probe(source)
    duration = duration_seconds(data)
    if duration <= 0 or not audio_present(data):
        return []

    ffmpeg = require("ffmpeg")
    completed = run_capture(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(source),
            "-af",
            f"silencedetect=noise={noise_db:.1f}dB:d={min_silence:.3f}",
            "-f",
            "null",
            "-",
        ]
    )

    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)", completed.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)", completed.stderr)]

    intervals: list[Segment] = []
    end_index = 0
    for start in starts:
        while end_index < len(ends) and ends[end_index] <= start:
            end_index += 1
        end = ends[end_index] if end_index < len(ends) else duration
        if end > start:
            intervals.append(Segment(max(0.0, start), min(duration, end)))
            end_index += 1
    return intervals


def _scene_inside(scene_times: list[float], start: float, end: float, target: float, tolerance: float) -> float | None:
    candidates = [
        value
        for value in scene_times
        if start <= value <= end and abs(value - target) <= tolerance
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda value: abs(value - target))


def build_keep_segments(
    duration: float,
    silences: list[Segment],
    scene_times: list[float],
    *,
    padding: float = 0.12,
    scene_snap: float = 0.35,
    min_keep: float = 0.30,
) -> list[Segment]:
    if duration <= 0:
        return []
    if not silences:
        return [Segment(0.0, duration)]

    removals: list[Segment] = []
    for silence in silences:
        start = silence.start
        end = silence.end
        if start <= 0.001:
            remove_start = 0.0
        else:
            remove_start = min(end, start + padding)
            snapped = _scene_inside(scene_times, start, end, remove_start, scene_snap)
            if snapped is not None:
                remove_start = snapped

        if end >= duration - 0.001:
            remove_end = duration
        else:
            remove_end = max(start, end - padding)
            snapped = _scene_inside(scene_times, start, end, remove_end, scene_snap)
            if snapped is not None:
                remove_end = snapped

        if remove_end - remove_start >= 0.08:
            removals.append(Segment(remove_start, remove_end))

    if not removals:
        return [Segment(0.0, duration)]

    removals.sort(key=lambda item: item.start)
    merged: list[Segment] = []
    for item in removals:
        if not merged or item.start > merged[-1].end + 0.02:
            merged.append(item)
        else:
            previous = merged[-1]
            merged[-1] = Segment(previous.start, max(previous.end, item.end))

    keep: list[Segment] = []
    cursor = 0.0
    for removal in merged:
        if removal.start - cursor >= min_keep:
            keep.append(Segment(cursor, removal.start))
        cursor = max(cursor, removal.end)
    if duration - cursor >= min_keep:
        keep.append(Segment(cursor, duration))

    if not keep:
        return [Segment(0.0, duration)]
    return keep


def _trim_filter(segments: list[Segment], has_audio: bool, audio_cleanup: bool) -> tuple[str, str, str | None]:
    chains: list[str] = []
    concat_inputs: list[str] = []
    for index, segment in enumerate(segments):
        chains.append(
            f"[0:v]trim=start={segment.start:.3f}:end={segment.end:.3f},"
            f"setpts=PTS-STARTPTS[v{index}]"
        )
        concat_inputs.append(f"[v{index}]")
        if has_audio:
            chains.append(
                f"[0:a]atrim=start={segment.start:.3f}:end={segment.end:.3f},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
            concat_inputs.append(f"[a{index}]")

    if has_audio:
        chains.append(
            f"{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a=1[vcat][acat]"
        )
        if audio_cleanup:
            chains.append(
                "[acat]highpass=f=70,lowpass=f=15000,"
                "loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
            )
            audio_label = "[aout]"
        else:
            audio_label = "[acat]"
        return ";".join(chains), "[vcat]", audio_label

    chains.append(f"{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a=0[vcat]")
    return ";".join(chains), "[vcat]", None


def render_rough_cut(
    source: Path,
    output: Path,
    segments: list[Segment],
    *,
    audio_cleanup: bool = True,
) -> dict[str, Any]:
    if not segments:
        raise RuntimeError("Rough-cut plan contains no keep segments")

    source_probe = probe(source)
    has_audio = audio_present(source_probe)
    ffmpeg = require("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)

    filter_complex, video_label, audio_label = _trim_filter(segments, has_audio, audio_cleanup)
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        filter_complex,
        "-map",
        video_label,
    ]
    if audio_label:
        command += ["-map", audio_label]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
    ]
    if audio_label:
        command += ["-c:a", "aac", "-b:a", "192k"]
    command += ["-movflags", "+faststart", str(output)]

    print("RUN:", " ".join(command))
    subprocess.run(command, check=True)

    result_probe = probe(output)
    result_duration = duration_seconds(result_probe)
    return {
        "output": str(output),
        "durationSeconds": round(result_duration, 3),
        "audioPresent": audio_present(result_probe),
        "audioCleanup": bool(audio_cleanup and has_audio),
        "keepSegments": [segment.as_dict() for segment in segments],
    }


def process(
    source: Path,
    output: Path,
    report_path: Path,
    *,
    scene_threshold: float = 0.32,
    silence_db: float = -40.0,
    min_silence: float = 0.55,
    silence_padding: float = 0.12,
    scene_snap: float = 0.35,
    audio_cleanup: bool = True,
) -> dict[str, Any]:
    source_probe = probe(source)
    duration = duration_seconds(source_probe)
    if duration <= 0:
        raise RuntimeError("Input duration could not be determined")

    scenes = detect_scenes(source, scene_threshold)
    silences = detect_silences(source, silence_db, min_silence)
    keep = build_keep_segments(
        duration,
        silences,
        scenes,
        padding=max(0.0, silence_padding),
        scene_snap=max(0.0, scene_snap),
    )
    rendered = render_rough_cut(source, output, keep, audio_cleanup=audio_cleanup)

    removed_seconds = max(0.0, duration - float(rendered["durationSeconds"]))
    report = {
        "package": "KBM-VIDEO-FACTORY-SCENE-DETECT-ROUGH-CUT-AUDIO-CLEANUP-03",
        "source": str(source),
        "sourceDurationSeconds": round(duration, 3),
        "sceneThreshold": scene_threshold,
        "sceneCount": len(scenes),
        "sceneTimes": scenes,
        "silenceNoiseDb": silence_db,
        "minimumSilenceSeconds": min_silence,
        "silencePaddingSeconds": silence_padding,
        "sceneSnapSeconds": scene_snap,
        "silenceCount": len(silences),
        "silences": [item.as_dict() for item in silences],
        "keepSegments": [item.as_dict() for item in keep],
        "removedSeconds": round(removed_seconds, 3),
        "output": rendered,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect scenes/silence, remove dead-space and normalize voice audio for KBM footage"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--scene-threshold", type=float, default=0.32)
    parser.add_argument("--silence-db", type=float, default=-40.0)
    parser.add_argument("--min-silence", type=float, default=0.55)
    parser.add_argument("--silence-padding", type=float, default=0.12)
    parser.add_argument("--scene-snap", type=float, default=0.35)
    parser.add_argument("--no-audio-cleanup", action="store_true")
    args = parser.parse_args()

    try:
        result = process(
            Path(args.input).expanduser().resolve(),
            Path(args.output).expanduser().resolve(),
            Path(args.report).expanduser().resolve(),
            scene_threshold=max(0.01, min(0.99, args.scene_threshold)),
            silence_db=min(-1.0, args.silence_db),
            min_silence=max(0.1, args.min_silence),
            silence_padding=max(0.0, args.silence_padding),
            scene_snap=max(0.0, args.scene_snap),
            audio_cleanup=not args.no_audio_cleanup,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ROUGH CUT FAILED: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
