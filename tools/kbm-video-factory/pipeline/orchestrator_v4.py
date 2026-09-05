#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ad_editorial_director import build_ad_storyboard
from ad_script_writer import write_ad_brief
from asset_router import route_assets
from audio_mastering import master_for_reels
from brand_director import resolve_brand
from broll_scout import scout
from caption_director_fa import professionalize
from editorial_critic import score as editorial_score
from quality_control import inspect_output
from render_router import render as render_with_fallback
from sound_designer_v2 import build_sound_plan
from style_dna_compiler import compile_style_dna, load_registry
from timeline_compiler import compile_timeline, maybe_export_otio

PACKAGE = "KBM-VIDEO-FACTORY-FULL-CINEMATIC-EDITORIAL-13"
VERSION = "0.13.0"
EDIT_STYLES = {"balanced", "cinematic", "high-energy"}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _arg_value(args: list[str], name: str, default: str) -> str:
    try:
        return args[args.index(name) + 1]
    except (ValueError, IndexError):
        return default


def _replace_arg(args: list[str], name: str, value: str) -> list[str]:
    result = list(args)
    while name in result:
        index = result.index(name)
        del result[index:index + 2]
    result.extend([name, value])
    return result


def _decode_campaign_brief(encoded: str) -> str:
    value = encoded.strip()
    if not value:
        return ""
    if len(value) > 1600 or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for ch in value):
        raise ValueError("campaign brief encoding is invalid")
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        text = raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("campaign brief encoding is invalid") from exc
    text = " ".join(text.replace("\x00", " ").split())
    if len(text) > 600:
        raise ValueError("campaign brief is too long")
    return text


def _enabled(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "off", "no", "disabled"}


def _run_v2(root: Path, args: list[str]) -> int:
    command = [sys.executable, str(root / "pipeline" / "orchestrator_v2.py"), *args]
    if "--no-render" not in command:
        command.append("--no-render")
    return subprocess.run(command, cwd=root, check=False).returncode


def _safe_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _caption_profile(root: Path, style: dict[str, Any]) -> dict[str, Any]:
    profiles = _safe_json(root / "config" / "caption-profiles.json", {})
    selected = profiles.get(style.get("captionProfile")) if isinstance(profiles, dict) else None
    if isinstance(selected, dict):
        return selected
    if isinstance(profiles, dict):
        fallback = profiles.get("KBM-CAPTION-BOLD-INDUSTRIAL")
        if isinstance(fallback, dict):
            return fallback
    return {
        "fontSize": 64,
        "hookFontSize": 76,
        "minFontSize": 44,
        "maxFontSize": 78,
        "maxWords": 5,
        "maxLines": 2,
        "bottom": 270,
        "outlinePx": 3,
        "activeScale": 1.08,
        "pill": True,
        "accent": "#F4B400",
    }


def _sound_profile(root: Path, style: dict[str, Any]) -> dict[str, Any]:
    profiles = _safe_json(root / "config" / "sound-design-profiles.json", {})
    selected = profiles.get(style.get("soundProfile")) if isinstance(profiles, dict) else None
    if isinstance(selected, dict):
        return selected
    if isinstance(profiles, dict):
        fallback = profiles.get("industrial-pro")
        if isinstance(fallback, dict):
            return fallback
    return {"targetLufs": -14, "truePeakDb": -1.0, "events": {}}


def _style(root: Path, edit_style: str) -> tuple[str, dict[str, Any]]:
    profile_id, registry_profile = load_registry(root, None)
    style = dict(compile_style_dna([], registry_profile, profile_id))
    reset_targets = {"balanced": 2.25, "cinematic": 1.90, "high-energy": 1.55}
    style["visualResetSeconds"] = reset_targets.get(edit_style, 1.55)
    style["brollDensity"] = "high" if edit_style != "balanced" else "medium"
    transitions = list(style.get("transitions") or [])
    if len(transitions) < 4:
        transitions = ["hard", "push", "flash", "cross-zoom", "wipe", "fade"]
    style["transitions"] = transitions
    style["editStyle"] = edit_style
    return profile_id, style


