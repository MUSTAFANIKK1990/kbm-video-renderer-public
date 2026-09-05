#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from avalai_creative_intelligence import apply_bounded_repairs, critique_final, direct_campaign, enabled, extract_contact_sheet_frames, refine_storyboard
from avalai_voice_director import direct_voice
from brand_director import KNOWN_REPO_PATHS
from campaign_brief import decode_campaign_brief
from ingest import duration_seconds, probe
from render_router import render as render_with_fallback
from timeline_compiler import compile_timeline

PACKAGE = "KBM-VIDEO-FACTORY-CUPAI-LIVE-CREATIVE-HARDENING-13.1.1"
VERSION = "13.1.1"
AUTHORITY = "PEP-V41-EDITORIAL-CTA-BRAND-TTS-DURATION-AUTHORITY"


def _arg(args: list[str], name: str, default: str = "") -> str:
    try:
        return args[args.index(name) + 1]
    except (ValueError, IndexError):
        return default


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _replace(args: list[str], name: str, value: str) -> list[str]:
    result = list(args)
    while name in result:
        i = result.index(name)
        del result[i:i + 2]
    result += [name, value]
    return result


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _campaign_text(plan: dict[str, Any], fallback: str) -> str:
    parts = [str(plan.get(k) or "").strip() for k in ("hook", "title", "subtitle", "voiceoverScript", "cta")]
    text = " | ".join(x for x in parts if x)
    return (text or fallback)[:600]


def _actionable_cta(plan: dict[str, Any]) -> str:
    current = " ".join(str(plan.get("cta") or "").split()).strip()
    action_tokens = ("ببین", "مشاهده", "بررسی", "مقایسه", "ثبت", "مراجعه", "انتخاب")
    has_action = any(token in current for token in action_tokens)
    has_destination = "کاریاب ماشین" in current or "KARYABMASHIN.IR" in current.upper()
    if has_action and has_destination:
        return current[:180]
    if current:
        return f"{current.rstrip(' .؛')} — گزینه‌ها را در KARYABMASHIN.IR ببین."[:180]
    return "گزینه‌ها را در KARYABMASHIN.IR ببین."


def _fallback_campaign(brief: str) -> dict[str, Any]:
    lower = brief.lower()
    if "اجاره" in lower and any(token in lower for token in ("معامله", "خرید", "فروش")):
        voiceover = "وضعیت واقعی دستگاه را ببین، پیش از اجاره یا معامله بررسی فنی را جدی بگیر و گزینه‌ها را در کاریاب ماشین مقایسه کن."
    elif "اجاره" in lower:
        voiceover = "وضعیت واقعی دستگاه را ببین، پیش از اجاره جزئیات را بررسی کن و گزینه‌ها را در کاریاب ماشین مقایسه کن."
    elif any(token in lower for token in ("معامله", "خرید", "فروش")):
        voiceover = "وضعیت واقعی دستگاه را ببین، پیش از معامله جزئیات را بررسی کن و گزینه‌ها را در کاریاب ماشین مقایسه کن."
    else:
        voiceover = "محتوای واقعی را دقیق ببین، جزئیات را بررسی کن و گزینه‌های مرتبط را در کاریاب ماشین مقایسه کن."
    return {
        "title": "کاریاب ماشین",
        "subtitle": "بررسی آگاهانه ماشین‌آلات",
        "voiceoverScript": voiceover,
        "cta": "گزینه‌ها را در KARYABMASHIN.IR ببین.",
        "fallback": True,
        "authority": AUTHORITY,
    }


def _voice_bounds(max_seconds: float) -> tuple[float, float, float]:
    maximum = max(5.0, float(max_seconds))
    target = max(4.0, min(maximum * 0.72, maximum - 1.0))
    ceiling = max(3.0, min(maximum - 0.35, target * 1.18))
    floor = max(2.5, target * 0.50)
    return target, floor, ceiling


