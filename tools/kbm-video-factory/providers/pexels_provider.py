from __future__ import annotations
import json, os, urllib.parse, urllib.request
from typing import Any

API = "https://api.pexels.com/videos/search"

def configured() -> bool:
    return bool(os.environ.get("PEXELS_API_KEY", "").strip())

def search_videos(query: str, per_page: int = 6) -> list[dict[str, Any]]:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key: return []
    url = API + "?" + urllib.parse.urlencode({"query": query, "per_page": max(1, min(12, per_page)), "orientation": "portrait"})
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "kbm-video-factory-11"})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.load(response)
    out = []
    for video in data.get("videos", []) or []:
        files = sorted((video.get("video_files") or []), key=lambda x: int(x.get("width") or 0) * int(x.get("height") or 0), reverse=True)
        candidate = next((f for f in files if str(f.get("file_type")) == "video/mp4" and f.get("link")), None)
        if not candidate: continue
        user = video.get("user") or {}
        out.append({"provider":"pexels","id":str(video.get("id")),"mediaType":"video","query":query,"width":candidate.get("width"),"height":candidate.get("height"),"duration":video.get("duration"),"downloadUrl":candidate.get("link"),"sourceUrl":video.get("url"),"creator":user.get("name"),"license":"Pexels License","attribution":"Pexels"})
    return out
