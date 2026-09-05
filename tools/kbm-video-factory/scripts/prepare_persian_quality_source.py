#!/usr/bin/env python3
"""Materialize a licensed, current industrial source clip for no-publish QA."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


AUTHORITY = "KBM-PERSIAN-CINEMATIC-QUALITY-SOURCE-AUTHORITY-01"
USER_AGENT = "KBM-Quality-Validation/1.0"
MAX_DOWNLOAD_BYTES = 80 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 - fixed provider URLs
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("Provider returned a non-object response")
    return value


def pexels_candidates(query: str) -> list[dict[str, Any]]:
    token = os.environ.get("PEXELS_API_KEY", "").strip()
    if not token:
        return []
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": query, "per_page": 15, "orientation": "portrait", "size": "medium"}
    )
    data = request_json(url, {"Authorization": token})
    output: list[dict[str, Any]] = []
    for video in data.get("videos", []) or []:
        if not isinstance(video, dict) or float(video.get("duration") or 0) < 4:
            continue
        files = [item for item in video.get("video_files", []) or [] if isinstance(item, dict) and item.get("link")]
        if not files:
            continue
        file = max(files, key=lambda item: int(item.get("width") or 0) * int(item.get("height") or 0))
        output.append({
            "provider": "pexels", "id": str(video.get("id") or ""), "duration": float(video.get("duration") or 0),
            "downloadUrl": str(file["link"]), "sourceUrl": str(video.get("url") or ""), "license": "Pexels License",
            "attribution": str((video.get("user") or {}).get("name") or "Pexels"),
            "width": int(file.get("width") or 0), "height": int(file.get("height") or 0),
        })
    return output


def pixabay_candidates(query: str) -> list[dict[str, Any]]:
    token = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not token:
        return []
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
        {"key": token, "q": query, "per_page": 15, "safesearch": "true", "video_type": "film"}
    )
    data = request_json(url, {})
    output: list[dict[str, Any]] = []
    for video in data.get("hits", []) or []:
        if not isinstance(video, dict) or float(video.get("duration") or 0) < 4:
            continue
        variants = video.get("videos") or {}
        selected = next((variants.get(name) for name in ("large", "medium", "small", "tiny") if isinstance(variants.get(name), dict) and variants[name].get("url")), None)
        if not selected:
            continue
        output.append({
            "provider": "pixabay", "id": str(video.get("id") or ""), "duration": float(video.get("duration") or 0),
            "downloadUrl": str(selected["url"]), "sourceUrl": str(video.get("pageURL") or ""), "license": "Pixabay Content License",
            "attribution": str(video.get("user") or "Pixabay"),
            "width": int(selected.get("width") or 0), "height": int(selected.get("height") or 0),
        })
    return output


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310 - selected provider download URL
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_DOWNLOAD_BYTES:
            raise RuntimeError("Licensed source exceeds download limit")
        total = 0
        with destination.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError("Licensed source exceeded download limit")
                handle.write(chunk)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=22.0)
    args = parser.parse_args()
    if args.duration < 8 or args.duration > 60:
        raise SystemExit("--duration must be between 8 and 60 seconds")
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required to prepare the quality source")

    candidates = pexels_candidates(args.query) + pixabay_candidates(args.query)
    if not candidates:
        raise SystemExit("No licensed Pexels/Pixabay source was found; check configured provider credentials")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    raw = args.output.with_suffix(".licensed-source.mp4")
    candidates.sort(key=lambda item: (item["height"] >= item["width"], item["width"] * item["height"], item["duration"]), reverse=True)
    selected: dict[str, Any] | None = None
    rejected: list[str] = []
    for candidate in candidates:
        try:
            download(candidate["downloadUrl"], raw)
        except RuntimeError as exc:
            raw.unlink(missing_ok=True)
            rejected.append(f"{candidate['provider']}:{candidate['id']}:{exc}")
            continue
        selected = candidate
        break
    if selected is None:
        raise SystemExit("No licensed source met the download limit: " + "; ".join(rejected))
    try:
        command = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(raw), "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", f"{args.duration:.3f}", "-filter:v", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "128k", "-movflags", "+faststart", str(args.output),
        ]
        subprocess.run(command, check=True)
    finally:
        raw.unlink(missing_ok=True)
    report = {
        "authority": AUTHORITY, "purpose": "licensed-current-real-footage-only; no-publish-e2e-validation",
        "query": args.query, "requestedDurationSeconds": args.duration,
        "source": {key: selected[key] for key in ("provider", "id", "sourceUrl", "license", "attribution", "width", "height", "duration")},
        "rejectedCandidates": rejected,
        "output": {"path": str(args.output), "sha256": sha256(args.output), "bytes": args.output.stat().st_size,
                   "format": "1080x1920 H.264 yuv420p 30fps AAC 48k stereo faststart"},
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
