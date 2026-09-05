#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

AUTHORITY = "KBM-VIDEO-PRODUCTION-LIVE-MONITOR-AUTHORITY-1"
SCHEMA_VERSION = 1

# This order mirrors the actual CAMP/v41 execution path.
STAGES: list[dict[str, Any]] = [
    {"id": "brief_preflight", "labelFa": "دریافت سفارش و پیش‌پرواز", "expectedSeconds": 20},
    {"id": "creative_direction", "labelFa": "کارگردانی خلاق و سناریو", "expectedSeconds": 65},
    {"id": "voice_narration", "labelFa": "نریشن و انتخاب Take", "expectedSeconds": 95},
    {"id": "media_rights", "labelFa": "مدیا، B-roll و حقوق استفاده", "expectedSeconds": 95},
    {"id": "storyboard_edit_plan", "labelFa": "استوری‌بورد و برنامه تدوین", "expectedSeconds": 55},
    {"id": "website_capture", "labelFa": "کپچر واقعی سایت", "expectedSeconds": 85},
    {"id": "cinematic_render", "labelFa": "رندر سینمایی Remotion", "expectedSeconds": 255},
    {"id": "audio_mastering", "labelFa": "مسترینگ و کنترل صوت", "expectedSeconds": 50},
    {"id": "critic_repair", "labelFa": "AI Critic و اصلاح محدود", "expectedSeconds": 120},
    {"id": "release_artifact", "labelFa": "Release Gate و فایل دانلود", "expectedSeconds": 25},
]

TERMINAL = {"completed", "failed", "blocked", "cancelled"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stage_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in data.get("stages", []) if isinstance(item, dict)}


def _recompute(data: dict[str, Any]) -> dict[str, Any]:
    stages = [item for item in data.get("stages", []) if isinstance(item, dict)]
    data["overallPercent"] = round(sum(float(item.get("percent") or 0) for item in stages) / max(1, len(stages)), 1)
    running = next((item for item in stages if item.get("status") == "running"), None)
    data["currentStage"] = running.get("id") if running else None

    remaining = 0.0
    for item in stages:
        status = str(item.get("status") or "pending")
        if status in {"completed", "failed", "blocked", "cancelled"}:
            continue
        expected = max(1.0, float(item.get("expectedSeconds") or 1))
        percent = min(100.0, max(0.0, float(item.get("percent") or 0)))
        remaining += expected * ((100.0 - percent) / 100.0)

    if str(data.get("status")) not in TERMINAL:
        data["etaSeconds"] = int(round(remaining))
        data["etaAt"] = _iso(_now() + timedelta(seconds=remaining))
    else:
        data["etaSeconds"] = 0
        data["etaAt"] = None
    data["updatedAt"] = _iso()
    return data


