#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from audio_critic import analyze_audio
from avalai_creative_client import chat_json, configured

PACKAGE = "KBM-VIDEO-FACTORY-AVALAI-LIVE-CREATIVE-HARDENING-13.1.1"
VERSION = "13.1.1"
AUTHORITY = "PEP-V41-BRAND-ASSET-PRESERVE-CRITIC-GATE-RESILIENCE-AUTHORITY"


def enabled() -> bool:
    flag = os.environ.get("KBM_PACKAGE131_AI_INTELLIGENCE", os.environ.get("KBM_PACKAGE131_CUPAI_INTELLIGENCE", "0"))
    return configured() and flag.strip().lower() in {"1", "true", "yes", "on"}


def _video_duration(video: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not video.is_file():
        return 0.0
    command = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video)]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=30)
        return max(0.0, float((result.stdout or "0").strip() or 0))
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def extract_contact_sheet_frames(video: Path, output_dir: Path, count: int = 6) -> list[Path]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not video.is_file():
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("frame-*.jpg"):
        old.unlink(missing_ok=True)

    sample_count = max(2, min(count, 8))
    duration = _video_duration(video)
    if duration > 0:
        safe_start = min(0.15, max(0.0, duration * 0.02))
        safe_end = max(safe_start, duration - min(0.08, duration * 0.01))
        span = max(0.0, safe_end - safe_start)
        times = [safe_start + span * i / (sample_count - 1) for i in range(sample_count)]
        for index, at_seconds in enumerate(times, start=1):
            destination = output_dir / f"frame-{index:02d}.jpg"
            command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{at_seconds:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", "-y", str(destination)]
            subprocess.run(command, check=False, timeout=45)
        return sorted(output_dir.glob("frame-*.jpg"))[:sample_count]

    pattern = output_dir / "frame-%02d.jpg"
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(video), "-vf", "fps=1/3,scale=480:-2", "-frames:v", str(sample_count), "-q:v", "5", str(pattern)]
    subprocess.run(command, check=False, timeout=90)
    return sorted(output_dir.glob("frame-*.jpg"))[:sample_count]


def direct_campaign(brief_text: str, frames: list[Path]) -> dict[str, Any]:
    prompt = f"""
Campaign brief in Persian:
{brief_text[:1000]}

Build a high-retention Instagram Reel plan for Karyab Mashin. Return JSON with exactly these keys:
title, subtitle, hook, cta, voiceoverScript, subject, campaignGoal, searchQueries, visualRules.
searchQueries must be 4-8 concise English B-roll search queries directly tied to the narration.
visualRules must contain maxUnchangedSeconds, brollTargetRatio, closeupTargetRatio, captionBottom.
Use Persian for title/subtitle/hook/cta/voiceoverScript. Do not invent technical specifications, prices, guarantees or facts not present in the brief/images.
The first 2 seconds must create tension or curiosity. CTA must be the final message and must contain a concrete next step such as viewing, comparing, checking or submitting on Karyab Mashin.
For premium advertising, the visual plan should deliberately mix hero, close-up/detail, operational and contextual shots instead of repeating the same wide shot.
""".strip()
    return chat_json(prompt, images=frames)


def refine_storyboard(storyboard: dict[str, Any], frames: list[Path], campaign: dict[str, Any]) -> dict[str, Any]:
    compact = [{k: s.get(k) for k in ("id", "kind", "copy", "searchQuery", "from", "to", "transition")} for s in storyboard.get("scenes", [])]
    prompt = f"""
You are refining a vertical 9:16 heavy-machinery commercial Reel.
Campaign JSON: {json.dumps(campaign, ensure_ascii=False)}
Current scenes: {json.dumps(compact, ensure_ascii=False)}
Return JSON with keys scenes and critique. scenes must preserve every existing scene id and from/to timing, but may improve kind, copy, searchQuery and transition.
Rules: make numbered promise delivery explicit; prefer close-up technical B-roll for each point; no full-screen dead cards when moving footage can carry text; final scene must be CTA/brand; transitions must be restrained and motivated; no invented facts.
""".strip()
    result = chat_json(prompt, images=frames)
    revised = result.get("scenes")
    if not isinstance(revised, list):
        return storyboard
    by_id = {str(x.get("id")): x for x in revised if isinstance(x, dict) and x.get("id")}
    output = dict(storyboard)
    scenes: list[dict[str, Any]] = []
    for original in storyboard.get("scenes", []):
        item = dict(original)
        patch = by_id.get(str(item.get("id")))
        if patch:
            for key in ("kind", "copy", "searchQuery", "transition"):
                value = patch.get(key)
                if isinstance(value, str) and value.strip():
                    item[key] = value.strip()[:260]
        scenes.append(item)
    output["scenes"] = scenes
    output["cupaiCritique"] = result.get("critique")
    return output


