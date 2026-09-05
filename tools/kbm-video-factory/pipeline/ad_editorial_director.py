#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any

from campaign_brief import reference_editing_profile, validated_edit_style

_SPLIT = re.compile(r"(?<=[\.؟!؛])\s+|\s*[،؛]\s*")


def _phrases(script: str) -> list[str]:
    parts = [x.strip(" \n\t،؛.") for x in _SPLIT.split(script.strip()) if x.strip(" \n\t،؛.")]
    return parts or ([script.strip()] if script.strip() else ["کاریاب ماشین"])


def _intent_query(text: str, subject: str) -> str:
    joined = f"{subject} {text}".lower()
    pairs = [
        (("بیل", "excavator"), "excavator construction site close up"),
        (("هیدرولیک", "hydraulic"), "excavator hydraulic cylinder inspection"),
        (("کابین", "operator"), "heavy equipment operator cabin"),
        (("معدن", "mining"), "open pit mine heavy machinery"),
        (("راهسازی", "road"), "road construction heavy equipment"),
        (("تعمیر", "maintenance"), "heavy equipment maintenance mechanic"),
        (("قطعه", "spare"), "heavy machinery spare parts workshop"),
        (("اجاره", "rental"), "heavy equipment rental inspection"),
        (("جرثقیل", "crane"), "mobile crane construction site"),
        (("لودر", "loader"), "wheel loader construction site"),
    ]
    for needles, query in pairs:
        if any(needle in joined for needle in needles):
            return query
    return "cinematic heavy machinery industrial construction"


def _reference_profile(brief: dict[str, Any]) -> dict[str, Any]:
    candidate = brief.get("referenceEditingProfile")
    if isinstance(candidate, dict):
        fallback = reference_editing_profile()
        return {**fallback, **candidate}
    return reference_editing_profile()


