#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from progress_tracker import complete_stage, fail_stage, start_stage, update_stage  # noqa: E402


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _status(progress: Path, stage_id: str) -> str:
    data = _read(progress)
    for item in data.get("stages", []):
        if isinstance(item, dict) and item.get("id") == stage_id:
            return str(item.get("status") or "pending")
    return "pending"


def _start_if_pending(progress: Path, stage_id: str, message: str) -> None:
    if _status(progress, stage_id) == "pending":
        start_stage(progress, stage_id, message)


def _done_if_active(progress: Path, stage_id: str, message: str) -> None:
    if _status(progress, stage_id) in {"pending", "running"}:
        if _status(progress, stage_id) == "pending":
            start_stage(progress, stage_id, message)
        complete_stage(progress, stage_id, message)


def _blocked_if_active(progress: Path, stage_id: str, message: str) -> None:
    if _status(progress, stage_id) in {"pending", "running"}:
        if _status(progress, stage_id) == "pending":
            start_stage(progress, stage_id, message)
        fail_stage(progress, stage_id, message, blocked=True)


def _advance(work: Path, progress: Path, *, final: bool = False) -> None:
    brief = work / "camp-brief.json"
    static_audio = work / "camp-static-audio.json"
    campaign = work / "package13-1-avalai-campaign.json"
    voice_manifest = work / "package13-1-voice-manifest.json"
    media_research = work / "package13-media-research.json"
    asset_routing = work / "package13-asset-routing.json"
    storyboard = work / "package13-storyboard.json"
    render_props = work / "render-props.json"
    website = work / "camp-website-capture.json"
    renderer = work / "camp-renderer.json"
    audio = work / "camp-audio-master.json"
    critic = work / "camp-critic.json"
    release = work / "camp-release-report.json"

    _start_if_pending(progress, "brief_preflight", "دریافت Brief، Source و پیش‌پرواز")
    if brief.is_file() and static_audio.is_file():
        _done_if_active(progress, "brief_preflight", "Brief و پیش‌پرواز آماده شد")
        _start_if_pending(progress, "creative_direction", "کارگردانی خلاق و ساخت Campaign Plan")

    if campaign.is_file():
        _done_if_active(progress, "creative_direction", "Campaign Plan و پیام تبلیغاتی آماده شد")
        _start_if_pending(progress, "voice_narration", "ساخت Takeهای نریشن و انتخاب صدا")

    if voice_manifest.is_file():
        voice = _read(voice_manifest)
        if voice.get("complete") is True and voice.get("durationFit") is True:
            _done_if_active(progress, "voice_narration", "نریشن انتخاب و Duration Fit تأیید شد")
        else:
            blocker = "نریشن کامل نشده"
            failures = voice.get("failures") if isinstance(voice.get("failures"), list) else []
            if any("credit" in str(item).lower() for item in failures):
                blocker = "AvalAI Credit برای Voice کافی نیست"
            _blocked_if_active(progress, "voice_narration", blocker)
        _start_if_pending(progress, "media_rights", "تحقیق B-roll، Asset Routing و Rights")

    if media_research.is_file() and asset_routing.is_file():
        _done_if_active(progress, "media_rights", "مدیا و Asset Routing آماده شد")
        _start_if_pending(progress, "storyboard_edit_plan", "تدوین استوری‌بورد و Timeline")

    if storyboard.is_file() and render_props.is_file():
        _done_if_active(progress, "storyboard_edit_plan", "استوری‌بورد و Render Props آماده شد")
        _start_if_pending(progress, "website_capture", "کپچر واقعی صفحات سایت")

    if website.is_file():
        _done_if_active(progress, "website_capture", "کپچر واقعی سایت تکمیل شد")
        _start_if_pending(progress, "cinematic_render", "رندر سینمایی Remotion در حال اجراست")

    if renderer.is_file():
        render_data = _read(renderer)
        if render_data.get("fallbackUsed") is True:
            _blocked_if_active(progress, "cinematic_render", "Fallback renderer استفاده شد؛ Release مجاز نیست")
        else:
            _done_if_active(progress, "cinematic_render", "رندر سینمایی Remotion تکمیل شد")
        _start_if_pending(progress, "audio_mastering", "مسترینگ، LUFS، Peak و Clipping")

    if audio.is_file():
        _done_if_active(progress, "audio_mastering", "Audio Master ساخته شد؛ Quality Gate در مرحله Release کنترل می‌شود")
        _start_if_pending(progress, "critic_repair", "Final AI Critic و Repair Pass")

    if critic.is_file():
        critic_data = _read(critic)
        if critic_data.get("criticComplete") is True:
            _done_if_active(progress, "critic_repair", "Final Critic کامل شد")
        else:
            reason = str(critic_data.get("providerBlocker") or critic_data.get("criticError") or "Critic incomplete")
            _blocked_if_active(progress, "critic_repair", reason[-220:])
        _start_if_pending(progress, "release_artifact", "Hard Release Gate و ساخت Artifact")

    if release.is_file():
        release_data = _read(release)
        if release_data.get("gatePass") is True and release_data.get("releaseReady") is True:
            _done_if_active(progress, "release_artifact", "Release Gate PASS؛ فایل نهایی آماده Artifact است")
        else:
            blockers = release_data.get("blockers") if isinstance(release_data.get("blockers"), list) else []
            repair_pass = int(release_data.get("repairPass") or 0)
            message = "Release Gate در حال Repair"
            if blockers:
                message += f" (Pass {repair_pass}/2): " + ", ".join(str(item) for item in blockers[:5])
            if final:
                final_message = "Release Gate BLOCKED"
                if blockers:
                    final_message += ": " + ", ".join(str(item) for item in blockers[:8])
                _blocked_if_active(progress, "release_artifact", final_message[:360])
            elif _status(progress, "release_artifact") in {"pending", "running"}:
                _start_if_pending(progress, "release_artifact", message[:320])
                # Do not make the run terminal while bounded repair passes are still executing.
                # Pass 0/1 are intermediate evidence; only the final CAMP report may BLOCK.
                percent = min(88.0, 28.0 + repair_pass * 28.0)
                update_stage(progress, "release_artifact", percent=percent, status="running", message=message[:320])


def _fail_first_open(progress: Path, message: str) -> None:
    data = _read(progress)
    for item in data.get("stages", []):
        if isinstance(item, dict) and str(item.get("status") or "pending") in {"running", "pending"}:
            fail_stage(progress, str(item.get("id")), message[:260], blocked=False)
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CAMP and expose real stage progress")
    parser.add_argument("--progress", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    progress = Path(args.progress).expanduser().resolve()
    work = Path(args.work).expanduser().resolve()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("CAMP command is required after --")
    if not progress.is_file():
        raise SystemExit(f"Progress file missing: {progress}")

    work.mkdir(parents=True, exist_ok=True)
    _start_if_pending(progress, "brief_preflight", "شروع سفارش و پیش‌پرواز")
    process = subprocess.Popen(command, cwd=ROOT)
    while process.poll() is None:
        _advance(work, progress, final=False)
        time.sleep(2)
    _advance(work, progress, final=True)
    rc = int(process.returncode or 0)
    if rc != 0:
        _fail_first_open(progress, f"Pipeline با کد {rc} متوقف شد")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
