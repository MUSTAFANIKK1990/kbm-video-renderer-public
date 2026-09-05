#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

MAX_BRIEF_CHARS = 600
ALLOWED_EDIT_STYLES = {"balanced", "cinematic", "high-energy"}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!؟!؛])\s+|\s*[؛]\s*")
QUALITY_PROFILE_PATH = Path(__file__).resolve().parents[1] / "config" / "persian-cinematic-quality.json"
DEFAULT_REFERENCE_EDITING_PROFILE: dict[str, Any] = {
    "profileId": "kbm-reference-reel-v1",
    "authority": "KBM-REFERENCE-REEL-EDITING-GRAMMAR-01",
    "sourcePolicy": "Derived editing grammar only; never reuse supplied reference media, logos, watermarks, or audio.",
    "hookMaxSeconds": 1.5,
    "visualResetTargetSeconds": 1.55,
    "maxUnchangedSeconds": 2.0,
    "endCardMinSeconds": 2.5,
    "caption": {"maxWords": 5, "maxLines": 2, "entrance": "kinetic", "placement": "safe-lower-third"},
    "motifs": ["hook-impact", "hero-detail", "ui-proof", "numbered-benefit", "animated-end-card"],
    "soundCues": ["impact", "whoosh", "click", "rise"],
    "proofBadges": ["مشاهده دقیق", "مقایسه واقعی", "اقدام سریع"],
}


