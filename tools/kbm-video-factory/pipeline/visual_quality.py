#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingest import duration_seconds, probe, require
from rough_cut import Segment, detect_scenes, render_rough_cut

PACKAGE = "KBM-VIDEO-FACTORY-VISUAL-QUALITY-SCENE-RANKING-SMART-CUT-04"


@dataclass
class FrameMetrics:
    time: float
    brightness: float
    contrast: float
    sharpness: float
    center_detail: float
    clipping: float
    motion: float


@dataclass
class Candidate:
    start: float
    end: float
    score: float
    metrics: dict[str, float]
    flags: list[str]
    selected: bool = False
    rank: int = 0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "score": round(self.score, 4),
            "rank": self.rank,
            "selected": self.selected,
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
            "flags": self.flags,
        }


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _edge_energy(frame: bytes, width: int, height: int, *, center: bool = False) -> float:
    if not frame or width < 3 or height < 3:
        return 0.0

    if center:
        x0 = width // 4
        x1 = width - x0
        y0 = height // 4
        y1 = height - y0
    else:
        x0, x1, y0, y1 = 0, width, 0, height

    total = 0
    count = 0
    for y in range(y0, y1):
        row = y * width
        for x in range(x0, x1 - 1):
            i = row + x
            total += abs(frame[i + 1] - frame[i])
            count += 1
    for y in range(y0, y1 - 1):
        row = y * width
        next_row = (y + 1) * width
        for x in range(x0, x1):
            total += abs(frame[next_row + x] - frame[row + x])
            count += 1
    return (total / count) if count else 0.0


def _frame_stats(frame: bytes, width: int, height: int) -> tuple[float, float, float, float, float]:
    count = len(frame)
    if count == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    mean = sum(frame) / count
    variance = sum((value - mean) ** 2 for value in frame) / count
    stddev = math.sqrt(variance)
    edge = _edge_energy(frame, width, height)
    center_edge = _edge_energy(frame, width, height, center=True)
    dark = sum(1 for value in frame if value <= 12) / count
    bright = sum(1 for value in frame if value >= 243) / count

    brightness = mean / 255.0
    contrast = clamp(stddev / 64.0)
    sharpness = clamp(edge / 30.0)
    if edge <= 0.001:
        center_detail = 0.0
    else:
        ratio = center_edge / edge
        center_detail = clamp((ratio - 0.55) / 0.95)
    clipping = clamp(1.0 - (dark + bright))
    return brightness, contrast, sharpness, center_detail, clipping