def _promote_gateway_voice(work: Path, prior: dict[str, Any], max_seconds: float) -> tuple[dict[str, Any], dict[str, Any] | None]:
    report = _safe_json(work / "voice-report.json", {})
    if not isinstance(report, dict) or report.get("engine") != "avalai-gateway":
        return prior, None
    selected_path = Path(str(report.get("output") or "")).expanduser()
    if not selected_path.is_file():
        return prior, {
            "stage": "avalai-voice-gateway-fallback",
            "state": "DEGRADED",
            "reason": "Gateway report exists but generated audio is missing",
        }
    try:
        selected_duration = float(duration_seconds(probe(selected_path)))
    except Exception as exc:
        return prior, {
            "stage": "avalai-voice-gateway-fallback",
            "state": "DEGRADED",
            "reason": str(exc)[-400:],
        }

    target, floor, ceiling = _voice_bounds(max_seconds)
    duration_fit = floor <= selected_duration <= ceiling
    script = " ".join(str(report.get("script") or "").split()).strip()
    promoted = {
        "engine": "avalai-gateway-fallback",
        "provider": "AvalAI",
        "voice": report.get("voice"),
        "requestedTakeCount": 1,
        "takeCount": 1,
        "complete": True,
        "durationFit": duration_fit,
        "targetSeconds": round(target, 3),
        "durationFloorSeconds": round(floor, 3),
        "durationCeilingSeconds": round(ceiling, 3),
        "selectedDuration": round(selected_duration, 3),
        "durationDeltaSeconds": round(selected_duration - target, 3),
        "scriptOriginal": script,
        "scriptUsed": script,
        "scriptFit": {
            "compacted": False,
            "method": "package13-base-campaign-writer",
            "wordBudget": None,
            "originalWords": len(script.split()),
            "fittedWords": len(script.split()),
        },
        "selectedTake": "gateway",
        "selectedPath": str(selected_path),
        "takes": [{
            "take": "gateway",
            "model": report.get("model"),
            "voice": report.get("voice"),
            "duration": round(selected_duration, 3),
            "bytes": report.get("sizeBytes"),
            "path": str(selected_path),
            "contentType": report.get("contentType"),
        }],
        "failures": [],
        "fallbackFrom": {
            "engine": prior.get("engine"),
            "complete": prior.get("complete"),
            "durationFit": prior.get("durationFit"),
            "failures": prior.get("failures", []),
        },
    }
    _write(work / "package13-1-voice-manifest.json", promoted)
    state = {
        "stage": "avalai-voice-gateway-fallback",
        "state": "PASS" if duration_fit else "DEGRADED",
        "selectedDuration": promoted["selectedDuration"],
        "targetSeconds": promoted["targetSeconds"],
        "durationFit": duration_fit,
        "engine": promoted["engine"],
    }
    return promoted, state


def _critic_state(critic: dict[str, Any]) -> str:
    return "PASS" if critic.get("criticComplete") is True else "BLOCKED"


def _brand_preflight(root: Path) -> dict[str, Any]:
    local = os.environ.get("KBM_BRAND_LOGO_LOCAL", "").strip()
    if local and Path(local).expanduser().is_file():
        return {"configured": True, "source": "local-env"}
    repo_root = root.parents[1]
    for relative in KNOWN_REPO_PATHS:
        if (repo_root / relative).is_file():
            return {"configured": True, "source": "repository", "path": relative}
    remote = os.environ.get("KBM_BRAND_LOGO_URL", "").strip()
    if remote.startswith("https://"):
        return {"configured": True, "source": "remote"}
    return {"configured": False, "source": "missing", "reason": "Official KBM logo source is not configured"}


def _brand_required() -> bool:
    return os.environ.get("KBM_PACKAGE131_REQUIRE_BRAND", "1").strip().lower() not in {"0", "false", "no", "off"}