def reference_editing_profile() -> dict[str, Any]:
    """Load the rights-clean editing grammar used by the topic-to-reel pipeline."""
    profile = json.loads(json.dumps(DEFAULT_REFERENCE_EDITING_PROFILE, ensure_ascii=False))
    try:
        document = json.loads(QUALITY_PROFILE_PATH.read_text(encoding="utf-8"))
        candidate = document.get("referenceEditingProfile") if isinstance(document, dict) else None
    except (OSError, json.JSONDecodeError):
        candidate = None
    if not isinstance(candidate, dict):
        return profile
    for key in ("profileId", "authority", "sourcePolicy"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            profile[key] = value.strip()[:240]
    for key, lower, upper in (
        ("hookMaxSeconds", 0.8, 2.0),
        ("visualResetTargetSeconds", 1.25, 2.5),
        ("maxUnchangedSeconds", 1.25, 2.5),
        ("endCardMinSeconds", 1.8, 5.0),
    ):
        try:
            value = float(candidate.get(key))
        except (TypeError, ValueError):
            continue
        if lower <= value <= upper:
            profile[key] = round(value, 3)
    value = candidate.get("caption")
    if isinstance(value, dict):
        profile["caption"] = {**profile["caption"], **{name: item for name, item in value.items() if isinstance(name, str)}}
    for key in ("motifs", "soundCues", "proofBadges"):
        value = candidate.get(key)
        if isinstance(value, list):
            cleaned = [str(item).strip()[:80] for item in value if str(item).strip()]
            if cleaned:
                profile[key] = cleaned[:8]
    return profile


def decode_campaign_brief(value: str | None = None) -> str:
    encoded = (value if value is not None else os.environ.get("CAMPAIGN_BRIEF_B64", "")).strip()
    if not encoded:
        return ""
    if len(encoded) > 1600 or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        raise ValueError("Campaign brief encoding is invalid")
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
        text = raw.decode("utf-8", errors="strict").replace("\x00", " ").strip()
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Campaign brief encoding is invalid") from exc
    if not text or len(text) > MAX_BRIEF_CHARS:
        raise ValueError("Campaign brief length is invalid")
    return text


def validated_edit_style(value: str | None = None) -> str:
    style = (value if value is not None else os.environ.get("EDIT_STYLE", "high-energy")).strip().lower() or "high-energy"
    if style not in ALLOWED_EDIT_STYLES:
        raise ValueError("Edit style is invalid")
    return style


def _sentences(text: str) -> list[str]:
    parts = [part.strip(" \n\t،؛.") for part in _SENTENCE_SPLIT.split(text) if part.strip(" \n\t،؛.")]
    return parts or [text.strip()]


def _subject(text: str) -> str:
    lower = text.lower()
    rules = (
        (("بیل", "excavator"), "excavator"),
        (("لودر", "loader"), "loader"),
        (("جرثقیل", "crane"), "crane"),
        (("معدن", "mining"), "mining-machinery"),
        (("راهسازی", "road"), "road-construction"),
        (("قطعه", "لوازم", "spare"), "heavy-equipment-parts"),
        (("تعمیر", "سرویس", "maintenance"), "heavy-equipment-maintenance"),
        (("پیمانکار", "پیمانکاری", "contractor"), "industrial-contractor"),
    )
    for needles, subject in rules:
        if any(needle in lower for needle in needles):
            return subject
    return "industrial-machinery"


def build_campaign_plan(text: str, duration_seconds: float, fps: int = 30) -> dict[str, Any]:
    brief = text.strip()
    if not brief:
        raise ValueError("Campaign brief is empty")
    duration = max(5.0, float(duration_seconds))
    grammar = reference_editing_profile()
    sentences = _sentences(brief)
    hook = sentences[0][:100]
    body = " ".join(sentences[:4]).strip()
    if len(body) > 430:
        body = body[:427].rstrip() + "..."
    voiceover = (f"{body} " "برای انتخاب و بررسی گزینه‌های مرتبط، آگهی‌ها و خدمات کاریاب ماشین را ببینید.").strip()
    hook_end = min(duration, min(float(grammar["hookMaxSeconds"]), max(0.9, duration * 0.10)))
    cta_seconds = max(float(grammar["endCardMinSeconds"]), min(3.2, duration * 0.20))
    cta_start = max(hook_end, duration - cta_seconds)
    return {
        "package": "KBM-VIDEO-FACTORY-FULL-CINEMATIC-EDITORIAL-13",
        "version": "0.13.1",
        "presetId": "auto-commercial",
        "subject": _subject(brief),
        "language": "fa-IR",
        "durationSeconds": round(duration, 3),
        "fps": int(fps),
        "title": hook or "کاریاب ماشین",
        "subtitle": "تدوین تبلیغاتی هوشمند",
        "cta": "در کاریاب ماشین ببین",
        "voiceoverScript": voiceover,
        "musicProfile": "industrial-cinematic-ad",
        "campaignBrief": brief,
        "editStyle": validated_edit_style(),
        "referenceEditingProfile": grammar,
        "overlays": [
            {"from": 0, "to": max(1, int(round(hook_end * fps))), "fromSeconds": 0.0, "toSeconds": round(hook_end, 3), "kind": "hook", "eyebrow": "کاریاب ماشین", "text": hook or "کاریاب ماشین", "accentText": "موضوع را سریع و واضح ببین", "position": "top"},
            {"from": int(round(cta_start * fps)), "to": max(int(round(cta_start * fps)) + 1, int(round(duration * fps))), "fromSeconds": round(cta_start, 3), "toSeconds": round(duration, 3), "kind": "cta", "eyebrow": "کاریاب ماشین", "text": "گزینه‌های مرتبط را مقایسه کن", "accentText": "karyabmashin.ir", "position": "center"},
        ],
        "sfxCues": [
            {"atSeconds": 0.12, "type": "hit", "volume": 0.62},
            {"atSeconds": round(max(0.4, hook_end - 0.25), 3), "type": "whoosh", "volume": 0.48},
            {"atSeconds": round(min(cta_start - 0.45, hook_end + float(grammar["visualResetTargetSeconds"])), 3), "type": "click", "volume": 0.34},
            {"atSeconds": round(cta_start, 3), "type": "rise", "volume": 0.50},
        ],
        "fallback": False,
        "authority": "package13-campaign-brief",
    }