def _rights_summary(rights: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "approved": sum(1 for row in rights if row.get("rightsApproved")),
        "materialized": sum(1 for row in rights if row.get("materialized")),
        "rejected": len(rejected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--disable-media-research", action="store_true")
    parser.add_argument("--disable-media-materialization", action="store_true")
    parser.add_argument("--campaign-brief-b64", default="")
    parser.add_argument("--edit-style", choices=sorted(EDIT_STYLES), default="high-energy")
    pro, base_args = parser.parse_known_args()

    root = Path(__file__).resolve().parents[1]
    job = _arg_value(base_args, "--job", "kbm-full-cinematic")
    job = "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in job).strip("-")[:80] or "kbm-full-cinematic"
    work = root / "work" / job
    public_job = root / "public" / "generated" / job
    report_path = work / "package13-report.json"
    states: list[dict[str, Any]] = []

    try:
        campaign_brief = _decode_campaign_brief(pro.campaign_brief_b64)
    except ValueError as exc:
        _write(report_path, {"package": PACKAGE, "version": VERSION, "job": job, "rendered": False, "states": [{"stage": "campaign-brief", "state": "FAILED", "reason": str(exc)}]})
        return 21

    custom_brief = write_ad_brief(campaign_brief, {}, pro.edit_style) if campaign_brief else {}
    effective_args = list(base_args)
    # A supplied TTS take is only valid against the exact script used to create it.
    # Never let the campaign copywriter replace that script downstream: ASR, captions
    # and pronunciation review must have one source of truth.
    explicit_voiceover_script = _arg_value(base_args, "--voiceover-script", "").strip()
    if custom_brief:
        if explicit_voiceover_script:
            custom_brief["voiceoverScript"] = explicit_voiceover_script
        else:
            effective_args = _replace_arg(effective_args, "--voiceover-script", str(custom_brief.get("voiceoverScript") or ""))
        effective_args = _replace_arg(effective_args, "--title", str(custom_brief.get("title") or "کاریاب ماشین"))
        effective_args = _replace_arg(effective_args, "--subtitle", str(custom_brief.get("subtitle") or ""))
        effective_args = _replace_arg(effective_args, "--cta", str(custom_brief.get("cta") or "مشاهده در کاریاب ماشین"))
        states.append({"stage": "campaign-copywriter", "state": "PASS", "goal": custom_brief.get("campaignGoal"), "subject": custom_brief.get("subject")})
    else:
        states.append({"stage": "campaign-copywriter", "state": "FALLBACK", "reason": "no custom campaign brief"})

    rc = _run_v2(root, effective_args)
    if rc != 0:
        _write(report_path, {"package": PACKAGE, "version": VERSION, "job": job, "rendered": False, "states": states + [{"stage": "base-editor", "state": "FAILED", "code": rc}]})
        return rc
    states.append({"stage": "base-editor", "state": "PASS"})

    base_report = _safe_json(work / "job-report.json", {})
    props_path = work / "render-props.json"
    props = _safe_json(props_path, {})
    brief = _safe_json(work / "creative-brief.json", {})
    if custom_brief and isinstance(brief, dict):
        brief.update(custom_brief)
        _write(work / "creative-brief.json", brief)
    if not isinstance(props, dict) or not props:
        _write(report_path, {"package": PACKAGE, "version": VERSION, "job": job, "rendered": False, "states": states + [{"stage": "render-props", "state": "FAILED"}]})
        return 20

    duration_frames = int(props.get("durationInFrames") or 1)
    duration_seconds = max(0.1, duration_frames / 30.0)
    profile_id, style = _style(root, pro.edit_style)
    _write(work / "package13-style.json", style)
    states.append({"stage": "style-director", "state": "PASS", "styleId": profile_id, "editStyle": pro.edit_style})

    storyboard = build_ad_storyboard(brief if isinstance(brief, dict) else {}, duration_seconds, style)
    _write(work / "package13-storyboard.json", storyboard)
    states.append({"stage": "advertising-story-director", "state": "PASS", "scenes": len(storyboard.get("scenes", []))})

    media_enabled = _enabled("KBM_PACKAGE13_MEDIA_RESEARCH", True) and not pro.disable_media_research
    materialize = _enabled("KBM_PACKAGE13_MATERIALIZE_MEDIA", True) and not pro.disable_media_materialization
    scout_report = scout(storyboard, enabled=media_enabled)
    _write(work / "package13-media-research.json", scout_report)
    states.append({
        "stage": "media-research",
        "state": "PASS" if scout_report.get("candidates") else "FALLBACK",
        "approvedCandidates": len(scout_report.get("candidates", [])),
        "rejectedByRights": len(scout_report.get("rejected", [])),
    })

    asset_report = route_assets(scout_report, public_job / "external", materialize=materialize)
    for asset in asset_report.get("assets", []):
        if asset.get("src"):
            asset["src"] = f"generated/{job}/external/{asset['src']}"
    _write(work / "package13-rights-manifest.json", asset_report.get("rights", []))
    _write(work / "package13-asset-routing.json", asset_report)
    states.append({"stage": "asset-router", "state": "PASS" if asset_report.get("assets") else "FALLBACK", "assets": len(asset_report.get("assets", []))})

    brand_report = resolve_brand(root, public_job)
    _write(work / "package13-brand-report.json", brand_report)
    if brand_report.get("ready"):
        states.append({"stage": "brand-authority", "state": "PASS", "source": brand_report.get("source")})
        if isinstance(brand_report.get("asset"), dict):
            asset_report.setdefault("assets", []).append(brand_report["asset"])
    else:
        states.append({"stage": "brand-authority", "state": "WARNING", "code": "BRAND_ASSET_MISSING", "reason": brand_report.get("reason")})

    compiled = compile_timeline(storyboard, asset_report, fps=30)
    _write(work / "package13-timeline.json", compiled)
    otio = maybe_export_otio(compiled, work / "package13-timeline.otio")
    states.append({"stage": "timeline-compiler", "state": "PASS", "otio": otio.get("status")})

    caption_profile = _caption_profile(root, style)
    pro_captions = professionalize(list(props.get("captions") or []), caption_profile)
    sound_profile = _sound_profile(root, style)
    sound = build_sound_plan(storyboard, sound_profile)
    sound["energyCurve"] = storyboard.get("energyCurve") or []
    _write(work / "package13-sound-design.json", sound)

    rights = list(asset_report.get("rights") or [])
    rejected = list(scout_report.get("rejected") or [])
    rights_summary = _rights_summary(rights, rejected)
    editorial_config = {
        "package": PACKAGE,
        "version": VERSION,
        "energyCurve": storyboard.get("energyCurve") or [],
        "maxUnchangedSeconds": (storyboard.get("policy") or {}).get("maxUnchangedSeconds", 2.5),
        "brollTargetRatio": (storyboard.get("policy") or {}).get("brollTargetRatio", 0.35),
        "stillTargetRatio": (storyboard.get("policy") or {}).get("stillTargetRatio", 0.10),
        "referenceEditingProfile": storyboard.get("referenceEditingProfile") or {},
        "rightsApproved": rights_summary["approved"],
        "rightsRejected": rights_summary["rejected"],
    }

    props.update({
        "title": str((brief if isinstance(brief, dict) else {}).get("title") or props.get("title") or "کاریاب ماشین"),
        "subtitle": str((brief if isinstance(brief, dict) else {}).get("subtitle") or props.get("subtitle") or ""),
        "cta": str((brief if isinstance(brief, dict) else {}).get("cta") or props.get("cta") or "مشاهده در کاریاب ماشین"),
        "captions": pro_captions,
        "captionPolicy": "single-lane",
        "captionProfile": caption_profile,
        "scenes": compiled.get("scenes", []),
        "assets": compiled.get("assets", []),
        "brand": brand_report.get("config") or {"logoAssetId": "kbm-brand-logo", "requireLogo": True},
        "editorial": editorial_config,
        "soundDesign": sound,
        "proEditDesk": {
            "enabled": True,
            "package": PACKAGE,
            "version": VERSION,
            "styleId": profile_id,
            "visualResetSeconds": style.get("visualResetSeconds"),
            "referenceCount": 0,
            "brollEnabled": bool(asset_report.get("assets")),
        },
    })
    _write(props_path, props)
    states.append({"stage": "caption-director", "state": "PASS", "captions": len(pro_captions)})
    states.append({"stage": "sound-director", "state": "PASS", "cues": len(sound.get("cues") or [])})

    thresholds = _safe_json(root / "config" / "editorial-thresholds.json", {})
    pre_score = editorial_score(props, style, rights, thresholds if isinstance(thresholds, dict) else {})
    _write(work / "package13-editorial-preflight.json", pre_score)

    source = Path(str(base_report.get("effectiveSource") or "")).expanduser().resolve()
    output = Path(str(base_report.get("output") or root / "out" / f"{job}.mp4")).expanduser().resolve()
    report: dict[str, Any] = {
        "package": PACKAGE,
        "version": VERSION,
        "job": job,
        "rendered": False,
        "pipelineMode": "v4",
        "editStyle": pro.edit_style,
        "campaignBriefProvided": bool(campaign_brief),
        "styleId": profile_id,
        "mediaResearch": scout_report.get("researchSummary") or {},
        "rights": rights_summary,
        "brandReady": bool(brand_report.get("ready")),
        "brandSource": brand_report.get("source"),
        "states": states,
        "preflight": pre_score,
    }

    try:
        render_report, remotion_error = render_with_fallback(
            root=root,
            source=source,
            props_path=props_path,
            template=str(props.get("templateId") or "KBM-V03-MACHINE-REVIEW"),
            output=output,
            duration_frames=duration_frames,
            allow_remotion=True,
        )
        report["rendered"] = True
        report["renderer"] = render_report
        states.append({"stage": "cinematic-render", "state": "FALLBACK" if remotion_error else "PASS", "reason": remotion_error[-300:] if remotion_error else None})
    except Exception as exc:
        states.append({"stage": "cinematic-render", "state": "FAILED", "reason": str(exc)[-500:]})
        report["states"] = states
        _write(report_path, report)
        return 13

    try:
        master = master_for_reels(output, target_lufs=float(sound.get("targetLufs") or -14), true_peak=float(sound.get("truePeakDb") or -1.0))
        report["audioMaster"] = master
        states.append({"stage": "audio-master", "state": str(master.get("status") or "PASS")})
    except Exception as exc:
        states.append({"stage": "audio-master", "state": "WARNING", "reason": str(exc)[-360:]})

    try:
        qc = inspect_output(output)
        report["qc"] = qc
        states.append({"stage": "quality-control", "state": "PASS" if qc.get("pass") else "WARNING"})
    except Exception as exc:
        states.append({"stage": "quality-control", "state": "WARNING", "reason": str(exc)[-360:]})

    editorial = editorial_score(props, style, rights, thresholds if isinstance(thresholds, dict) else {})
    report["editorial"] = editorial
    report["states"] = states
    report["output"] = str(output)
    _write(work / "package13-editorial-report.json", editorial)
    _write(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
