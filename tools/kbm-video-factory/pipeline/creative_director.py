#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from campaign_brief import build_campaign_plan, decode_campaign_brief
from creative_plan import build_plan

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"


def fallback_brief(duration_seconds: float, fps: int = 30, *, title: str = "کاریاب ماشین") -> dict[str, Any]:
    duration = max(1.0, duration_seconds)
    hook_end = min(duration, max(1.6, duration * 0.18))
    cta_start = max(hook_end, duration - min(3.0, duration * 0.22))
    overlays = [
        {
            "from": 0,
            "to": max(1, int(round(hook_end * fps))),
            "fromSeconds": 0.0,
            "toSeconds": round(hook_end, 3),
            "kind": "hook",
            "eyebrow": "کاریاب ماشین",
            "text": title or "ماشین‌آلات پروژه",
            "accentText": "معرفی سریع و کاربردی",
            "position": "top",
        },
        {
            "from": int(round(cta_start * fps)),
            "to": max(int(round(cta_start * fps)) + 1, int(round(duration * fps))),
            "fromSeconds": round(cta_start, 3),
            "toSeconds": round(duration, 3),
            "kind": "cta",
            "eyebrow": "کاریاب ماشین",
            "text": "ماشین‌آلات مورد نیاز پروژه را پیدا کن",
            "accentText": "karyabmashin.ir",
            "position": "center",
        },
    ]
    return {
        "package": PACKAGE,
        "presetId": "package09-safe-default",
        "subject": "generic-machinery",
        "language": "fa-IR",
        "durationSeconds": round(duration, 3),
        "fps": fps,
        "title": title or "کاریاب ماشین",
        "subtitle": "ویدیوی صنعتی هوشمند",
        "cta": "مشاهده در کاریاب ماشین",
        "voiceoverScript": "برای مشاهده ماشین‌آلات، خدمات و آگهی‌های تخصصی پروژه، به کاریاب ماشین مراجعه کنید.",
        "musicProfile": "industrial-corporate-105",
        "overlays": overlays,
        "sfxCues": [
            {"atSeconds": 0.15, "type": "hit", "volume": 0.55},
            {"atSeconds": round(cta_start, 3), "type": "rise", "volume": 0.45},
        ],
        "fallback": True,
    }


def build_brief(
    preset_id: str | None,
    *,
    duration_seconds: float,
    fps: int = 30,
    title: str = "",
    presets_path: Path | None = None,
) -> tuple[dict[str, Any], bool, str | None]:
    try:
        campaign_brief = decode_campaign_brief()
    except ValueError as exc:
        fallback = fallback_brief(duration_seconds, fps, title=title or "کاریاب ماشین")
        fallback["package13"] = {"director": "campaign-brief", "fallback": True, "reason": str(exc)}
        return fallback, True, str(exc)

    if campaign_brief:
        plan = build_campaign_plan(campaign_brief, duration_seconds, fps)
        plan["package09"] = {"director": "package13-campaign-brief", "fallback": False}
        return plan, False, None

    if preset_id:
        try:
            plan = build_plan(
                preset_id,
                duration_seconds=duration_seconds,
                fps=fps,
                presets_path=presets_path,
            )
            plan["package09"] = {"director": "preset-adapter", "fallback": False}
            return plan, False, None
        except (RuntimeError, ValueError) as exc:
            fallback = fallback_brief(duration_seconds, fps, title=title or "کاریاب ماشین")
            return fallback, True, str(exc)
    return fallback_brief(duration_seconds, fps, title=title or "کاریاب ماشین"), True, "No creative preset supplied"
