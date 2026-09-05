#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
def build_sound_plan(storyboard:dict[str,Any],profile:dict[str,Any])->dict[str,Any]:
    events=profile.get("events") or {}; cues=[]
    for scene in storyboard.get("scenes",[]):
        transition=str(scene.get("transition") or "hard"); kind=events.get(transition,"whoosh"); cues.append({"atSeconds":scene.get("fromSeconds",0),"kind":kind,"gainDb":-9.0 if kind in {"whoosh","whip","riser"} else -7.0})
    if storyboard.get("scenes"): cues.append({"atSeconds":max(0.0,float(storyboard["durationSeconds"])-1.0),"kind":events.get("cta","sub-boom"),"gainDb":-6.5})
    return {"targetLufs":profile.get("targetLufs",-14),"truePeakDb":profile.get("truePeakDb",-1.0),"voicePriority":True,"cues":cues}
