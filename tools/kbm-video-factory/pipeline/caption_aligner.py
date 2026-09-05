#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any

from captions import normalize_text, seconds_to_frame

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"


def _words(script: str) -> list[str]:
    text = normalize_text(script)
    return [item for item in re.split(r"\s+", text) if item]


def align_script(
    script: str,
    *,
    duration_seconds: float,
    fps: int = 30,
    max_words: int = 5,
    max_chars: int = 42,
) -> list[dict[str, Any]]:
    words = _words(script)
    duration = max(0.0, duration_seconds)
    if not words or duration <= 0:
        return []

    word_duration = duration / len(words)
    timed: list[dict[str, Any]] = []
    for index, word in enumerate(words):
        start = index * word_duration
        end = duration if index == len(words) - 1 else (index + 1) * word_duration
        timed.append({
            "text": word,
            "from": seconds_to_frame(start, fps),
            "to": max(seconds_to_frame(start, fps) + 1, seconds_to_frame(end, fps, ceil=True)),
        })

    cues: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for word in timed:
        candidate = current + [word]
        text = " ".join(item["text"] for item in candidate)
        if current and (len(candidate) > max_words or len(text) > max_chars):
            cues.append({
                "text": " ".join(item["text"] for item in current),
                "from": current[0]["from"],
                "to": current[-1]["to"],
                "words": current,
            })
            current = [word]
        else:
            current = candidate
    if current:
        cues.append({
            "text": " ".join(item["text"] for item in current),
            "from": current[0]["from"],
            "to": current[-1]["to"],
            "words": current,
        })
    return cues