def init_progress(
    path: Path,
    *,
    order_id: str,
    topic: str,
    vertical: str,
    duration_seconds: float,
    workflow_url: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    now = _iso()
    data: dict[str, Any] = {
        "authority": AUTHORITY,
        "schemaVersion": SCHEMA_VERSION,
        "order": {"id": order_id, "topic": topic, "vertical": vertical, "durationSeconds": float(duration_seconds)},
        "run": {"id": run_id, "workflowUrl": workflow_url},
        "status": "queued",
        "overallPercent": 0,
        "currentStage": None,
        "startedAt": now,
        "updatedAt": now,
        "etaAt": None,
        "etaSeconds": 0,
        "artifactUrl": None,
        "finalVideoReady": False,
        "message": "سفارش ثبت شد و در صف تولید است.",
        "stages": [
            {**stage, "status": "pending", "percent": 0, "startedAt": None, "finishedAt": None, "message": "در انتظار"}
            for stage in STAGES
        ],
    }
    _atomic_write(path, _recompute(data))
    return data


def update_stage(path: Path, stage_id: str, *, percent: float | None = None, status: str | None = None, message: str | None = None) -> dict[str, Any]:
    data = _load(path)
    stages = _stage_map(data)
    if stage_id not in stages:
        raise KeyError(f"Unknown KBM monitor stage: {stage_id}")
    stage = stages[stage_id]
    now = _iso()

    if status == "running" and not stage.get("startedAt"):
        stage["startedAt"] = now
    if percent is not None:
        stage["percent"] = round(min(100.0, max(0.0, float(percent))), 1)
    if status:
        stage["status"] = status
    if message is not None:
        stage["message"] = message
    if status == "completed":
        stage["percent"] = 100
        stage["finishedAt"] = now
    elif status in {"failed", "blocked", "cancelled"}:
        stage["finishedAt"] = now

    # Intermediate stages may be blocked while CAMP continues with fallback/evidence.
    # The order becomes terminal only at Release Gate or explicit finalize().
    if status == "running":
        data["status"] = "running"
    elif status in {"failed", "blocked", "cancelled"}:
        data["message"] = message or f"مرحله {stage_id} مشکل دارد."
        if stage_id == "release_artifact":
            data["status"] = status
        elif str(data.get("status")) not in TERMINAL:
            data["status"] = "running"

    _atomic_write(path, _recompute(data))
    return data


def start_stage(path: Path, stage_id: str, message: str = "در حال اجرا") -> dict[str, Any]:
    return update_stage(path, stage_id, percent=0, status="running", message=message)


def complete_stage(path: Path, stage_id: str, message: str = "تکمیل شد") -> dict[str, Any]:
    return update_stage(path, stage_id, percent=100, status="completed", message=message)


def fail_stage(path: Path, stage_id: str, message: str, *, blocked: bool = False) -> dict[str, Any]:
    return update_stage(path, stage_id, status="blocked" if blocked else "failed", message=message)


def finalize(path: Path, *, success: bool, artifact_url: str = "", message: str = "") -> dict[str, Any]:
    data = _load(path)
    if success:
        data["status"] = "completed"
        data["finalVideoReady"] = True
        for stage in data.get("stages", []):
            if isinstance(stage, dict):
                stage["status"] = "completed"
                stage["percent"] = 100
                stage["finishedAt"] = stage.get("finishedAt") or _iso()
    else:
        if str(data.get("status")) not in {"blocked", "cancelled"}:
            data["status"] = "failed"
        data["finalVideoReady"] = False
    if artifact_url:
        data["artifactUrl"] = artifact_url
    data["message"] = message or ("فایل نهایی آماده دانلود است." if success else "تولید به Release نهایی نرسید.")
    _atomic_write(path, _recompute(data))
    return data


def set_artifact(path: Path, artifact_url: str) -> dict[str, Any]:
    data = _load(path)
    data["artifactUrl"] = artifact_url
    _atomic_write(path, _recompute(data))
    return data


def progress_path_from_env() -> Path | None:
    raw = os.environ.get("KBM_PROGRESS_FILE", "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def safe_start(stage_id: str, message: str = "در حال اجرا") -> None:
    path = progress_path_from_env()
    if path and path.is_file():
        try:
            start_stage(path, stage_id, message)
        except Exception:
            pass


def safe_done(stage_id: str, message: str = "تکمیل شد") -> None:
    path = progress_path_from_env()
    if path and path.is_file():
        try:
            complete_stage(path, stage_id, message)
        except Exception:
            pass


def safe_fail(stage_id: str, message: str, *, blocked: bool = False) -> None:
    path = progress_path_from_env()
    if path and path.is_file():
        try:
            fail_stage(path, stage_id, message, blocked=blocked)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="KBM video production progress tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--file", required=True)
    init.add_argument("--order-id", required=True)
    init.add_argument("--topic", required=True)
    init.add_argument("--vertical", required=True)
    init.add_argument("--duration", type=float, required=True)
    init.add_argument("--workflow-url", default="")
    init.add_argument("--run-id", default="")

    stage = sub.add_parser("stage")
    stage.add_argument("--file", required=True)
    stage.add_argument("--id", required=True)
    stage.add_argument("--status", choices=["running", "completed", "failed", "blocked", "cancelled"], required=True)
    stage.add_argument("--percent", type=float)
    stage.add_argument("--message", default="")

    artifact = sub.add_parser("artifact")
    artifact.add_argument("--file", required=True)
    artifact.add_argument("--url", required=True)

    final = sub.add_parser("finalize")
    final.add_argument("--file", required=True)
    final.add_argument("--success", choices=["0", "1"], required=True)
    final.add_argument("--artifact-url", default="")
    final.add_argument("--message", default="")

    args = parser.parse_args()
    path = Path(args.file).expanduser().resolve()
    if args.command == "init":
        result = init_progress(path, order_id=args.order_id, topic=args.topic, vertical=args.vertical, duration_seconds=args.duration, workflow_url=args.workflow_url, run_id=args.run_id)
    elif args.command == "stage":
        result = update_stage(path, args.id, percent=args.percent, status=args.status, message=args.message or None)
    elif args.command == "artifact":
        result = set_artifact(path, args.url)
    else:
        result = finalize(path, success=args.success == "1", artifact_url=args.artifact_url, message=args.message)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
