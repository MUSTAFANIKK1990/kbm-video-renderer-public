#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
PACKAGE = "KBM-TOPIC-TO-REEL-NO-PUBLISH-01"
TTS_MODEL = "gemini-2.5-pro-tts"
ALLOWED_STYLES = {"balanced", "cinematic", "high-energy"}
ALLOWED_VERTICALS = {"generic", "machine-sale", "machine-rental", "service", "parts"}
def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
def _bounded_text(value: str, label: str, limit: int) -> str:
    text = " ".join((value or "").replace("\x00", " ").split()).strip()
    if not text or len(text) > limit: raise ValueError(f"{label} is invalid")
    return text
def safe_job_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", (value or "").strip()).strip("-")[:80]
    return cleaned or "kbm-topic-reel"
def source_query_for_topic(topic: str) -> str:
    lowered = topic.lower()
    rules = (
        (("بیل", "excavator"), "excavator construction site close-up"),
        (("لودر", "loader"), "wheel loader construction site"),
        (("جرثقیل", "crane"), "mobile crane construction site"),
        (("معدن", "mining"), "open pit mining heavy machinery"),
        (("راهسازی", "road"), "road construction heavy equipment"),
        (("تعمیر", "سرویس", "maintenance"), "heavy equipment maintenance workshop"),
        (("قطعه", "لوازم", "spare"), "heavy machinery spare parts workshop"),
    )
    for needles, query in rules:
        if any(needle in lowered for needle in needles): return query
    return "cinematic heavy machinery industrial construction"
def build_camp_command(root: Path, *, topic: str, vertical: str, duration: float, goal: str, cta: str, website_url: str, source: Path, output: Path, job: str, voice: str, edit_style: str) -> list[str]:
    # CAMP capture requires an explicit frame budget. A topic run supplies one
    # first-party route, so make it a deterministic 9-second website walkthrough.
    route = json.dumps([{
        "name": "campaign-site-walkthrough",
        "url": website_url,
        "label": "بررسی و ثبت آگهی",
        "mode": "scroll",
        "frames": 90,
        "target": 2200,
    }], ensure_ascii=False)
    return [sys.executable, str(root / "pipeline" / "orchestrator_camp.py"), "--camp-topic", topic, "--camp-vertical", vertical, "--camp-duration", f"{duration:.3f}", "--camp-goal", goal, "--camp-cta", cta, "--camp-website-required", "--camp-website-routes-json", route, "--package131-mode", "maximum", "--input", str(source), "--output", str(output), "--job", job, "--max-seconds", f"{duration:.3f}", "--avalai-voice", voice, "--edit-style", edit_style]
def main() -> int:
    parser = argparse.ArgumentParser(description="Build one fail-closed KBM Reel from a topic.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--vertical", default="machine-sale", choices=sorted(ALLOWED_VERTICALS))
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--goal", default="conversion")
    parser.add_argument("--cta", default="همین حالا آگهی فروش ماشینت را ثبت کن")
    parser.add_argument("--website-url", default="https://karyabmashin.ir/machine-sales/")
    parser.add_argument("--source-query", default="")
    parser.add_argument("--job", default="kbm-topic-reel")
    parser.add_argument("--output", default="")
    parser.add_argument("--voice", default="onyx")
    parser.add_argument("--edit-style", default="high-energy", choices=sorted(ALLOWED_STYLES))
    args = parser.parse_args()
    topic = _bounded_text(args.topic, "topic", 240)
    goal = _bounded_text(args.goal, "goal", 80)
    cta = _bounded_text(args.cta, "cta", 160)
    if not 6.0 <= args.duration <= 60.0: raise SystemExit("--duration must be between 6 and 60 seconds")
    if not args.website_url.startswith("https://karyabmashin.ir/"): raise SystemExit("--website-url must be an HTTPS KaryabMashin route")
    job = safe_job_id(args.job)
    root = Path(__file__).resolve().parents[1]
    work = root / "work" / job
    source = root / "out" / f"{job}-licensed-source.mp4"
    output = Path(args.output).expanduser().resolve() if args.output else (root / "out" / f"{job}.mp4").resolve()
    source_query = _bounded_text(args.source_query, "source query", 180) if args.source_query else source_query_for_topic(topic)
    environment = os.environ.copy()
    environment["KBM_EXTERNAL_PUBLISH"] = "0"
    environment["KBM_TTS_PROVIDER"] = "avalai"
    environment["KBM_AVALAI_TTS_MODEL"] = TTS_MODEL
    request = {"package": PACKAGE, "job": job, "topic": topic, "vertical": args.vertical, "durationSeconds": round(args.duration, 3), "goal": goal, "cta": cta, "websiteUrl": args.website_url, "sourceQuery": source_query, "editStyle": args.edit_style, "ttsProvider": "avalai", "ttsModel": TTS_MODEL, "externalPublish": False, "sourcePolicy": "licensed Pexels/Pixabay footage plus first-party site capture only"}
    _write(work / "topic-reel-request.json", request)
    prepare = [sys.executable, str(root / "scripts" / "prepare_persian_quality_source.py"), "--query", source_query, "--output", str(source), "--report", str(work / "topic-source-provenance.json"), "--duration", f"{min(60.0, max(8.0, args.duration + 2.0)):.3f}"]
    source_rc = subprocess.run(prepare, cwd=root, env=environment, check=False).returncode
    if source_rc != 0 or not source.is_file():
        _write(work / "topic-reel-result.json", {**request, "status": "FAILED", "stage": "licensed-source", "returnCode": source_rc})
        return 72
    command = build_camp_command(root, topic=topic, vertical=args.vertical, duration=args.duration, goal=goal, cta=cta, website_url=args.website_url, source=source, output=output, job=job, voice=_bounded_text(args.voice, "voice", 80), edit_style=args.edit_style)
    camp_rc = subprocess.run(command, cwd=root, env=environment, check=False).returncode
    _write(work / "topic-reel-result.json", {**request, "status": "PASS" if camp_rc == 0 and output.is_file() else "FAILED", "stage": "camp-render", "returnCode": camp_rc, "output": str(output)})
    return camp_rc
if __name__ == "__main__":
    raise SystemExit(main())
