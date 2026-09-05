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

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))
START = "<!-- KBM_MASTER_LIVE_START -->"
END = "<!-- KBM_MASTER_LIVE_END -->"
TERMINAL = {"completed", "failed", "blocked", "cancelled"}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _api(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or "/" not in repository:
        raise RuntimeError("GITHUB_TOKEN/GITHUB_REPOSITORY are required")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}{endpoint}",
        data=json.dumps(payload or {}).encode("utf-8") if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "kbm-master-control-center/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[-800:]
        raise RuntimeError(f"GitHub master monitor failed: HTTP {exc.code}: {detail}") from exc


def _bar(percent: float, width: int = 20) -> str:
    value = min(100.0, max(0.0, float(percent)))
    filled = int(round(width * value / 100.0))
    return f"{'█' * filled}{'░' * (width - filled)} {value:.1f}%"


def _status_icon(status: str) -> str:
    return {
        "queued": "⚪",
        "running": "🟡",
        "completed": "✅",
        "failed": "❌",
        "blocked": "⛔",
        "cancelled": "🚫",
    }.get(status, "⚪")


def _current_stage(data: dict[str, Any]) -> dict[str, Any] | None:
    stages = [item for item in data.get("stages", []) if isinstance(item, dict)]
    return next((item for item in stages if item.get("status") == "running"), None)


def _blockers(data: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for stage in data.get("stages", []):
        if not isinstance(stage, dict) or str(stage.get("status") or "") not in {"blocked", "failed"}:
            continue
        message = str(stage.get("message") or "").strip()
        if message:
            values.append(message)
    return values


def _render_live(data: dict[str, Any], *, base_percent: float, span_percent: float, run_issue: str, run_url: str, phase: str) -> str:
    status = str(data.get("status") or "queued")
    run_percent = float(data.get("overallPercent") or 0.0)
    attempted = min(base_percent + span_percent, base_percent + span_percent * run_percent / 100.0)
    verified = base_percent
    if status == "completed" and data.get("finalVideoReady") is True:
        verified = base_percent + span_percent
        attempted = verified
    stage = _current_stage(data)
    blocker_rows = _blockers(data)
    order = data.get("order") if isinstance(data.get("order"), dict) else {}
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    resolved_run_url = run_url or str(run.get("workflowUrl") or "")
    now = datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        START,
        "## 🔴 Live Architecture Status",
        "",
        f"**Verified overall:** `{_bar(verified)}`  ",
        f"**Current attempt position:** `{_bar(attempted)}`  ",
        f"**Phase:** `{phase}`  ",
        f"**Run:** `{order.get('id') or run.get('id') or '-'}`  ",
        f"**Status:** {_status_icon(status)} **{status.upper()}**  ",
        f"**Run progress:** `{run_percent:.1f}%`  ",
        f"**Current stage:** {stage.get('labelFa') if stage else '—'}  ",
        f"**Last sync:** {now} ایران",
        "",
        "> `Verified overall` فقط با Evidence واقعی بالا می‌رود. `Current attempt position` جایگاه زنده Run را نشان می‌دهد و در صورت Block شدن Commit نمی‌شود.",
    ]
    if blocker_rows:
        lines += ["", "### ⛔ Current blocker", ""]
        for item in blocker_rows[:3]:
            lines.append(f"- `{item}`")
    lines += ["", "### Live links", ""]
    if run_issue:
        lines.append(f"- 🎬 [Run Live Monitor]({run_issue})")
    if resolved_run_url:
        lines.append(f"- 🔎 [GitHub Actions Run]({resolved_run_url})")
    lines += ["", END]
    return "\n".join(lines)


def _replace_live_block(body: str, replacement: str) -> str:
    if START in body and END in body:
        left = body.split(START, 1)[0].rstrip()
        right = body.split(END, 1)[1].lstrip()
        return f"{left}\n\n{replacement}\n\n{right}".strip() + "\n"
    anchor = "# 🎛️ KBM Video → Social Master Live Control Center"
    if anchor in body:
        head, tail = body.split(anchor, 1)
        return f"{head}{anchor}\n\n{replacement}\n\n{tail.lstrip()}".strip() + "\n"
    return f"{replacement}\n\n{body}".strip() + "\n"


def sync(progress: Path, *, issue_number: int, base_percent: float, span_percent: float, run_issue: str, run_url: str, phase: str) -> None:
    data = _load(progress)
    issue = _api("GET", f"/issues/{issue_number}")
    body = str(issue.get("body") or "")
    replacement = _render_live(data, base_percent=base_percent, span_percent=span_percent, run_issue=run_issue, run_url=run_url, phase=phase)
    new_body = _replace_live_block(body, replacement)
    if new_body != body:
        _api("PATCH", f"/issues/{issue_number}", {"body": new_body})


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync KBM architecture 70→100 master issue from a live progress contract")
    parser.add_argument("--progress", required=True)
    parser.add_argument("--issue-number", type=int, default=48)
    parser.add_argument("--base-percent", type=float, default=70.0)
    parser.add_argument("--span-percent", type=float, default=8.0)
    parser.add_argument("--run-issue", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--phase", default="CAMP Final Quality Gate")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=20)
    args = parser.parse_args()

    progress = Path(args.progress).expanduser().resolve()
    while True:
        sync(
            progress,
            issue_number=args.issue_number,
            base_percent=args.base_percent,
            span_percent=args.span_percent,
            run_issue=args.run_issue,
            run_url=args.run_url,
            phase=args.phase,
        )
        if not args.watch:
            return 0
        data = _load(progress)
        if str(data.get("status") or "") in TERMINAL:
            return 0
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
