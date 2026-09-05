#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from brand_director import resolve_brand
from providers import pexels_provider, pixabay_provider

PACKAGE = "KBM-VIDEO-FACTORY-BRAND-STOCK-PROVIDER-CONNECTION-13.1.1"
VERSION = "13.1.1"
SECRET_NAMES = ("PEXELS_API_KEY", "PIXABAY_API_KEY")


def _redact(value: object) -> str:
    text = str(value)
    for name in SECRET_NAMES:
        secret = os.environ.get(name, "").strip()
        if secret:
            text = text.replace(secret, "***")
    text = re.sub(r"([?&]key=)[^&\s]+", r"\1***", text, flags=re.IGNORECASE)
    return text[-500:]


def _probe(name: str, provider: Any, query: str) -> dict[str, Any]:
    if not provider.configured():
        return {"provider": name, "configured": False, "state": "MISSING_SECRET", "videos": 0, "images": 0}
    try:
        videos = provider.search_videos(query, per_page=3)
        images = provider.search_images(query, per_page=3)
        count = len(videos) + len(images)
        sample = None
        if videos:
            sample = {"mediaType": "video", "providerId": videos[0].get("providerId"), "sourceUrl": videos[0].get("sourceUrl")}
        elif images:
            sample = {"mediaType": "image", "providerId": images[0].get("providerId"), "sourceUrl": images[0].get("sourceUrl")}
        return {
            "provider": name,
            "configured": True,
            "state": "PASS" if count else "EMPTY",
            "videos": len(videos),
            "images": len(images),
            "sample": sample,
        }
    except Exception as exc:
        return {
            "provider": name,
            "configured": True,
            "state": "FAILED",
            "videos": 0,
            "images": 0,
            "httpStatus": getattr(exc, "code", None),
            "reason": _redact(exc),
        }


def _brand(root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="kbm-brand-preflight-") as temporary:
        public_job = Path(temporary) / "provider-preflight"
        result = resolve_brand(root, public_job)
    return {
        "ready": bool(result.get("ready")),
        "source": result.get("source"),
        "reason": result.get("reason"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Live first-party brand and stock provider preflight for KBM Package 13.1.1")
    parser.add_argument("--query", default="excavator construction machinery")
    parser.add_argument("--output", default="")
    parser.add_argument("--require-brand", action="store_true")
    parser.add_argument("--require-stock", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    report = {
        "package": PACKAGE,
        "version": VERSION,
        "brand": _brand(root),
        "providers": {
            "pexels": _probe("pexels", pexels_provider, args.query),
            "pixabay": _probe("pixabay", pixabay_provider, args.query),
        },
    }
    report["stockReady"] = all(item.get("state") == "PASS" for item in report["providers"].values())
    report["releaseConnectionReady"] = bool(report["brand"].get("ready")) and bool(report["stockReady"])

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        destination = Path(args.output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    print(rendered)

    if args.require_brand and not report["brand"].get("ready"):
        return 41
    if args.require_stock and not report["stockReady"]:
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
