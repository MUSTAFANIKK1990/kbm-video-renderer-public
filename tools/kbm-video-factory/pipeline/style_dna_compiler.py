#!/usr/bin/env python3
from __future__ import annotations
import json, statistics
from pathlib import Path
from typing import Any
PACKAGE="KBM-VIDEO-FACTORY-PRO-EDIT-DESK-REFERENCE-DIRECTOR-11"; VERSION="0.11.0"
def compile_style_dna(analyses:list[dict[str,Any]],registry_profile:dict[str,Any],profile_id:str)->dict[str,Any]:
    resets=[float(x["medianVisualResetSeconds"]) for x in analyses if x.get("medianVisualResetSeconds")]; measured=statistics.median(resets) if resets else float(registry_profile.get("visualResetSeconds",2.4)); target=max(1.4,min(3.0,measured)); cuts=[float(x.get("cutsPerMinute",0)) for x in analyses]; energy=max(cuts) if cuts else (25.0 if registry_profile.get("brollDensity")=="high" else 16.0)
    return {"package":PACKAGE,"version":VERSION,"styleId":profile_id,"referenceCount":len(analyses),"visualResetSeconds":round(target,3),"editEnergy":"high" if energy>=20 else "medium" if energy>=10 else "low","brollDensity":registry_profile.get("brollDensity","medium"),"captionProfile":str(registry_profile.get("captionProfile") or "KBM-CAPTION-BOLD-INDUSTRIAL"),"soundProfile":registry_profile.get("soundProfile","industrial-pro"),"transitions":registry_profile.get("transitions",["hard","push","cross-zoom"]),"ratios":registry_profile.get("ratios",{"userFootage":0.55,"broll":0.25,"motion":0.12,"infographic":0.08}),"rules":{"singleCaptionLane":True,"duplicateCopy":False,"maxUnchangedSeconds":min(4.0,target*1.7),"rightsManifestRequired":True}}
def load_registry(root:Path,profile_id:str|None=None)->tuple[str,dict[str,Any]]:
    data=json.loads((root/"references"/"registry.json").read_text(encoding="utf-8")); pid=profile_id or data.get("defaultProfile") or "kbm-industrial-pro"; profile=(data.get("profiles") or {}).get(pid)
    if not isinstance(profile,dict): pid=data.get("defaultProfile") or "kbm-industrial-pro"; profile=(data.get("profiles") or {}).get(pid,{})
    return str(pid),dict(profile)
