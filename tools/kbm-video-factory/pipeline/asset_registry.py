#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE = "KBM-VIDEO-FACTORY-CINEMATIC-MULTI-ASSET-EDITOR-10"
VERSION = "0.10.0"


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("Asset registry must contain an assets array")
    return data


def resolve_assets(registry: dict[str, Any], asset_dir: Path | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for raw in registry.get("assets", []) or []:
        asset_id = str(raw.get("id") or "").strip()
        filename = str(raw.get("filename") or "").strip()
        kind = str(raw.get("kind") or "image")
        fallback = str(raw.get("fallback") or "base-video")
        required = bool(raw.get("required", False))
        if not asset_id:
            raise RuntimeError("Asset id cannot be empty")
        candidate = (asset_dir / filename).resolve() if asset_dir and filename else None
        available = bool(candidate and candidate.is_file())
        resolved.append({"id": asset_id, "kind": kind, "src": candidate.as_uri() if available and candidate else None, "fallback": fallback})
        diagnostics.append({"id": asset_id, "filename": filename, "available": available, "required": required, "fallback": fallback, "status": "PASS" if available else ("FAILED" if required else "FALLBACK")})
    return resolved, diagnostics


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Resolve Package 10 external cinematic assets")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--asset-dir", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        registry = load_registry(Path(args.registry).expanduser().resolve())
        assets, diagnostics = resolve_assets(registry, Path(args.asset_dir).expanduser().resolve() if args.asset_dir else None)
        if any(item["status"] == "FAILED" for item in diagnostics):
            raise RuntimeError("One or more required cinematic assets are missing")
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"package": PACKAGE, "version": VERSION, "assets": assets, "diagnostics": diagnostics}, ensure_ascii=False, indent=2), encoding="utf-8")
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"ASSET REGISTRY FAILED: {exc}")
        raise SystemExit(1)
