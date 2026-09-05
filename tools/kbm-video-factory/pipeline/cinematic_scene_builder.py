#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from asset_registry import PACKAGE, VERSION, load_registry, resolve_assets


def _normalize(value: str) -> str:
    table = str.maketrans({"ي": "ی", "ك": "ک"})
    cleaned = value.translate(table)
    for char in "؟?!،,.؛:«»\"'()[]{}":
        cleaned = cleaned.replace(char, " ")
    return " ".join(cleaned.split()).strip().lower()


def is_duplicate_caption(caption: str, scene: dict[str, Any]) -> bool:
    a = _normalize(caption)
    b = _normalize(" ".join(str(scene.get(key) or "") for key in ("title", "accentText", "kicker")))
    if not a or not b:
        return False
    return a == b or a in b or b in a


def build_scene_props(scene_config: dict[str, Any], *, registry: dict[str, Any], asset_dir: Path | None) -> dict[str, Any]:
    target = scene_config.get("target") or {}
    fps = int(target.get("fps") or 30)
    duration_seconds = float(target.get("durationSeconds") or 0.0)
    if fps <= 0 or duration_seconds <= 0:
        raise RuntimeError("Cinematic scene config requires positive fps and durationSeconds")

    scenes: list[dict[str, Any]] = []
    last_end = 0.0
    for index, raw in enumerate(scene_config.get("scenes", []) or []):
        start = float(raw.get("fromSeconds") or 0.0)
        end = float(raw.get("toSeconds") or 0.0)
        if start < 0 or end <= start or end > duration_seconds + 0.001:
            raise RuntimeError(f"Invalid cinematic scene range at index {index}")
        if start < last_end - 0.001:
            raise RuntimeError(f"Cinematic scenes overlap at index {index}")
        last_end = end
        scenes.append({
            "id": str(raw.get("id") or f"scene-{index + 1:02d}"),
            "from": int(round(start * fps)),
            "to": max(int(round(start * fps)) + 1, int(round(end * fps))),
            "kind": str(raw.get("kind") or "video"),
            "assetId": raw.get("assetId"),
            "title": str(raw.get("title") or "") or None,
            "kicker": str(raw.get("kicker") or "") or None,
            "accentText": str(raw.get("accentText") or "") or None,
            "items": raw.get("items") or [],
            "transitionIn": str(raw.get("transitionIn") or "fade"),
            "transitionOut": str(raw.get("transitionOut") or "fade"),
            "motion": str(raw.get("motion") or "none"),
            "suppressCaption": bool(raw.get("suppressCaption", False)),
        })

    assets, diagnostics = resolve_assets(registry, asset_dir)
    if any(item["status"] == "FAILED" for item in diagnostics):
        raise RuntimeError("Required Package 10 asset missing")
    return {
        "package": PACKAGE,
        "version": VERSION,
        "templateId": str(scene_config.get("templateId") or "KBM-V03-MACHINE-REVIEW"),
        "title": str(scene_config.get("title") or "کاریاب ماشین"),
        "cta": str(scene_config.get("cta") or "ثبت آگهی"),
        "accent": str(scene_config.get("accent") or "#F4B400"),
        "background": str(scene_config.get("background") or "#0B1F33"),
        "durationInFrames": int(round(duration_seconds * fps)),
        "captionPolicy": "single-lane",
        "scenes": scenes,
        "assets": assets,
        "assetDiagnostics": diagnostics,
        "note": "Binary cinematic assets stay external to Git and fall back non-blockingly when optional.",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build Package 10 cinematic multi-asset render props")
    parser.add_argument("--config", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--asset-dir", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        config = json.loads(Path(args.config).expanduser().resolve().read_text(encoding="utf-8"))
        registry = load_registry(Path(args.registry).expanduser().resolve())
        props = build_scene_props(config, registry=registry, asset_dir=Path(args.asset_dir).expanduser().resolve() if args.asset_dir else None)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    except (RuntimeError, json.JSONDecodeError, ValueError) as exc:
        print(f"CINEMATIC SCENE BUILDER FAILED: {exc}")
        raise SystemExit(1)
