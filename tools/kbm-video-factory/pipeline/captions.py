#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "هٔ"})


def normalize_text(value: str) -> str:
    text = value.translate(_ARABIC_TO_PERSIAN)
    text = text.replace("\u200f", "").replace("\u200e", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def seconds_to_frame(value: float, fps: int, *, ceil: bool = False) -> int:
    scaled = max(0.0, value) * fps
    return int(math.ceil(scaled) if ceil else math.floor(scaled))


def iter_words(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for segment in data.get("segments", []) or []:
        words = segment.get("words") or []
        for word in words:
            text = normalize_text(str(word.get("word", "")))
            start = word.get("start")
            end = word.get("end")
            if text and isinstance(start, (int, float)) and isinstance(end, (int, float)):
                yield {"text": text, "start": float(start), "end": float(end)}


def segment_cues(data: dict[str, Any], fps: int) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for segment in data.get("segments", []) or []:
        text = normalize_text(str(segment.get("text", "")))
        start = segment.get("start")
        end = segment.get("end")
        if not text or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        cues.append(
            {
                "text": text,
                "from": seconds_to_frame(float(start), fps),
                "to": max(
                    seconds_to_frame(float(start), fps) + 1,
                    seconds_to_frame(float(end), fps, ceil=True),
                ),
            }
        )
    return cues


def word_cues(
    data: dict[str, Any],
    fps: int,
    max_words: int,
    max_chars: int,
    gap_seconds: float,
) -> list[dict[str, Any]]:
    words = list(iter_words(data))
    if not words:
        return segment_cues(data, fps)

    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for word in words:
        candidate = current + [word]
        candidate_text = " ".join(item["text"] for item in candidate)
        previous_end = current[-1]["end"] if current else None
        gap = word["start"] - previous_end if previous_end is not None else 0.0

        should_break = bool(current) and (
            len(candidate) > max_words
            or len(candidate_text) > max_chars
            or gap > gap_seconds
        )
        if should_break:
            groups.append(current)
            current = [word]
        else:
            current = candidate

    if current:
        groups.append(current)

    cues: list[dict[str, Any]] = []
    for group in groups:
        start = float(group[0]["start"])
        end = float(group[-1]["end"])
        cues.append(
            {
                "text": normalize_text(" ".join(item["text"] for item in group)),
                "from": seconds_to_frame(start, fps),
                "to": max(
                    seconds_to_frame(start, fps) + 1,
                    seconds_to_frame(end, fps, ceil=True),
                ),
                "words": [
                    {
                        "text": item["text"],
                        "from": seconds_to_frame(float(item["start"]), fps),
                        "to": max(
                            seconds_to_frame(float(item["start"]), fps) + 1,
                            seconds_to_frame(float(item["end"]), fps, ceil=True),
                        ),
                    }
                    for item in group
                ],
            }
        )
    return cues


def convert(
    data: dict[str, Any],
    *,
    fps: int = 30,
    max_words: int = 5,
    max_chars: int = 42,
    gap_seconds: float = 0.65,
) -> list[dict[str, Any]]:
    return word_cues(data, fps, max_words, max_chars, gap_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert WhisperX JSON to KBM frame captions")
    parser.add_argument("--input", required=True, help="WhisperX JSON file")
    parser.add_argument("--output", required=True, help="KBM captions JSON file")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--max-words", type=int, default=5)
    parser.add_argument("--max-chars", type=int, default=42)
    parser.add_argument("--gap-seconds", type=float, default=0.65)
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    destination = Path(args.output).expanduser().resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    cues = convert(
        data,
        fps=args.fps,
        max_words=max(1, args.max_words),
        max_chars=max(10, args.max_chars),
        gap_seconds=max(0.0, args.gap_seconds),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Caption cues: {len(cues)} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