def _final_report(*, output_path: Path, original_brief: str, campaign: dict[str, Any], voice_manifest: dict[str, Any], critic: dict[str, Any], base: dict[str, Any], states: list[dict[str, Any]], mode: str, brand_preflight: dict[str, Any], gate_pass: bool) -> dict[str, Any]:
    return {
        "package": PACKAGE,
        "version": VERSION,
        "authority": AUTHORITY,
        "pipelineMode": "v41",
        "mode": mode,
        "rendered": bool(output_path.is_file() and gate_pass),
        "output": str(output_path),
        "cupaiConfigured": enabled(),
        "campaignBriefProvided": bool(original_brief),
        "campaign": campaign,
        "voiceDirector": voice_manifest,
        "critic": critic,
        "brandPreflight": brand_preflight,
        "brandReady": bool(base.get("brandReady")),
        "gatePass": gate_pass,
        "package13": base,
        "states": states,
    }


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--package131-mode", choices=["standard", "maximum"], default=os.environ.get("KBM_PACKAGE131_MODE", "maximum"))
    opts, base_args = parser.parse_known_args()
    root = Path(__file__).resolve().parents[1]
    input_path = Path(_arg(base_args, "--input")).expanduser().resolve()
    output_path = Path(_arg(base_args, "--output", str(root / "out" / "package131.mp4"))).expanduser().resolve()
    job = _arg(base_args, "--job", "kbm-package131")
    work = root / "work" / job
    work.mkdir(parents=True, exist_ok=True)
    report_path = work / "package13-1-report.json"
    states: list[dict[str, Any]] = [{"stage": "pep-authority", "state": "PASS", "authority": AUTHORITY}]

    os.environ["KBM_PACKAGE131_CUPAI_INTELLIGENCE"] = "1"
    os.environ["KBM_PACKAGE131_CUPAI_MEDIA"] = "1"
    os.environ["KBM_PACKAGE131_MEDIA_DIR"] = str((work / "cupai-generated").resolve())
    os.environ["KBM_PACKAGE131_CUPAI_GENERATE_ALWAYS"] = "1" if opts.package131_mode == "maximum" else "0"

    brand_preflight = _brand_preflight(root)
    if _brand_required() and not brand_preflight.get("configured"):
        states.append({"stage": "brand-preflight", "state": "FAILED", **brand_preflight})
        report = _final_report(output_path=output_path, original_brief="", campaign={}, voice_manifest={}, critic={}, base={}, states=states, mode=opts.package131_mode, brand_preflight=brand_preflight, gate_pass=False)
        _write(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 31
    states.append({"stage": "brand-preflight", "state": "PASS" if brand_preflight.get("configured") else "WARNING", **brand_preflight})

    encoded_brief = _arg(base_args, "--campaign-brief-b64", os.environ.get("CAMPAIGN_BRIEF_B64", ""))
    try:
        original_brief = decode_campaign_brief(encoded_brief) if encoded_brief else ""
    except ValueError as exc:
        _write(report_path, {"package": PACKAGE, "version": VERSION, "authority": AUTHORITY, "pipelineMode": "v41", "rendered": False, "gatePass": False, "states": states + [{"stage": "campaign-brief", "state": "FAILED", "reason": str(exc)}]})
        return 21

    seed = original_brief or "یک ریلز تبلیغاتی حرفه‌ای برای کاریاب ماشین بر اساس محتوای واقعی این ویدیو بساز."
    frames = extract_contact_sheet_frames(input_path, work / "cupai-source-frames", 6) if enabled() else []
    campaign: dict[str, Any] = _fallback_campaign(seed)
    effective_args = list(base_args)
    enhanced_brief = _campaign_text(campaign, seed)
    effective_args = _replace(effective_args, "--campaign-brief-b64", _b64(enhanced_brief))
    if enabled():
        try:
            directed = direct_campaign(seed, frames)
            directed["cta"] = _actionable_cta(directed)
            campaign = directed
            enhanced_brief = _campaign_text(campaign, seed)
            effective_args = _replace(effective_args, "--campaign-brief-b64", _b64(enhanced_brief))
            states.append({"stage": "cupai-multimodal-director", "state": "PASS", "frames": len(frames), "model": os.environ.get("KBM_CUPAI_VISION_MODEL", "gpt-5.6-sol"), "actionableCta": True})
        except Exception as exc:
            states.append({"stage": "cupai-multimodal-director", "state": "FALLBACK", "reason": str(exc)[-400:], "fallbackCampaign": True})
    else:
        states.append({"stage": "cupai-multimodal-director", "state": "SKIPPED", "reason": "CUPAI_API_KEY not configured", "fallbackCampaign": True})

    voice_manifest: dict[str, Any] = {}
    max_seconds = float(_arg(base_args, "--max-seconds", "60") or 60)
    voice = _arg(base_args, "--avalai-voice", "alloy") or "alloy"
    if enabled():
        try:
            script = str(campaign.get("voiceoverScript") or enhanced_brief).strip()
            voice_manifest = direct_voice(script, work, voice=voice, max_seconds=max_seconds, maximum=opts.package131_mode == "maximum")
            selected = str(voice_manifest.get("selectedPath") or "")
            script_used = str(voice_manifest.get("scriptUsed") or script).strip()
            if script_used:
                campaign["voiceoverScript"] = script_used
                enhanced_brief = _campaign_text(campaign, enhanced_brief)
                effective_args = _replace(effective_args, "--campaign-brief-b64", _b64(enhanced_brief))
            if selected:
                effective_args = _replace(effective_args, "--voiceover-audio", selected)
                effective_args = _replace(effective_args, "--voiceover-script", script_used or script)
            voice_state = "PASS" if voice_manifest.get("complete") and voice_manifest.get("durationFit") else "DEGRADED"
            states.append({
                "stage": "cupai-voice-director",
                "state": voice_state,
                "takes": voice_manifest.get("takeCount"),
                "requestedTakes": voice_manifest.get("requestedTakeCount"),
                "selectedTake": voice_manifest.get("selectedTake"),
                "selectedDuration": voice_manifest.get("selectedDuration"),
                "targetSeconds": voice_manifest.get("targetSeconds"),
                "durationFit": voice_manifest.get("durationFit"),
                "scriptFit": voice_manifest.get("scriptFit"),
                "failures": voice_manifest.get("failures", []),
            })
        except Exception as exc:
            manifest = _safe_json(work / "package13-1-voice-manifest.json", {})
            voice_manifest = manifest if isinstance(manifest, dict) else {}
            states.append({"stage": "cupai-voice-director", "state": "FALLBACK", "fallback": "existing-avalai-gateway", "reason": str(exc)[-400:], "failures": voice_manifest.get("failures", [])})
    else:
        states.append({"stage": "cupai-voice-director", "state": "SKIPPED", "reason": "CUPAI_API_KEY not configured", "fallback": "existing-avalai-gateway"})

    _write(work / "package13-1-cupai-campaign.json", campaign)
    (work / "voice-report.json").unlink(missing_ok=True)

    command = [sys.executable, str(root / "pipeline" / "orchestrator_v4.py"), *effective_args]
    rc = subprocess.run(command, cwd=root, check=False).returncode
    if rc != 0:
        _write(report_path, {"package": PACKAGE, "version": VERSION, "authority": AUTHORITY, "pipelineMode": "v41", "rendered": False, "gatePass": False, "states": states + [{"stage": "package13-base", "state": "FAILED", "code": rc}]})
        return rc
    states.append({"stage": "package13-base", "state": "PASS"})

    if voice_manifest.get("complete") is not True or voice_manifest.get("durationFit") is not True:
        voice_manifest, gateway_state = _promote_gateway_voice(work, voice_manifest, max_seconds)
        if gateway_state is not None:
            states.append(gateway_state)

    base = _safe_json(work / "package13-report.json", {})
    if _brand_required() and not bool(base.get("brandReady")):
        states.append({"stage": "brand-authority-gate", "state": "FAILED", "code": "BRAND_ASSET_NOT_RESOLVED", "source": base.get("brandSource")})
        report = _final_report(output_path=output_path, original_brief=original_brief, campaign=campaign, voice_manifest=voice_manifest, critic={}, base=base if isinstance(base, dict) else {}, states=states, mode=opts.package131_mode, brand_preflight=brand_preflight, gate_pass=False)
        _write(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 32
    states.append({"stage": "brand-authority-gate", "state": "PASS" if bool(base.get("brandReady")) else "WARNING"})

    props_path = work / "render-props.json"
    props = _safe_json(props_path, {})
    storyboard = _safe_json(work / "package13-storyboard.json", {})
    asset_report = _safe_json(work / "package13-asset-routing.json", {})

    if enabled() and isinstance(storyboard, dict) and storyboard.get("scenes"):
        try:
            refined = refine_storyboard(storyboard, frames, campaign)
            _write(work / "package13-1-refined-storyboard.json", refined)
            compiled = compile_timeline(refined, asset_report if isinstance(asset_report, dict) else {}, fps=30)
            props["scenes"] = compiled.get("scenes", props.get("scenes", []))
            props["assets"] = compiled.get("assets", props.get("assets", []))
            props.setdefault("editorial", {})["package131Refined"] = True
            if campaign.get("cta"):
                props["cta"] = campaign["cta"]
            _write(props_path, props)
            states.append({"stage": "cupai-storyboard-refiner", "state": "PASS"})
            duration_frames = int(props.get("durationInFrames") or 1)
            render_with_fallback(root=root, source=input_path, props_path=props_path, template=str(props.get("templateId") or "KBM-V03-MACHINE-REVIEW"), output=output_path, duration_frames=duration_frames, allow_remotion=True)
            states.append({"stage": "refined-render", "state": "PASS"})
        except Exception as exc:
            states.append({"stage": "cupai-storyboard-refiner", "state": "FALLBACK", "reason": str(exc)[-400:]})

    critic: dict[str, Any] = {}
    if enabled() and output_path.is_file():
        try:
            critic = critique_final(output_path, work)
            _write(work / "package13-1-cupai-critic-pass0.json", critic)
            critic_complete = critic.get("criticComplete") is True
            states.append({"stage": "cupai-final-critic", "state": _critic_state(critic), "pass": 0, "overall": critic.get("overall"), "audioEnergy": critic.get("audioEnergy"), "publishReady": critic.get("publishReady"), "criticComplete": critic_complete, "reason": str(critic.get("criticError") or "")[-400:]})
            threshold = float(os.environ.get("KBM_PACKAGE131_CRITIC_THRESHOLD", "8.0") or 8.0)
            needs_repair = critic_complete and (float(critic.get("overall") or 0) < threshold or critic.get("publishReady") is not True)
            if needs_repair:
                repaired = apply_bounded_repairs(props, critic)
                _write(props_path, repaired)
                duration_frames = int(repaired.get("durationInFrames") or 1)
                render_with_fallback(root=root, source=input_path, props_path=props_path, template=str(repaired.get("templateId") or "KBM-V03-MACHINE-REVIEW"), output=output_path, duration_frames=duration_frames, allow_remotion=True)
                states.append({"stage": "bounded-auto-reedit", "state": "PASS", "pass": 1, "authority": AUTHORITY})
                critic = critique_final(output_path, work)
                states.append({"stage": "cupai-final-critic", "state": _critic_state(critic), "pass": 1, "overall": critic.get("overall"), "audioEnergy": critic.get("audioEnergy"), "publishReady": critic.get("publishReady"), "criticComplete": critic.get("criticComplete") is True, "reason": str(critic.get("criticError") or "")[-400:]})
            _write(work / "package13-1-cupai-critic.json", critic)
        except Exception as exc:
            states.append({"stage": "cupai-final-critic", "state": "WARNING", "reason": str(exc)[-400:]})

    gate_pass = bool(output_path.is_file())
    report = _final_report(output_path=output_path, original_brief=original_brief, campaign=campaign, voice_manifest=voice_manifest, critic=critic, base=base if isinstance(base, dict) else {}, states=states, mode=opts.package131_mode, brand_preflight=brand_preflight, gate_pass=gate_pass)
    _write(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["rendered"] else 13


if __name__ == "__main__":
    raise SystemExit(main())
