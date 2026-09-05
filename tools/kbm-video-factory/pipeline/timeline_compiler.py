#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any


def compile_timeline(storyboard: dict[str, Any], asset_report: dict[str, Any], fps: int = 30) -> dict[str, Any]:
    selected = {r.get("sceneId"): r.get("assetId") for r in asset_report.get("rights", []) if r.get("materialized")}
    scenes: list[dict[str, Any]] = []
    for item in storyboard.get("scenes", []):
        source_kind = str(item.get("kind") or "video")
        render_kind = "video" if source_kind == "broll" else source_kind
        scene = {
            "id": item["id"],
            "from": int(round(float(item["fromSeconds"]) * fps)),
            "to": int(round(float(item["toSeconds"]) * fps)),
            "kind": render_kind,
            "transitionIn": item.get("transition") or "hard",
            "transitionOut": item.get("transitionOut") or "hard",
            "motion": item.get("motion") or ("punch" if source_kind in {"video", "broll"} else "slow-push"),
            "suppressCaption": bool(item.get("suppressCaption", source_kind == "motion-slide")),
            "intensity": float(item.get("intensity") or 0.5),
            "beatRole": item.get("beatRole") or "body",
        }
        asset_id = selected.get(item["id"])
        if asset_id:
            scene["assetId"] = asset_id
        if item.get("title"):
            scene["title"] = str(item.get("title"))[:100]
        elif source_kind == "motion-slide":
            scene["title"] = str(item.get("copy") or "کاریاب ماشین").strip()[:100] or "کاریاب ماشین"
        for key in ("kicker", "accentText"):
            if item.get(key):
                scene[key] = str(item.get(key))[:100]
        if isinstance(item.get("items"), list):
            scene["items"] = item.get("items")[:6]
        scenes.append(scene)
    return {
        "fps": fps,
        "durationSeconds": storyboard.get("durationSeconds"),
        "scenes": scenes,
        "assets": asset_report.get("assets", []),
        "energyCurve": storyboard.get("energyCurve") or [],
        "policy": storyboard.get("policy") or {},
    }


def maybe_export_otio(compiled: dict[str, Any], output: Path) -> dict[str, Any]:
    try:
        import opentimelineio as otio
    except Exception:
        return {"status": "SKIPPED", "reason": "OpenTimelineIO optional dependency not installed"}
    timeline = otio.schema.Timeline(name="KBM Full Cinematic Editorial")
    track = otio.schema.Track(name="Editorial", kind=otio.schema.TrackKind.Video)
    timeline.tracks.append(track)
    fps = float(compiled.get("fps") or 30)
    for scene in compiled.get("scenes", []):
        frames = max(1, int(scene["to"]) - int(scene["from"]))
        clip = otio.schema.Clip(name=str(scene.get("id")))
        clip.source_range = otio.opentime.TimeRange(
            otio.opentime.RationalTime(0, fps),
            otio.opentime.RationalTime(frames, fps),
        )
        clip.metadata["kbm"] = {"intensity": scene.get("intensity"), "beatRole": scene.get("beatRole")}
        track.append(clip)
    otio.adapters.write_to_file(timeline, str(output))
    return {"status": "PASS", "path": str(output)}