def _score(value: Any) -> float:
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _normalize_visual_evidence(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    counts = source.get("shotRoleCounts") if isinstance(source.get("shotRoleCounts"), dict) else {}
    normalized_counts = {role: max(0, int(counts.get(role) or 0)) for role in ("hero", "closeup", "detail", "operation", "context", "website", "cta")}
    required_booleans = ("thirdPartyWatermarkDetected", "duplicateBrandDetected", "brandPresent", "realWebsiteCapture")
    complete = all(isinstance(source.get(key), bool) for key in required_booleans)
    return {
        "evidenceComplete": complete,
        "thirdPartyWatermarkDetected": source.get("thirdPartyWatermarkDetected") if isinstance(source.get("thirdPartyWatermarkDetected"), bool) else None,
        "duplicateBrandDetected": source.get("duplicateBrandDetected") if isinstance(source.get("duplicateBrandDetected"), bool) else None,
        "brandPresent": source.get("brandPresent") if isinstance(source.get("brandPresent"), bool) else None,
        "realWebsiteCapture": source.get("realWebsiteCapture") if isinstance(source.get("realWebsiteCapture"), bool) else None,
        "visualStagnationRisk": source.get("visualStagnationRisk") if isinstance(source.get("visualStagnationRisk"), bool) else None,
        "shotRoleCounts": normalized_counts,
    }


def critique_final(video: Path, work: Path) -> dict[str, Any]:
    frames = extract_contact_sheet_frames(video, work / "cupai-final-frames", 8)
    audio = analyze_audio(video)
    (work / "package13-1-audio-evidence.json").write_text(json.dumps(audio, ensure_ascii=False, indent=2), encoding="utf-8")
    prompt = f"""
Score this finished Instagram Reel as a senior international commercial editor. Return JSON only with:
overall, hook, pacing, brollRelevance, shotVariety, brandVisibility, captionReadability, audioEnergy, ctaStrength, publishReady, actions, visualEvidence.
Every score is 0-10. actions is an array of maximum 5 concise repair instructions.
visualEvidence must be an object with exactly these keys:
thirdPartyWatermarkDetected, duplicateBrandDetected, brandPresent, realWebsiteCapture, visualStagnationRisk, shotRoleCounts.
The first five fields are booleans. shotRoleCounts is an object with integer keys hero, closeup, detail, operation, context, website, cta counted only from the supplied sampled frames.
Mark realWebsiteCapture true only when the sampled frames visibly show the actual Karyab Mashin website/URL or unmistakable first-party site UI; do not mark generic mockups as real website capture.
Mark thirdPartyWatermarkDetected true if a third-party editing/tool watermark or unrelated watermark is visibly present.
Mark duplicateBrandDetected true when duplicated or conflicting Karyab Mashin logo/brand lockups visibly reduce polish.
Judge visual criteria only from the supplied frames. Do not infer unheard audio from still images.
For audioEnergy, use only the measured audio evidence below.
Measured audio evidence:
{json.dumps(audio, ensure_ascii=False)}
Do not invent product facts. publishReady requires overall >= 8 and no major brand, CTA or audio failure.
""".strip()
    try:
        result = chat_json(prompt, images=frames, attempts=3)
    except Exception as exc:
        return {
            "overall": 0.0, "hook": 0.0, "pacing": 0.0, "brollRelevance": 0.0, "shotVariety": 0.0,
            "brandVisibility": 0.0, "captionReadability": 0.0, "audioEnergy": _score(audio.get("technicalAudioScore")),
            "ctaStrength": 0.0, "publishReady": False,
            "actions": ["Critic evaluation unavailable; rerun when AvalAI critic capacity is available."],
            "visualEvidence": _normalize_visual_evidence({}), "criticComplete": False,
            "criticError": f"{type(exc).__name__}: {str(exc)[-320:]}", "authority": AUTHORITY,
            "package": PACKAGE, "version": VERSION, "frameCount": len(frames), "frameSampling": "even-plus-end",
            "criticRequestAttempts": 3, "audioEvidence": audio,
        }

    result["audioEnergy"] = _score(audio.get("technicalAudioScore"))
    result["visualEvidence"] = _normalize_visual_evidence(result.get("visualEvidence"))
    metric_names = ("hook", "pacing", "brollRelevance", "shotVariety", "brandVisibility", "captionReadability", "audioEnergy", "ctaStrength")
    scores = [_score(result.get(name)) for name in metric_names]
    result["overall"] = round(sum(scores) / len(scores), 2) if scores else 0.0
    result["publishReady"] = bool(result["overall"] >= 8.0 and _score(result.get("brandVisibility")) >= 7.0 and _score(result.get("ctaStrength")) >= 7.0 and _score(result.get("audioEnergy")) >= 6.0)
    result.update({
        "criticComplete": True,
        "authority": AUTHORITY,
        "package": PACKAGE,
        "version": VERSION,
        "frameCount": len(frames),
        "frameSampling": "even-plus-end",
        "criticRequestAttempts": 3,
        "audioEvidence": audio,
    })
    return result


def apply_bounded_repairs(props: dict[str, Any], critique: dict[str, Any]) -> dict[str, Any]:
    repaired = dict(props)
    editorial = dict(repaired.get("editorial") or {})
    previous_pass = max(0, int(editorial.get("repairPass") or 0))
    repair_pass = min(2, previous_pass + 1)

    flags = {
        "hook": _score(critique.get("hook")) < 8.2,
        "pacing": _score(critique.get("pacing")) < 8.0,
        "broll": _score(critique.get("brollRelevance")) < 8.3,
        "shotVariety": _score(critique.get("shotVariety")) < 8.0,
        "caption": _score(critique.get("captionReadability")) < 8.3,
        "cta": _score(critique.get("ctaStrength")) < 8.3,
        "brand": _score(critique.get("brandVisibility")) < 8.3,
        "stagnation": bool((critique.get("visualEvidence") or {}).get("visualStagnationRisk")) if isinstance(critique.get("visualEvidence"), dict) else False,
    }

    profile = dict(repaired.get("captionProfile") or {})
    if flags["caption"]:
        profile["bottom"] = max(330 if repair_pass >= 2 else 310, int(profile.get("bottom") or 270))
        profile["outlinePx"] = max(5, int(profile.get("outlinePx") or 3))
        profile["pill"] = True
        if profile.get("fontSize"):
            profile["fontSize"] = min(int(profile.get("fontSize") or 52), 50 if repair_pass >= 2 else 52)
    repaired["captionProfile"] = profile

    brand = dict(repaired.get("brand") or {})
    if flags["brand"]:
        brand["requireLogo"] = True
        brand["logoReveal"] = True
        brand["endCard"] = True
        brand["endCardRequired"] = True
        brand["prominence"] = "strong"
    # CAMP remains single-lockup: no duplicate persistent legacy watermark.
    brand["persistentBug"] = False
    repaired["brand"] = brand

    if flags["cta"]:
        vertical = str((repaired.get("camp") or {}).get("vertical") or "") if isinstance(repaired.get("camp"), dict) else ""
        repaired["cta"] = (
            "همین حالا در KARYABMASHIN.IR آگهی فروش را ثبت کن"
            if vertical == "machine-sale"
            else "همین حالا در KARYABMASHIN.IR بررسی کن"
        )

    editorial["cupaiCritic"] = critique
    editorial["repairPass"] = repair_pass
    editorial["repairFlags"] = flags
    editorial["repairActions"] = list(critique.get("actions") or [])[:5]
    editorial["repairAuthority"] = "KBM-CAMP-HOTFIX05-PROGRESSIVE-REPAIR-AUTHORITY"
    if flags["pacing"] or flags["shotVariety"] or flags["stagnation"]:
        editorial["maxUnchangedSeconds"] = 1.85 if repair_pass >= 2 else 2.05
    repaired["editorial"] = editorial
    return repaired
