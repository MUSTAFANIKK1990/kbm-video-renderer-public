#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_ALLOWED = {"images.pexels.com", "videos.pexels.com", "cdn.pixabay.com", "pixabay.com", "www.pixabay.com"}


def _allowed_hosts() -> set[str]:
    extra = {x.strip().lower() for x in os.environ.get("KBM_MEDIA_DOWNLOAD_HOSTS", "").split(",") if x.strip()}
    return BASE_ALLOWED | extra


def _download(url: str, destination: Path, max_bytes: int) -> int:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in _allowed_hosts():
        raise RuntimeError("asset host is not allowlisted")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "kbm-video-factory-package13/1.0"})
    total = 0
    with urllib.request.urlopen(request, timeout=45) as response, destination.open("wb") as target:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise RuntimeError("asset exceeds max size")
            target.write(chunk)
    if total < 1024:
        raise RuntimeError("downloaded asset is empty")
    return total



def _normalize_video_for_render(path: Path) -> int:
    normalized = path.with_name(f"{path.stem}.normalized.mp4")
    normalized.unlink(missing_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(path),
        "-map", "0:v:0", "-map_metadata", "-1", "-an",
        "-vf", "scale='min(1080,iw)':'min(1920,ih)':force_original_aspect_ratio=decrease,format=yuv420p",
        "-r", "30",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-movflags", "+faststart",
        str(normalized),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0 or not normalized.is_file() or normalized.stat().st_size < 1024:
        normalized.unlink(missing_ok=True)
        raise RuntimeError(f"video normalization failed: {(result.stderr or '').strip()[-220:]}")
    normalized.replace(path)
    return path.stat().st_size


def _copy_generated(item: dict[str, Any], destination: Path, max_bytes: int) -> int:
    local = str(item.get("localPath") or "").strip()
    provider = str(item.get("provider") or "").strip().lower()
    license_id = str(item.get("license") or "").strip().upper()
    if provider != "cupai-generated" or license_id != "KBM-OWNED" or not local:
        raise RuntimeError("local asset is not trusted")
    source = Path(local).expanduser().resolve()
    allowed_root = Path(os.environ.get("KBM_PACKAGE131_MEDIA_DIR", source.parent)).expanduser().resolve()
    if allowed_root not in source.parents or not source.is_file():
        raise RuntimeError("generated local asset path is outside authority root")
    size = source.stat().st_size
    if size < 1024 or size > max_bytes:
        raise RuntimeError("generated local asset size is invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return size


def _extension(item: dict[str, Any]) -> str:
    media_type = str(item.get("mediaType") or "video")
    local = str(item.get("localPath") or "").lower()
    if media_type == "image":
        if local.endswith(".png"):
            return "png"
        path = urllib.parse.urlparse(str(item.get("downloadUrl") or "")).path.lower()
        if path.endswith(".png"):
            return "png"
        if path.endswith(".webp"):
            return "webp"
        return "jpg"
    return "mp4"


def _identity(item: dict[str, Any]) -> str:
    provider = str(item.get("provider") or "").strip().lower()
    provider_id = str(item.get("providerId") or "").strip()
    source = str(item.get("sourceUrl") or "").strip()
    download = str(item.get("downloadUrl") or "").strip()
    return f"{provider}|{provider_id or source or download}"


def _candidate_groups(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for raw in report.get("candidates", []):
        if not isinstance(raw, dict):
            continue
        request_id = str(raw.get("requestId") or "").strip()
        if not request_id:
            continue
        groups.setdefault(request_id, []).append(raw)
    for rows in groups.values():
        rows.sort(
            key=lambda item: (
                float(item.get("semanticRelevance") or 0.0),
                float(item.get("score") or 0.0),
                int(item.get("height") or 0),
                int(item.get("width") or 0),
            ),
            reverse=True,
        )
    return groups


def route_assets(
    scout_report: dict[str, Any],
    public_dir: Path,
    materialize: bool = False,
    max_bytes: int = 80 * 1024 * 1024,
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    rights: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    groups = _candidate_groups(scout_report)
    used: set[str] = set()

    for req in scout_report.get("requests", []):
        if not isinstance(req, dict):
            continue
        request_id = str(req.get("id") or "")
        rows = groups.get(request_id, [])
        choices = [item for item in rows if _identity(item) not in used]
        if not choices:
            choices = rows[:1]
        if not choices:
            states.append({"sceneId": req.get("sceneId"), "state": "FALLBACK", "fallback": "base-video", "reason": "no-approved-candidate"})
            continue

        selected_item: dict[str, Any] | None = None
        selected_src: str | None = None
        selected_size = 0
        asset_id = f"ext-{req['sceneId']}"
        last_error = ""

        for item in choices:
            identity = _identity(item)
            media_type = str(item.get("mediaType") or req.get("mediaType") or "video")
            kind = "image" if media_type == "image" else "video"
            if not materialize:
                selected_item = item
                used.add(identity)
                break
            try:
                ext = _extension(item)
                dest = public_dir / f"{asset_id}.{ext}"
                dest.unlink(missing_ok=True)
                selected_size = _copy_generated(item, dest, max_bytes) if item.get("localPath") else _download(str(item["downloadUrl"]), dest, max_bytes)
                if kind == "video":
                    selected_size = _normalize_video_for_render(dest)
                selected_src = dest.name
                selected_item = item
                used.add(identity)
                states.append({
                    "sceneId": req["sceneId"],
                    "state": "PASS",
                    "kind": kind,
                    "bytes": selected_size,
                    "provider": item.get("provider"),
                    "providerId": item.get("providerId"),
                    "unique": True,
                })
                break
            except Exception as exc:
                last_error = str(exc)[-260:]
                states.append({
                    "sceneId": req["sceneId"],
                    "state": "CANDIDATE_REJECTED",
                    "provider": item.get("provider"),
                    "providerId": item.get("providerId"),
                    "reason": last_error,
                })

        if not selected_item:
            states.append({"sceneId": req.get("sceneId"), "state": "FALLBACK", "fallback": "base-video", "reason": last_error or "all-candidates-failed"})
            continue

        item = selected_item
        selected.append(item)
        media_type = str(item.get("mediaType") or req.get("mediaType") or "video")
        kind = "image" if media_type == "image" else "video"
        decision = item.get("rightsDecision") if isinstance(item.get("rightsDecision"), dict) else {}
        if selected_src:
            assets.append({
                "id": asset_id,
                "kind": kind,
                "src": selected_src,
                "fallback": "base-video",
                "provider": item.get("provider"),
                "providerId": item.get("providerId"),
                "sourceUrl": item.get("sourceUrl"),
                "license": item.get("license"),
                "attribution": item.get("attribution"),
                "shotRole": item.get("shotRole"),
                "semanticRelevance": item.get("semanticRelevance"),
                "score": item.get("score"),
                "rightsDecision": decision,
            })
        rights.append({
            "assetId": asset_id,
            "sceneId": req["sceneId"],
            "mediaType": media_type,
            "provider": item.get("provider"),
            "providerId": item.get("providerId"),
            "sourceUrl": item.get("sourceUrl"),
            "creator": item.get("creator"),
            "license": item.get("license"),
            "attribution": item.get("attribution"),
            "rightsApproved": bool(decision.get("approved")),
            "materialized": bool(selected_src),
            "uniqueIdentity": _identity(item),
            "generation": item.get("generation") if isinstance(item.get("generation"), dict) else None,
        })

    unique_selected = len({_identity(item) for item in selected})
    return {
        "selected": selected,
        "assets": assets,
        "rights": rights,
        "states": states,
        "selectionPolicy": "highest-semantic-unused-identity-first",
        "uniqueSelectedCount": unique_selected,
        "duplicateSelectedCount": max(0, len(selected) - unique_selected),
    }
