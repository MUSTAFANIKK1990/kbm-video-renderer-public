#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any

from campaign_brief import build_campaign_plan, validated_edit_style

HOTFIX = "KBM-PACKAGE-13.1.1-V4-CAMPAIGN-WRITER-COMPAT"


def _duration(context: dict[str, Any] | None) -> float:
    if isinstance(context, dict):
        for key in ("durationSeconds", "maxSeconds", "duration"):
            try:
                value = float(context.get(key) or 0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                return max(5.0, min(90.0, value))
    try:
        value = float(os.environ.get("KBM_CAMPAIGN_DURATION_SECONDS", "60") or 60)
    except ValueError:
        value = 60.0
    return max(5.0, min(90.0, value))


def write_ad_brief(text: str, context: dict[str, Any] | None = None, edit_style: str | None = None) -> dict[str, Any]:
    """Deprecated compatibility adapter for Package 13/13.1.

    `campaign_brief.py` remains the canonical authority. This shim exists only
    because `orchestrator_v4.py` still imports `write_ad_brief`.
    """
    brief = str(text or "").strip()
    if not brief:
        return {}
    style = validated_edit_style(edit_style)
    plan = build_campaign_plan(brief, duration_seconds=_duration(context), fps=30)
    plan["editStyle"] = style
    plan["campaignGoal"] = "auto-commercial"
    plan["compatibilityHotfix"] = HOTFIX
    return plan