def decode_sample_frames(
    source: Path,
    *,
    sample_fps: float = 2.0,
    width: int = 160,
    height: int = 90,
) -> list[FrameMetrics]:
    ffmpeg = require("ffmpeg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        f"fps={sample_fps:.4f},scale={width}:{height}:flags=bilinear,format=gray",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    print("RUN:", " ".join(command))
    completed = subprocess.run(command, check=True, capture_output=True)
    frame_size = width * height
    if frame_size <= 0:
        raise RuntimeError("Invalid visual analysis frame size")
    raw = completed.stdout
    frame_count = len(raw) // frame_size
    if frame_count <= 0:
        raise RuntimeError("Visual analyzer could not decode sample frames")

    metrics: list[FrameMetrics] = []
    previous: bytes | None = None
    for index in range(frame_count):
        frame = raw[index * frame_size : (index + 1) * frame_size]
        brightness, contrast, sharpness, center_detail, clipping = _frame_stats(frame, width, height)
        if previous is None:
            motion = 0.0
        else:
            motion_raw = sum(abs(a - b) for a, b in zip(frame, previous)) / frame_size
            motion = clamp(motion_raw / 48.0)
        metrics.append(
            FrameMetrics(
                time=index / sample_fps,
                brightness=brightness,
                contrast=contrast,
                sharpness=sharpness,
                center_detail=center_detail,
                clipping=clipping,
                motion=motion,
            )
        )
        previous = frame
    return metrics


def _subdivide(start: float, end: float, window: float, min_clip: float) -> list[Segment]:
    duration = end - start
    if duration <= 0:
        return []
    if duration <= window + 0.15:
        return [Segment(start, end)] if duration >= min_clip else []

    segments: list[Segment] = []
    cursor = start
    while cursor < end - 0.001:
        proposed_end = min(end, cursor + window)
        remaining = end - proposed_end
        if 0 < remaining < min_clip:
            proposed_end = end
        if proposed_end - cursor >= min_clip:
            segments.append(Segment(cursor, proposed_end))
        cursor = proposed_end
    return segments


def build_candidates(
    duration: float,
    scene_times: list[float],
    *,
    window: float = 2.5,
    min_clip: float = 1.2,
) -> list[Segment]:
    boundaries = [0.0]
    boundaries.extend(value for value in scene_times if min_clip <= value <= duration - min_clip)
    boundaries.append(duration)
    boundaries = sorted(set(round(value, 3) for value in boundaries))

    result: list[Segment] = []
    for index in range(len(boundaries) - 1):
        result.extend(_subdivide(boundaries[index], boundaries[index + 1], window, min_clip))

    if not result and duration > 0:
        result = [Segment(0.0, duration)]
    return result


def _frames_for_segment(frames: list[FrameMetrics], segment: Segment) -> list[FrameMetrics]:
    selected = [frame for frame in frames if segment.start <= frame.time < segment.end]
    if selected:
        return selected
    midpoint = (segment.start + segment.end) / 2
    if not frames:
        return []
    return [min(frames, key=lambda frame: abs(frame.time - midpoint))]


def _exposure_score(brightness: float) -> float:
    if 0.28 <= brightness <= 0.78:
        return 1.0
    if brightness < 0.28:
        return clamp(brightness / 0.28)
    return clamp((1.0 - brightness) / 0.22)


def _motion_scores(motion: float) -> tuple[float, float]:
    stability = 1.0 if motion <= 0.20 else clamp(1.0 - ((motion - 0.20) / 0.60))
    activity = clamp(motion / 0.10)
    return stability, activity


def score_candidate(segment: Segment, frames: list[FrameMetrics]) -> Candidate:
    selected = _frames_for_segment(frames, segment)
    if not selected:
        metrics = {
            "brightness": 0.0,
            "contrast": 0.0,
            "sharpness": 0.0,
            "centerDetail": 0.0,
            "clipping": 0.0,
            "motion": 0.0,
            "exposure": 0.0,
            "stability": 0.0,
            "activity": 0.0,
        }
        return Candidate(segment.start, segment.end, 0.0, metrics, ["no-samples"])

    def avg(name: str) -> float:
        return sum(getattr(frame, name) for frame in selected) / len(selected)

    brightness = avg("brightness")
    contrast = avg("contrast")
    sharpness = avg("sharpness")
    center_detail = avg("center_detail")
    clipping = avg("clipping")
    motion = avg("motion")
    exposure = _exposure_score(brightness)
    stability, activity = _motion_scores(motion)

    score = (
        sharpness * 0.27
        + exposure * 0.20
        + contrast * 0.15
        + stability * 0.13
        + activity * 0.10
        + center_detail * 0.10
        + clipping * 0.05
    )
    score = clamp(score)

    flags: list[str] = []
    if brightness < 0.16:
        flags.append("dark")
    elif brightness > 0.90:
        flags.append("overexposed")
    if contrast < 0.12:
        flags.append("low-contrast")
    if sharpness < 0.12:
        flags.append("soft-or-blurry")
    if motion < 0.012:
        flags.append("near-static")
    if motion > 0.70:
        flags.append("high-motion")
    if clipping < 0.70:
        flags.append("heavy-clipping")

    return Candidate(
        start=segment.start,
        end=segment.end,
        score=score,
        metrics={
            "brightness": brightness,
            "contrast": contrast,
            "sharpness": sharpness,
            "centerDetail": center_detail,
            "clipping": clipping,
            "motion": motion,
            "exposure": exposure,
            "stability": stability,
            "activity": activity,
        },
        flags=flags,
    )


def _merge_selected(candidates: list[Candidate], gap: float = 0.08) -> list[Segment]:
    selected = sorted((item for item in candidates if item.selected), key=lambda item: item.start)
    if not selected:
        return []
    merged: list[Segment] = [Segment(selected[0].start, selected[0].end)]
    for item in selected[1:]:
        previous = merged[-1]
        if item.start <= previous.end + gap:
            merged[-1] = Segment(previous.start, max(previous.end, item.end))
        else:
            merged.append(Segment(item.start, item.end))
    return merged


def select_candidates(
    candidates: list[Candidate],
    *,
    duration: float,
    target_ratio: float = 0.65,
    target_seconds: float | None = None,
    min_score: float = 0.35,
    min_target: float = 8.0,
    max_target: float = 45.0,
) -> tuple[list[Segment], float]:
    if not candidates:
        return [], 0.0

    if duration <= min_target + 1.0:
        target = duration
    elif target_seconds is not None and target_seconds > 0:
        target = min(duration, target_seconds)
    else:
        target = min(duration, max(min_target, min(max_target, duration * clamp(target_ratio, 0.15, 1.0))))

    ranked = sorted(candidates, key=lambda item: (-item.score, item.start))
    for rank, item in enumerate(ranked, start=1):
        item.rank = rank

    chosen_duration = 0.0
    for item in ranked:
        if chosen_duration >= target:
            break
        if item.score < min_score:
            continue
        item.selected = True
        chosen_duration += item.duration

    if chosen_duration < target:
        for item in ranked:
            if chosen_duration >= target:
                break
            if item.selected:
                continue
            item.selected = True
            chosen_duration += item.duration

    keep = _merge_selected(candidates)
    if not keep:
        best = ranked[0]
        best.selected = True
        keep = [Segment(best.start, best.end)]
    return keep, target


def process(
    source: Path,
    output: Path,
    report_path: Path,
    *,
    sample_fps: float = 2.0,
    window: float = 2.5,
    scene_threshold: float = 0.22,
    target_ratio: float = 0.65,
    target_seconds: float | None = None,
    min_score: float = 0.35,
    min_clip: float = 1.2,
    analysis_only: bool = False,
) -> dict[str, Any]:
    source_data = probe(source)
    duration = duration_seconds(source_data)
    if duration <= 0:
        raise RuntimeError("Input duration could not be determined")

    scenes = detect_scenes(source, scene_threshold)
    frames = decode_sample_frames(source, sample_fps=sample_fps)
    segments = build_candidates(duration, scenes, window=window, min_clip=min_clip)
    candidates = [score_candidate(segment, frames) for segment in segments]
    keep, target = select_candidates(
        candidates,
        duration=duration,
        target_ratio=target_ratio,
        target_seconds=target_seconds,
        min_score=min_score,
    )

    selected_duration = sum(segment.duration for segment in keep)
    rendered: dict[str, Any] | None = None
    if not analysis_only:
        rendered = render_rough_cut(source, output, keep, audio_cleanup=False)
        selected_duration = float(rendered.get("durationSeconds") or selected_duration)

    selected_candidates = [item for item in candidates if item.selected]
    rejected_candidates = [item for item in candidates if not item.selected]
    selected_average = (
        sum(item.score for item in selected_candidates) / len(selected_candidates)
        if selected_candidates
        else 0.0
    )
    rejected_average = (
        sum(item.score for item in rejected_candidates) / len(rejected_candidates)
        if rejected_candidates
        else 0.0
    )

    report = {
        "package": PACKAGE,
        "source": str(source),
        "sourceDurationSeconds": round(duration, 3),
        "sampleFps": sample_fps,
        "sampleFrameCount": len(frames),
        "sceneThreshold": scene_threshold,
        "sceneCount": len(scenes),
        "sceneTimes": scenes,
        "candidateWindowSeconds": window,
        "candidateCount": len(candidates),
        "targetRatio": target_ratio,
        "targetSeconds": round(target, 3),
        "minimumScore": min_score,
        "selectedCandidateCount": len(selected_candidates),
        "selectedAverageScore": round(selected_average, 4),
        "rejectedAverageScore": round(rejected_average, 4),
        "keepSegments": [segment.as_dict() for segment in keep],
        "selectedDurationSeconds": round(selected_duration, 3),
        "removedSeconds": round(max(0.0, duration - selected_duration), 3),
        "candidates": [item.as_dict() for item in sorted(candidates, key=lambda item: item.start)],
        "output": rendered,
        "analysisOnly": analysis_only,
        "limitations": [
            "Package 04 ranks deterministic visual quality, not machine-part semantics.",
            "No face, brand, machine-model or object classifier is used in this package.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze visual quality, rank micro-scenes and create a deterministic KBM smart cut"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--sample-fps", type=float, default=2.0)
    parser.add_argument("--window", type=float, default=2.5)
    parser.add_argument("--scene-threshold", type=float, default=0.22)
    parser.add_argument("--target-ratio", type=float, default=0.65)
    parser.add_argument("--target-seconds", type=float, default=None)
    parser.add_argument("--min-score", type=float, default=0.35)
    parser.add_argument("--min-clip", type=float, default=1.2)
    parser.add_argument("--analysis-only", action="store_true")
    args = parser.parse_args()

    try:
        result = process(
            Path(args.input).expanduser().resolve(),
            Path(args.output).expanduser().resolve(),
            Path(args.report).expanduser().resolve(),
            sample_fps=max(0.5, min(6.0, args.sample_fps)),
            window=max(1.2, min(8.0, args.window)),
            scene_threshold=max(0.01, min(0.99, args.scene_threshold)),
            target_ratio=max(0.15, min(1.0, args.target_ratio)),
            target_seconds=max(0.5, args.target_seconds) if args.target_seconds else None,
            min_score=max(0.0, min(1.0, args.min_score)),
            min_clip=max(0.5, min(4.0, args.min_clip)),
            analysis_only=args.analysis_only,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"VISUAL SMART CUT FAILED: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
