from __future__ import annotations
import json, os, urllib.parse, urllib.request
from typing import Any

API = "https://pixabay.com/api/videos/"

def configured() -> bool:
    return bool(os.environ.get("PIXABAY_API_KEY", "").strip())

def search_videos(query: str, per_page: int = 6) -> list[dict[str, Any]]:
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key: return []
    url = API + "?" + urllib.parse.urlencode({"key": key, "q": query, "per_page": max(3, min(20, per_page)), "safesearch": "true"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"kbm-video-factory-11"}), timeout=15) as response:
        data = json.load(response)
    out=[]
    for item in data.get("hits", []) or []:
        variants=item.get("videos") or {}
        candidate=variants.get("medium") or variants.get("large") or variants.get("small")
        if not candidate or not candidate.get("url"): continue
        out.append({"provider":"pixabay","id":str(item.get("id")),"mediaType":"video","query":query,"width":candidate.get("width"),"height":candidate.get("height"),"duration":item.get("duration"),"downloadUrl":candidate.get("url"),"sourceUrl":item.get("pageURL"),"creator":item.get("user"),"license":"Pixabay Content License","attribution":"Pixabay"})
    return out