def _positive(value: Any, fallback: float, *, lower: float, upper: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if lower <= number <= upper else fallback


def _style_policy(style_name: str) -> dict[str, Any]:
    if style_name == "cinematic":
        return {
            "reset": 2.15,
            "pattern": ("video", "broll", "video", "image", "video", "broll", "motion-slide"),
            "intensityBase": 0.50,
            "intensitySpan": 0.26,
            "transitions": ["fade", "cross-zoom", "push", "wipe", "hard"],
            "brollTarget": 0.30,
            "stillTarget": 0.12,
        }
    if style_name == "balanced":
        return {
            "reset": 2.30,
            "pattern": ("video", "broll", "video", "image", "video", "motion-slide"),
            "intensityBase": 0.52,
            "intensitySpan": 0.30,
            "transitions": ["hard", "push", "fade", "wipe"],
            "brollTarget": 0.28,
            "stillTarget": 0.10,
        }
    return {
        # Keep high-energy visibly faster than cinematic while preserving readable Persian captions.
        "reset": 1.45,
        "pattern": ("video", "broll", "image", "video", "broll", "video", "motion-slide"),
        "intensityBase": 0.64,
        "intensitySpan": 0.34,
        "transitions": ["hard", "flash", "push", "cross-zoom", "wipe"],
        "brollTarget": 0.38,
        "stillTarget": 0.10,
    }


def _scene_kind(index: int, total: int, pattern: tuple[str, ...]) -> str:
    if index == total - 1:
        return "end-card"
    return pattern[index % len(pattern)]


def build_ad_storyboard(brief: dict[str, Any], duration_seconds: float, style: dict[str, Any]) -> dict[str, Any]:
    duration = max(5.0, float(duration_seconds))
    script = str(brief.get("voiceoverScript") or "").strip()
    phrases = _phrases(script)
    style_name = validated_edit_style(str(brief.get("editStyle") or "") or None)
    policy = _style_policy(style_name)
    reference_profile = _reference_profile(brief)
    reference_reset = _positive(reference_profile.get("visualResetTargetSeconds"), float(policy["reset"]), lower=1.25, upper=2.5)
    reset = max(1.25, min(2.5, min(float(style.get("visualResetSeconds") or policy["reset"]), float(policy["reset"]), reference_reset)))
    target_scenes = max(4, min(20, int(round(duration / reset))))

    expanded: list[str] = []
    while len(expanded) < target_scenes:
        expanded.extend(phrases)
    expanded = expanded[:target_scenes]

    hook_cap = _positive(reference_profile.get("hookMaxSeconds"), 1.65 if style_name == "high-energy" else 1.85, lower=0.8, upper=2.0)
    end_card_min = _positive(reference_profile.get("endCardMinSeconds"), 2.5, lower=1.8, upper=5.0)
    hook = min(hook_cap, max(0.85, duration * 0.10))
    cta = min(3.25, max(end_card_min, duration * 0.17))
    middle = max(0.2, duration - hook - cta)
    middle_count = max(1, target_scenes - 2)
    timings: list[tuple[float, float]] = [(0.0, hook)]
    cursor = hook
    for i in range(middle_count):
        end = hook + middle * (i + 1) / middle_count
        timings.append((cursor, end))
        cursor = end
    timings.append((max(cursor, duration - cta), duration))
    timings = timings[:target_scenes]
    if timings:
        timings[-1] = (timings[-1][0], duration)

    transitions = list(style.get("transitions") or policy["transitions"])
    if style_name == "high-energy":
        transitions = list(dict.fromkeys(["flash", "hard", "push", "cross-zoom", "wipe", *transitions]))
    elif style_name == "cinematic":
        transitions = list(dict.fromkeys(["fade", "cross-zoom", "push", "wipe", *transitions]))
    subject = str(brief.get("subject") or brief.get("presetId") or "heavy machinery")
    motifs = [str(item) for item in reference_profile.get("motifs", []) if str(item).strip()] or ["hook-impact", "hero-detail", "ui-proof", "numbered-benefit", "animated-end-card"]
    proof_badges = [str(item) for item in reference_profile.get("proofBadges", []) if str(item).strip()] or ["مشاهده دقیق", "مقایسه واقعی", "اقدام سریع"]
    scenes: list[dict[str, Any]] = []
    for index, ((start, end), copy) in enumerate(zip(timings, expanded)):
        kind = "motion-slide" if index == 0 else _scene_kind(index, len(timings), policy["pattern"])
        if index == 0:
            intensity = 0.98
        elif index == len(timings) - 1:
            intensity = 1.0
        else:
            intensity = float(policy["intensityBase"]) + float(policy["intensitySpan"]) * ((index % 4) / 3)
        transition = "flash" if index == 0 and style_name == "high-energy" else transitions[index % len(transitions)]
        motion = "punch" if intensity > 0.84 else ("pan-right" if index % 2 else "slow-push")
        if style_name == "cinematic" and intensity < 0.84:
            motion = "slow-push" if index % 2 == 0 else "pan-left"
        scene = {
            "id": f"ad-scene-{index + 1:02d}",
            "fromSeconds": round(start, 3),
            "toSeconds": round(max(start + 0.25, end), 3),
            "kind": kind,
            "copy": copy,
            "searchQuery": _intent_query(copy, subject),
            "transition": transition,
            "motion": motion,
            "caption": kind not in {"motion-slide", "end-card"},
            "suppressCaption": kind in {"motion-slide", "end-card"},
            "intensity": round(intensity, 3),
            "beatRole": "hook" if index == 0 else ("cta" if index == len(timings) - 1 else "body"),
            "editStyle": style_name,
            "referenceMotif": "hook-impact" if index == 0 else ("animated-end-card" if index == len(timings) - 1 else motifs[index % len(motifs)]),
            "proofBadge": None if index in {0, len(timings) - 1} else proof_badges[(index - 1) % len(proof_badges)],
        }
        if kind == "motion-slide":
            scene["title"] = str(brief.get("title") or copy or "کاریاب ماشین")[:80]
            scene["accentText"] = str(brief.get("subtitle") or "قبل از تصمیم، دقیق‌تر ببین")[:80]
            scene["kicker"] = "کاریاب ماشین"
        elif kind == "end-card":
            scene["title"] = str(brief.get("cta") or "در کاریاب ماشین ببین")[:80]
            scene["accentText"] = "karyabmashin.ir"
            scene["kicker"] = "ماشین‌آلات • خدمات • پروژه"
        scenes.append(scene)

    return {
        "package": "KBM-VIDEO-FACTORY-FULL-CINEMATIC-EDITORIAL-13",
        "version": "0.13.0",
        "durationSeconds": round(duration, 3),
        "visualResetTargetSeconds": reset,
        "subject": subject,
        "editStyle": style_name,
        "referenceEditingProfile": reference_profile,
        "scenes": scenes,
        "energyCurve": [scene["intensity"] for scene in scenes],
        "policy": {
            "maxUnchangedSeconds": min(2.5 if style_name != "high-energy" else 2.0, _positive(reference_profile.get("maxUnchangedSeconds"), 2.0, lower=1.25, upper=2.5)),
            "brollTargetRatio": policy["brollTarget"],
            "stillTargetRatio": policy["stillTarget"],
            "brandBug": True,
            "logoReveal": True,
            "endCard": True,
        },
    }
