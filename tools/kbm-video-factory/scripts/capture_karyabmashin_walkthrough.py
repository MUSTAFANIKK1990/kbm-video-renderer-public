#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "https://karyabmashin.ir/"
ADS_URL = "https://karyabmashin.ir/ads/"
FPS_CAPTURE = 10
WIDTH = 900
HEIGHT = 1600


def _wait(page, ms: int = 280) -> None:
    page.wait_for_timeout(ms)


def _scroll_frames(page, frames_dir: Path, start_index: int, start_y: float, end_y: float, count: int) -> int:
    for offset in range(count):
        ratio = 0 if count <= 1 else offset / (count - 1)
        eased = ratio * ratio * (3 - 2 * ratio)
        y = start_y + (end_y - start_y) * eased
        page.evaluate("y => window.scrollTo(0, y)", y)
        _wait(page, 90)
        page.screenshot(path=str(frames_dir / f"frame-{start_index + offset:04d}.png"), full_page=False)
    return start_index + count


def _hold_frames(page, frames_dir: Path, start_index: int, count: int) -> int:
    for offset in range(count):
        page.screenshot(path=str(frames_dir / f"frame-{start_index + offset:04d}.png"), full_page=False)
        _wait(page, 80)
    return start_index + count


def _goto(page, url: str) -> None:
    if not url.startswith("https://karyabmashin.ir/"):
        raise ValueError(f"CAMP website capture only accepts first-party public routes: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    page.add_style_tag(content="""
      html { scroll-behavior: auto !important; }
      * { animation-duration: .001s !important; animation-delay: 0s !important; transition-duration: .001s !important; }
      body { overscroll-behavior: none !important; }
    """)
    _wait(page, 650)


def _default_routes() -> list[dict[str, object]]:
    return [
        {"name": "home-top", "url": BASE_URL, "mode": "hold", "frames": 13},
        {"name": "home-market", "url": BASE_URL, "mode": "scroll", "frames": 20, "target": 1550},
        {"name": "rental-ads-top", "url": ADS_URL, "mode": "hold", "frames": 14},
        {"name": "rental-ads-list", "url": ADS_URL, "mode": "scroll", "frames": 25, "target": 2100},
        {"name": "home-cta", "url": BASE_URL, "mode": "relative-hold", "frames": 18, "ratio": 0.84},
    ]


def _load_routes(raw: str) -> list[dict[str, object]]:
    if not raw.strip():
        return _default_routes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --routes-json: {exc}") from exc
    if not isinstance(value, list) or not value:
        raise ValueError("--routes-json must be a non-empty JSON array")
    routes: list[dict[str, object]] = []
    total_frames = 0
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Route {index} must be an object")
        url = str(item.get("url") or "").strip()
        if not url.startswith("https://karyabmashin.ir/"):
            raise ValueError(f"Route {index} is not first-party: {url}")
        mode = str(item.get("mode") or "hold").strip()
        if mode not in {"hold", "scroll", "relative-hold"}:
            raise ValueError(f"Route {index} has unsupported mode: {mode}")
        frames = int(item.get("frames") or 0)
        if frames <= 0:
            raise ValueError(f"Route {index} frames must be positive")
        total_frames += frames
        routes.append({**item, "url": url, "mode": mode, "frames": frames, "name": str(item.get("name") or f"route-{index+1}")})
    if not 60 <= total_frames <= 180:
        raise ValueError(f"CAMP capture frame budget must be 60..180 at {FPS_CAPTURE}fps; got {total_frames}")
    return routes


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a deterministic first-party Karyab Mashin mobile website walkthrough for rc7/CAMP reels.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--routes-json", default="", help="Optional first-party route plan JSON. Omit to preserve the rc7 rental capture contract.")
    parser.add_argument("--vertical", default="rental", help="Evidence label only; URLs must still be supplied explicitly via --routes-json for non-rental verticals.")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    work = Path(args.work).expanduser().resolve()
    frames_dir = work / "site-walkthrough-frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    routes = _load_routes(args.routes_json)

    timeline: list[dict[str, object]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
            locale="fa-IR",
            user_agent="Mozilla/5.0 (Linux; Android 16; KaryabMashin-VideoFactory/CAMP-13.2) AppleWebKit/537.36 Chrome/140 Mobile Safari/537.36",
        )
        page = context.new_page()
        frame_index = 0

        for route in routes:
            url = str(route["url"])
            mode = str(route["mode"])
            count = int(route["frames"])
            _goto(page, url)
            start = frame_index
            if mode == "hold":
                page.evaluate("window.scrollTo(0, 0)")
                frame_index = _hold_frames(page, frames_dir, frame_index, count)
            elif mode == "scroll":
                page.evaluate("window.scrollTo(0, 0)")
                max_y = float(page.evaluate("Math.max(0, document.body.scrollHeight - window.innerHeight)") or 0)
                target = min(max_y, float(route.get("target") or max_y))
                frame_index = _scroll_frames(page, frames_dir, frame_index, 0, target, count)
            else:
                max_y = float(page.evaluate("Math.max(0, document.body.scrollHeight - window.innerHeight)") or 0)
                ratio = max(0.0, min(1.0, float(route.get("ratio") or 0.8)))
                page.evaluate("y => window.scrollTo(0, y)", max_y * ratio)
                _wait(page, 450)
                frame_index = _hold_frames(page, frames_dir, frame_index, count)
            timeline.append({"page": route["name"], "url": url, "mode": mode, "frames": [start, frame_index - 1]})

        context.close()
        browser.close()

    if not args.routes_json:
        expected = 90
    else:
        expected = sum(int(item["frames"]) for item in routes)
    if frame_index != expected:
        raise SystemExit(f"WEBSITE_CAPTURE_FRAME_COUNT_MISMATCH: expected={expected} actual={frame_index}")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required for website capture")
    subprocess.run([
        ffmpeg,
        "-y",
        "-framerate", str(FPS_CAPTURE),
        "-i", str(frames_dir / "frame-%04d.png"),
        "-vf", f"fps=30,scale={WIDTH}:{HEIGHT}:flags=lanczos,format=yuv420p",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-movflags", "+faststart",
        "-an",
        str(output),
    ], check=True)

    evidence = {
        "authority": "KBM-CAMP-13.2-CINEMATIC-AD-MASTER-AUTHORITY" if args.routes_json else "PEP-V41-RC7-CINEMATIC-WEBSITE-20S-AUTHORITY",
        "source": "live-public-site",
        "vertical": args.vertical,
        "baseUrl": BASE_URL,
        "adsUrl": ADS_URL,
        "viewport": {"width": WIDTH, "height": HEIGHT},
        "captureFps": FPS_CAPTURE,
        "outputFps": 30,
        "frameCount": frame_index,
        "durationSeconds": frame_index / FPS_CAPTURE,
        "timeline": timeline,
        "routesExplicit": bool(args.routes_json),
        "output": str(output),
    }
    filename = "camp-website-capture.json" if args.routes_json else "package13-1-rc7-website-capture.json"
    (work / filename).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
