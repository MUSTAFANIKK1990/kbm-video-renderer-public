#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"
VERSION = "0.9.0"

HARD_BLOCKERS = {
    "input-video-stream",
    "input-decode",
    "input-duration",
    "output-write",
    "render-all",
}

SOFT_STAGES = {
    "rough-cut",
    "visual-smart-cut",
    "creative-director",
    "creative-audio",
    "voiceover",
    "shot-composer",
    "effect-router",
    "caption-aligner",
    "whisperx",
    "audio-mix",
    "remotion-render",
    "analytics",
}


@dataclass
class StageState:
    stage: str
    status: str
    message: str = ""
    fallback: str | None = None
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def pass_state(stage: str, *, details: dict[str, Any] | None = None) -> StageState:
    return StageState(stage=stage, status="PASS", details=details)


def fallback_state(stage: str, message: str, fallback: str, *, details: dict[str, Any] | None = None) -> StageState:
    return StageState(stage=stage, status="FALLBACK", message=message, fallback=fallback, details=details)


def warning_state(stage: str, message: str, *, details: dict[str, Any] | None = None) -> StageState:
    return StageState(stage=stage, status="WARNING", message=message, details=details)


def failed_state(stage: str, message: str, *, details: dict[str, Any] | None = None) -> StageState:
    return StageState(stage=stage, status="FAILED", message=message, details=details)


def is_hard_blocker(stage: str) -> bool:
    return stage in HARD_BLOCKERS
