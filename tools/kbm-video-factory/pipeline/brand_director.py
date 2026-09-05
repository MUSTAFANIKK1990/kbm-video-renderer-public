#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BRAND_ASSET_ID = "kbm-brand-logo"
KNOWN_REPO_PATHS = (
    "plugins/kbm-core/assets/media/kbm-visual-system-v3/ipui25/brand/kbm-logo-transparent.png",
    "plugins/kbm-core/assets/images/kbm-industrial-premium-ui-24/kbm-logo-transparent.png",
    "themes/kbm-theme-core-theme/assets/brand/kbm-logo-gold-gear.png",
)


def _copy(source: Path, public_job: Path) -> str:
    target_dir = public_job / "brand"
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() if source.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg", ".svg"} else ".png"
    target = target_dir / f"kbm-logo{suffix}"
    shutil.copy2(source, target)
    return f"generated/{public_job.name}/brand/{target.name}"


def _download(url: str, public_job: Path) -> str:
    parsed = urllib.parse.urlparse(url)
    allowed = {"karyabmashin.ir", "www.karyabmashin.ir"}
    allowed.update(x.strip().lower() for x in os.environ.get("KBM_BRAND_ASSET_HOSTS", "").split(",") if x.strip())
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in allowed:
        raise RuntimeError("brand logo host is not allowlisted")
    target_dir = public_job / "brand"
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".png", ".webp", ".jpg", ".jpeg", ".svg"}:
        suffix = ".png"
    target = target_dir / f"kbm-logo{suffix}"
    request = urllib.request.Request(url, headers={"User-Agent": "kbm-video-factory-package13/1.0"})
    total = 0
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as stream:
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > 8 * 1024 * 1024:
                raise RuntimeError("brand logo exceeds size limit")
            stream.write(chunk)
    if total < 256:
        raise RuntimeError("brand logo download is empty")
    return f"generated/{public_job.name}/brand/{target.name}"


def _owned_asset(src: str, *, source_url: str | None = None) -> dict[str, Any]:
    return {
        "id": BRAND_ASSET_ID,
        "kind": "image",
        "src": src,
        "fallback": "static-card",
        "provider": "kbm-owned",
        "license": "KBM-OWNED",
        "sourceUrl": source_url,
        "rightsApproved": True,
    }


def resolve_brand(root: Path, public_job: Path) -> dict[str, Any]:
    local_env = os.environ.get("KBM_BRAND_LOGO_LOCAL", "").strip()
    candidates: list[Path] = []
    if local_env:
        candidates.append(Path(local_env).expanduser().resolve())
    repo_root = root.parents[1]
    candidates.extend((repo_root / path).resolve() for path in KNOWN_REPO_PATHS)

    for candidate in candidates:
        if candidate.is_file():
            src = _copy(candidate, public_job)
            return {
                "ready": True,
                "source": "local",
                "asset": _owned_asset(src),
                "config": {
                    "logoAssetId": BRAND_ASSET_ID,
                    "logoSrc": src,
                    "requireLogo": True,
                    "watermark": True,
                    "logoReveal": True,
                    "endCard": True,
                    "site": "KARYABMASHIN.IR",
                    "name": "کاریاب ماشین",
                },
            }

    remote = os.environ.get("KBM_BRAND_LOGO_URL", "").strip()
    if remote:
        try:
            src = _download(remote, public_job)
            return {
                "ready": True,
                "source": "remote",
                "asset": _owned_asset(src, source_url=remote),
                "config": {
                    "logoAssetId": BRAND_ASSET_ID,
                    "logoSrc": src,
                    "requireLogo": True,
                    "watermark": True,
                    "logoReveal": True,
                    "endCard": True,
                    "site": "KARYABMASHIN.IR",
                    "name": "کاریاب ماشین",
                },
            }
        except Exception as exc:
            return {"ready": False, "source": "remote", "reason": str(exc)[-240:], "asset": None, "config": {"logoAssetId": BRAND_ASSET_ID, "requireLogo": True}}

    return {
        "ready": False,
        "source": "missing",
        "reason": "Official KBM logo asset is not configured",
        "asset": None,
        "config": {
            "logoAssetId": BRAND_ASSET_ID,
            "requireLogo": True,
            "watermark": False,
            "logoReveal": False,
            "endCard": True,
            "site": "KARYABMASHIN.IR",
            "name": "کاریاب ماشین",
        },
    }
