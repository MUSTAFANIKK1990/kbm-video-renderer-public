#!/usr/bin/env python3
from __future__ import annotations
import re
from typing import Any
_SPLIT=re.compile(r"(?<=[\.؟!؛])\s+|\s*[،؛]\s*")
def _segments(script:str)->list[str]:
    items=[x.strip(" \n\t،؛.") for x in _SPLIT.split(script.strip()) if x.strip(" \n\t،؛.")]; return items or ([script.strip()] if script.strip() else [])
def build_storyboard(script:str,duration_seconds:float,style:dict[str,Any])->dict[str,Any]:
    parts=_segments(script) or [""]; weights=[max(3,len(x)) for x in parts]; total=float(sum(weights)); reset=max(1.4,min(3.0,float(style.get("visualResetSeconds",2.4)))); phrase_ranges=[]; cursor=0.0
    for i,(text,weight) in enumerate(zip(parts,weights)):
        end=duration_seconds if i==len(parts)-1 else min(duration_seconds,cursor+duration_seconds*weight/total); phrase_ranges.append((text,cursor,end)); cursor=end
    chunks=[]
    for text,start,end in phrase_ranges:
        span=max(0.0,end-start); count=1
        while count and span/count>reset*1.25: count+=1
        for i in range(count):
            a=start+span*i/count; b=end if i==count-1 else start+span*(i+1)/count; chunks.append((text,a,b))
    scenes=[]; transitions=style.get("transitions") or ["hard"]
    for seq,(text,start,end) in enumerate(chunks):
        kind="motion-slide" if seq and seq%5==2 else "broll" if seq and seq%3==1 and style.get("brollDensity") in {"high","medium"} else "video"
        scenes.append({"id":f"pro-scene-{seq+1:02d}","fromSeconds":round(start,3),"toSeconds":round(end,3),"kind":kind,"copy":text,"searchQuery":text[:120] or "heavy machinery","transition":transitions[seq%len(transitions)],"assetRequired":kind=="broll","caption":kind!="motion-slide"})
    return {"durationSeconds":round(duration_seconds,3),"visualResetTargetSeconds":reset,"scenes":scenes}
