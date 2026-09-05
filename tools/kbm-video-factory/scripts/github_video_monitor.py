#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

AUTHORITY = "KBM-GITHUB-ISSUE-LIVE-MONITOR-AUTHORITY-1"
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))
TERMINAL = {"completed", "failed", "blocked", "cancelled"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _api(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or "/" not in repository:
        raise RuntimeError("GITHUB_TOKEN/GITHUB_REPOSITORY are required for KBM live monitor")
    url = f"https://api.github.com/repos/{repository}{endpoint}"
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "kbm-video-production-live-monitor/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[-1000:]
        raise RuntimeError(f"GitHub monitor API failed: HTTP {exc.code}: {detail}") from exc


def _bar(percent: float, width: int = 12) -> str:
    value = min(100.0, max(0.0, float(percent)))
    filled = int(round(width * value / 100.0))
    return f"{'█' * filled}{'░' * (width - filled)} {int(round(value)):>3}%"


def _status_icon(status: str) -> str:
    return {
        "pending": "⚪",
        "running": "🟡",
        "completed": "✅",
        "failed": "❌",
        "blocked": "⛔",
        "cancelled": "🚫",
    }.get(status, "⚪")


def _display_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    clone = json.loads(json.dumps(data, ensure_ascii=False))
    stages = [item for item in clone.get("stages", []) if isinstance(item, dict)]

    for stage in stages:
        if stage.get("status") != "running":
            continue
        started = _parse_iso(str(stage.get("startedAt") or ""))
        expected = max(10.0, float(stage.get("expectedSeconds") or 10.0))
        if started:
            elapsed = max(0.0, (now - started).total_seconds())
            estimated = min(95.0, max(float(stage.get("percent") or 0), (elapsed / expected) * 92.0))
            stage["percent"] = round(estimated, 1)

    if stages:
        clone["displayOverallPercent"] = round(sum(float(item.get("percent") or 0) for item in stages) / len(stages), 1)
    else:
        clone["displayOverallPercent"] = float(clone.get("overallPercent") or 0)

    remaining = 0.0
    for stage in stages:
        status = str(stage.get("status") or "pending")
        if status in TERMINAL or status == "completed":
            continue
        expected = max(1.0, float(stage.get("expectedSeconds") or 1))
        percent = min(100.0, max(0.0, float(stage.get("percent") or 0)))
        remaining += expected * ((100.0 - percent) / 100.0)
    clone["displayEtaSeconds"] = int(round(remaining)) if str(clone.get("status")) not in TERMINAL else 0
    clone["displayEtaAt"] = now + timedelta(seconds=remaining) if remaining > 0 and str(clone.get("status")) not in TERMINAL else None
    return clone


def _format_eta(snapshot: dict[str, Any]) -> str:
    status = str(snapshot.get("status") or "queued")
    if status == "completed":
        return "تکمیل شده"
    if status in {"failed", "blocked", "cancelled"}:
        return "متوقف شده — پس از رفع Blocker و اجرای مجدد Workflow دوباره محاسبه می‌شود"
    eta_seconds = int(snapshot.get("displayEtaSeconds") or 0)
    eta_at = snapshot.get("displayEtaAt")
    minutes = max(1, int(round(eta_seconds / 60))) if eta_seconds else 0
    if isinstance(eta_at, datetime):
        iran = eta_at.astimezone(IRAN_TZ).strftime("%H:%M:%S")
        return f"حدود {minutes} دقیقه دیگر — تقریباً ساعت **{iran} ایران**"
    return "در حال محاسبه"


def _blocker_action(message: str) -> str:
    upper = message.upper()
    if "CUPAI_CREDIT_EXHAUSTED" in upper or "CREDIT" in upper and "CUPAI" in upper:
        return "اعتبار CupAI را بررسی/شارژ کنید و Workflow را مجدد اجرا کنید."
    if "VOICE_" in upper or "VOICE" in upper or "NARRATION" in upper:
        return "Voice Director / Narration را پس از رفع Provider Blocker مجدد اجرا کنید."
    if "AUDIO_LUFS" in upper or "AUDIO_CLIPPING" in upper or "AUDIO_" in upper:
        return "Audio Mastering و Quality Gate را اصلاح/تکرار کنید، سپس Workflow را مجدد اجرا کنید."
    if "CRITIC" in upper:
        return "Final AI Critic باید مجدد اجرا و PASS شود."
    if "RIGHTS" in upper:
        return "Rights Evidence دارایی مشکل‌دار را تکمیل کنید و Pipeline را مجدد اجرا کنید."
    if "RENDER" in upper:
        return "Render dependency/asset را رفع کنید و Remotion Render را مجدد اجرا کنید."
    return "علت این مرحله را رفع کنید و Workflow را مجدد اجرا کنید."


def _blockers(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for stage in snapshot.get("stages", []):
        if not isinstance(stage, dict):
            continue
        status = str(stage.get("status") or "")
        if status not in {"blocked", "failed"}:
            continue
        message = str(stage.get("message") or "بدون جزئیات").strip()
        result.append({
            "stage": str(stage.get("labelFa") or stage.get("id") or "مرحله نامشخص"),
            "status": status,
            "message": message,
            "action": _blocker_action(message),
        })
    return result


def render_issue(data: dict[str, Any]) -> str:
    snapshot = _display_snapshot(data)
    order = snapshot.get("order") if isinstance(snapshot.get("order"), dict) else {}
    run = snapshot.get("run") if isinstance(snapshot.get("run"), dict) else {}
    overall = float(snapshot.get("displayOverallPercent") or 0)
    status = str(snapshot.get("status") or "queued")
    stages = [item for item in snapshot.get("stages", []) if isinstance(item, dict)]
    workflow_url = str(run.get("workflowUrl") or "")
    artifact_url = str(snapshot.get("artifactUrl") or "")
    current = next((item for item in stages if item.get("status") == "running"), None)
    blockers = _blockers(snapshot)

    lines = [
        "<!-- KBM_VIDEO_PRODUCTION_LIVE_MONITOR -->",
        "# 🎬 KBM Video Production Live Monitor",
        "",
        f"**سفارش:** `{order.get('id') or '-'}`  ",
        f"**موضوع:** {order.get('topic') or '-'}  ",
        f"**Vertical:** `{order.get('vertical') or '-'}` · **مدت هدف:** `{order.get('durationSeconds') or '-'}s`  ",
        f"**وضعیت:** {_status_icon(status)} **{status.upper()}**",
        "",
        "## پیشرفت کلی",
        "",
        f"`{_bar(overall, 20)}`",
        "",
        f"**مرحله جاری:** {current.get('labelFa') if current else '—'}  ",
        f"**ETA تخمینی:** {_format_eta(snapshot)}  ",
        f"**آخرین بروزرسانی:** {datetime.now(IRAN_TZ).strftime('%Y-%m-%d %H:%M:%S')} ایران",
    ]

    if blockers:
        lines += [
            "",
            "## ⛔ Blocker فعلی و اقدام لازم",
            "",
            "| مرحله | علت Blocker | اقدام لازم |",
            "|---|---|---|",
        ]
        for item in blockers:
            cause = item["message"].replace("|", "/")
            action = item["action"].replace("|", "/")
            lines.append(f"| {item['stage']} | `{cause}` | **{action}** |")
        lines += [
            "",
            "> **پس از رفع Blocker، Workflow را Re-run کنید؛ ETA از همان Run جدید دوباره محاسبه می‌شود.**",
        ]

    lines += [
        "",
        "## مراحل تولید",
        "",
        "| # | مرحله | وضعیت | پیشرفت | توضیح |",
        "|---:|---|:---:|---|---|",
    ]
    for index, stage in enumerate(stages, 1):
        percent = float(stage.get("percent") or 0)
        stage_status = str(stage.get("status") or "pending")
        message = str(stage.get("message") or "").replace("|", "/")
        lines.append(
            f"| {index} | {stage.get('labelFa') or stage.get('id')} | {_status_icon(stage_status)} | `{_bar(percent)}` | {message} |"
        )

    lines += ["", "## لینک‌ها", ""]
    if workflow_url:
        lines.append(f"- 🔎 [مشاهده Workflow Run]({workflow_url})")
    if artifact_url:
        label = "⬇️ دانلود فایل نهایی / Artifact" if snapshot.get("finalVideoReady") else "📦 دانلود Preview / Evidence Artifact"
        lines.append(f"- [{label}]({artifact_url})")
    else:
        lines.append("- ⏳ لینک دانلود پس از ساخت Artifact به‌صورت خودکار اینجا ظاهر می‌شود.")

    lines += [
        "",
        "## پیام Pipeline",
        "",
        f"> {snapshot.get('message') or 'در حال تولید...'}",
        "",
        "---",
        f"`{AUTHORITY}` · بروزرسانی خودکار تقریباً هر 20 ثانیه · درصدهای مرحله در حال اجرا تا 95٪ بر اساس ETA به‌صورت زنده برآورد می‌شوند و فقط با تأیید واقعی Pipeline به 100٪ می‌رسند.",
    ]
    return "\n".join(lines)


def create_issue(progress_path: Path, issue_file: Path | None = None) -> dict[str, Any]:
    data = _load(progress_path)
    order = data.get("order") if isinstance(data.get("order"), dict) else {}
    title = f"🎬 KBM Video #{order.get('id') or 'ORDER'} — {order.get('topic') or 'Production Monitor'}"
    result = _api("POST", "/issues", {"title": title[:240], "body": render_issue(data)})
    if issue_file:
        issue_file.parent.mkdir(parents=True, exist_ok=True)
        issue_file.write_text(str(result.get("number") or ""), encoding="utf-8")
    return {"number": result.get("number"), "html_url": result.get("html_url"), "title": result.get("title")}


def update_issue(progress_path: Path, issue_number: int) -> dict[str, Any]:
    data = _load(progress_path)
    result = _api("PATCH", f"/issues/{issue_number}", {"body": render_issue(data)})
    return {"number": result.get("number"), "html_url": result.get("html_url"), "updated_at": result.get("updated_at")}


def watch(progress_path: Path, issue_number: int, interval: int) -> int:
    last_body = ""
    while True:
        data = _load(progress_path)
        body = render_issue(data)
        if body != last_body:
            _api("PATCH", f"/issues/{issue_number}", {"body": body})
            last_body = body
        if str(data.get("status") or "") in TERMINAL:
            return 0
        time.sleep(max(10, interval))


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish KBM video progress to a live GitHub Issue")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--progress", required=True)
    create.add_argument("--issue-file", default="")

    sync = sub.add_parser("sync")
    sync.add_argument("--progress", required=True)
    sync.add_argument("--issue-number", type=int, required=True)

    watcher = sub.add_parser("watch")
    watcher.add_argument("--progress", required=True)
    watcher.add_argument("--issue-number", type=int, required=True)
    watcher.add_argument("--interval", type=int, default=20)

    args = parser.parse_args()
    progress = Path(args.progress).expanduser().resolve()
    if args.command == "create":
        result = create_issue(progress, Path(args.issue_file).expanduser().resolve() if args.issue_file else None)
    elif args.command == "sync":
        result = update_issue(progress, args.issue_number)
    else:
        return watch(progress, args.issue_number, args.interval)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())