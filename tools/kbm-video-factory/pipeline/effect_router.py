#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

PACKAGE = "KBM-VIDEO-FACTORY-SMART-NONBLOCKING-EDITOR-09"


def _effect_for(text: str, purpose: str) -> list[str]:
    normalized = text.strip()
    effects: list[str] = []
    if purpose == "hook":
        effects.extend(["punch-zoom", "text-pop", "flash-accent"])
    elif purpose == "cta":
        effects.extend(["logo-reveal", "rise", "cta-card"])
    else:
        effects.extend(["slow-zoom", "active-word"])

    if any(token in normalized for token in ("۳", "3", "سه")):
        effects.append("number-pop")
    if any(token in normalized for token in ("اشتباه", "غلط", "خطر")):
        effects.extend(["cross-mark", "hit"])
    if any(token in normalized for token in ("مزیت", "مناسب", "تأیید", "صحیح")):
        effects.append("check-mark")
    if any(token in normalized for token in ("قدرت", "موتور", "بازو", "کابین", "مدل")):
        effects.extend(["machine-highlight", "tracking-label"])
    return list(dict.fromkeys(effects))


def build_effect_plan(timeline: dict[str, Any]) -> dict[str, Any]:
    cues = []
    for segment in timeline.get("segments", []) or []:
        cues.append({
            "sceneId": segment.get("id"),
            "fromSeconds": segment.get("fromSeconds"),
            "toSeconds": segment.get("toSeconds"),
            "effects": _effect_for(str(segment.get("text") or ""), str(segment.get("purpose") or "point")),
        })
    return {"package": PACKAGE, "cues": cues}
