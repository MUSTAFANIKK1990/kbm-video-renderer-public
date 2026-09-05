#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

USER_AGENT = "kbm-video-factory-package13/1.0"
MAX_JSON_BYTES = 2 * 1024 * 1024


def _json_request(url: str, headers: dict[str, str] | None = None, timeout: int = 25) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        declared = int(response.headers.get("Content-Length", "0") or 0)
        if declared > MAX_JSON_BYTES:
            raise RuntimeError("provider response too large")
        body = response.read(MAX_JSON_BYTES + 1)
    if len(body) > MAX_JSON_BYTES:
        raise RuntimeError("provider response too large")
    return json.loads(body)


def _video_file(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [f for f in files if isinstance(f, dict) and str(f.get("link") or "").startswith("https://")]
    if not candidates:
        return None
    candidates.sort(key=lambda f: (int(f.get("height") or 0) >= int(f.get("width") or 0), int(f.get("height") or 0), int(f.get("width") or 0)), reverse=True)
    return candidates[0]


def _slug_title(url: Any) -> str:
    try:
        path = urllib.parse.urlparse(str(url or "")).path.rstrip("/")
        slug = path.split("/")[-1]
        slug = re.sub(r"-\d+$", "", slug)
        return re.sub(r"[-_]+", " ", slug).strip()
    except Exception:
        return ""


@dataclass(frozen=True)
class PexelsProvider:
    key_env: str = "PEXELS_API_KEY"

    def configured(self) -> bool:
        return bool(os.environ.get(self.key_env, "").strip())

    def search_videos(self, query: str, per_page: int = 8) -> list[dict[str, Any]]:
        key = os.environ.get(self.key_env, "").strip()
        if not key:
            return []
        params = urllib.parse.urlencode({"query": query[:100], "orientation": "portrait", "size": "medium", "per_page": max(1, min(20, per_page))})
        payload = _json_request(f"https://api.pexels.com/v1/videos/search?{params}", {"Authorization": key})
        rows = payload.get("videos") if isinstance(payload, dict) else []
        output: list[dict[str, Any]] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            selected = _video_file(list(row.get("video_files") or []))
            if not selected:
                continue
            user = row.get("user") if isinstance(row.get("user"), dict) else {}
            source_url = row.get("url")
            output.append({
                "provider": "pexels",
                "mediaType": "video",
                "providerId": str(row.get("id") or ""),
                "width": int(selected.get("width") or row.get("width") or 0),
                "height": int(selected.get("height") or row.get("height") or 0),
                "duration": float(row.get("duration") or 0),
                "downloadUrl": selected.get("link"),
                "sourceUrl": source_url,
                "title": _slug_title(source_url),
                "creator": user.get("name"),
                "license": "PEXELS",
                "attribution": f"Video by {user.get('name') or 'Pexels contributor'} on Pexels",
            })
        return output

    def search_images(self, query: str, per_page: int = 6) -> list[dict[str, Any]]:
        key = os.environ.get(self.key_env, "").strip()
        if not key:
            return []
        params = urllib.parse.urlencode({"query": query[:100], "orientation": "portrait", "size": "large", "per_page": max(1, min(20, per_page))})
        payload = _json_request(f"https://api.pexels.com/v1/search?{params}", {"Authorization": key})
        rows = payload.get("photos") if isinstance(payload, dict) else []
        output: list[dict[str, Any]] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            src = row.get("src") if isinstance(row.get("src"), dict) else {}
            url = src.get("portrait") or src.get("large2x") or src.get("large")
            if not isinstance(url, str) or not url.startswith("https://"):
                continue
            source_url = row.get("url")
            output.append({
                "provider": "pexels",
                "mediaType": "image",
                "providerId": str(row.get("id") or ""),
                "width": int(row.get("width") or 0),
                "height": int(row.get("height") or 0),
                "duration": 0,
                "downloadUrl": url,
                "sourceUrl": source_url,
                "title": _slug_title(source_url),
                "alt": str(row.get("alt") or "").strip(),
                "creator": row.get("photographer"),
                "license": "PEXELS",
                "attribution": f"Photo by {row.get('photographer') or 'Pexels contributor'} on Pexels",
            })
        return output


@dataclass(frozen=True)
class PixabayProvider:
    key_env: str = "PIXABAY_API_KEY"

    def configured(self) -> bool:
        return bool(os.environ.get(self.key_env, "").strip())

    def _url(self, endpoint: str, query: str, per_page: int) -> str:
        params = urllib.parse.urlencode({"key": os.environ.get(self.key_env, "").strip(), "q": query[:100], "safesearch": "true", "order": "popular", "per_page": max(3, min(20, per_page)), "category": "industry"})
        return f"https://pixabay.com/api/{endpoint}?{params}"

    def search_videos(self, query: str, per_page: int = 8) -> list[dict[str, Any]]:
        if not self.configured():
            return []
        payload = _json_request(self._url("videos/", query, per_page))
        rows = payload.get("hits") if isinstance(payload, dict) else []
        output: list[dict[str, Any]] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            videos = row.get("videos") if isinstance(row.get("videos"), dict) else {}
            selected = videos.get("large") or videos.get("medium") or videos.get("small")
            if not isinstance(selected, dict):
                continue
            url = selected.get("url")
            if not isinstance(url, str) or not url.startswith("https://"):
                continue
            output.append({
                "provider": "pixabay",
                "mediaType": "video",
                "providerId": str(row.get("id") or ""),
                "width": int(selected.get("width") or 0),
                "height": int(selected.get("height") or 0),
                "duration": float(row.get("duration") or 0),
                "downloadUrl": url,
                "sourceUrl": row.get("pageURL"),
                "title": _slug_title(row.get("pageURL")),
                "tags": str(row.get("tags") or "").strip(),
                "creator": row.get("user"),
                "license": "PIXABAY",
                "attribution": f"Video by {row.get('user') or 'Pixabay contributor'} on Pixabay",
            })
        return output

    def search_images(self, query: str, per_page: int = 6) -> list[dict[str, Any]]:
        if not self.configured():
            return []
        payload = _json_request(self._url("", query, per_page) + "&orientation=vertical&min_width=720&min_height=1080")
        rows = payload.get("hits") if isinstance(payload, dict) else []
        output: list[dict[str, Any]] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            url = row.get("largeImageURL") or row.get("webformatURL")
            if not isinstance(url, str) or not url.startswith("https://"):
                continue
            output.append({
                "provider": "pixabay",
                "mediaType": "image",
                "providerId": str(row.get("id") or ""),
                "width": int(row.get("imageWidth") or 0),
                "height": int(row.get("imageHeight") or 0),
                "duration": 0,
                "downloadUrl": url,
                "sourceUrl": row.get("pageURL"),
                "title": _slug_title(row.get("pageURL")),
                "tags": str(row.get("tags") or "").strip(),
                "creator": row.get("user"),
                "license": "PIXABAY",
                "attribution": f"Image by {row.get('user') or 'Pixabay contributor'} on Pixabay",
            })
        return output


@dataclass(frozen=True)
class IranMediaGatewayProvider:
    url_env: str = "KBM_IRAN_MEDIA_SEARCH_URL"
    token_env: str = "KBM_IRAN_MEDIA_SEARCH_TOKEN"

    def configured(self) -> bool:
        return bool(os.environ.get(self.url_env, "").strip() and os.environ.get(self.token_env, "").strip())

    def _search(self, query: str, media_type: str, per_page: int) -> list[dict[str, Any]]:
        if not self.configured():
            return []
        base = os.environ.get(self.url_env, "").strip()
        if not base.startswith("https://"):
            raise RuntimeError("Iran media search gateway must use HTTPS")
        params = urllib.parse.urlencode({"q": query[:120], "type": media_type, "limit": max(1, min(20, per_page))})
        payload = _json_request(f"{base.rstrip('/')}?{params}", {"Authorization": f"Bearer {os.environ.get(self.token_env, '').strip()}"})
        rows = payload.get("results") if isinstance(payload, dict) else []
        output: list[dict[str, Any]] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item["provider"] = str(item.get("provider") or "iran-gateway")
            item["mediaType"] = media_type
            output.append(item)
        return output

    def search_videos(self, query: str, per_page: int = 8) -> list[dict[str, Any]]:
        return self._search(query, "video", per_page)

    def search_images(self, query: str, per_page: int = 6) -> list[dict[str, Any]]:
        return self._search(query, "image", per_page)


@dataclass(frozen=True)
class CupAIGeneratedProvider:
    api_key_env: str = "CUPAI_API_KEY"
    enable_env: str = "KBM_PACKAGE131_CUPAI_MEDIA"
    root_env: str = "KBM_PACKAGE131_MEDIA_DIR"

    def configured(self) -> bool:
        enabled = os.environ.get(self.enable_env, "0").strip().lower() in {"1", "true", "yes", "on"}
        return enabled and bool(os.environ.get(self.api_key_env, "").strip())

    def _root(self) -> Path:
        value = os.environ.get(self.root_env, "").strip()
        if not value:
            raise RuntimeError("KBM_PACKAGE131_MEDIA_DIR is not configured")
        root = Path(value).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _id(kind: str, query: str) -> str:
        return hashlib.sha256(f"{kind}:{query}".encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _prompt(query: str, media_type: str) -> str:
        movement = "Use controlled cinematic camera movement and clear subject separation. " if media_type == "video" else "Use foreground depth and clean negative space. "
        return (
            "Create a photorealistic commercial social-media shot for a heavy-machinery advertisement. "
            "Vertical 9:16 composition, realistic industrial lighting, physically plausible machinery, no text, no watermark, no logo, no unsafe action. "
            + movement + f"Requested shot: {query[:240]}"
        )

    def search_videos(self, query: str, per_page: int = 1) -> list[dict[str, Any]]:
        # Costly CupAI video generation stays fail-closed until its async response
        # and polling contract are source-verified and explicitly enabled.
        return []

    def search_images(self, query: str, per_page: int = 1) -> list[dict[str, Any]]:
        if not self.configured():
            return []
        from avalai_creative_client import generate_image
        key = self._id("image", query)
        path = self._root() / f"cupai-{key}.png"
        report = generate_image(self._prompt(query, "image"), path)
        return [{"provider": "cupai-generated", "providerId": key, "mediaType": "image", "width": 1024, "height": 1536, "duration": 0, "downloadUrl": "https://api.cupai.ir/v1/images/generations", "sourceUrl": "https://api.cupai.ir/", "title": query[:180], "creator": "KBM via CupAI", "license": "KBM-OWNED", "attribution": None, "localPath": str(path), "generation": {"model": report.get("model")}}]


pexels_provider = PexelsProvider()
pixabay_provider = PixabayProvider()
iran_media_provider = IranMediaGatewayProvider()
cupai_generated_provider = CupAIGeneratedProvider()
# Source compatibility only; both names resolve to the CupAI implementation.
avalai_generated_provider = cupai_generated_provider
