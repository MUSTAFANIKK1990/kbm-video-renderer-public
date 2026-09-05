#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shutil, statistics, subprocess
from pathlib import Path
from typing import Any
PACKAGE = "KBM-VIDEO-FACTORY-PRO-EDIT-DESK-REFERENCE-DIRECTOR-11"
VERSION = "0.11.0"
PTS_RE = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")
def _exe(name: str) -> str:
    value = shutil.which(name)
    if not value: raise RuntimeError(f"Missing executable: {name}")
    return value
def _probe(path: Path) -> dict[str, Any]:
    raw = subprocess.check_output([_exe("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True)
    return json.loads(raw)
def _fps(stream: dict[str, Any]) -> float:
    value = str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"); a,b=value.split("/",1)
    return float(a)/max(1.0,float(b))
def analyze_reference(path: Path, scene_threshold: float = 0.30) -> dict[str, Any]:
    path=path.expanduser().resolve()
    if not path.is_file(): raise FileNotFoundError(path)
    meta=_probe(path); video=next((s for s in meta.get("streams",[]) if s.get("codec_type")=="video"),None)
    if not video: raise RuntimeError("Reference has no video stream")
    duration=float((meta.get("format") or {}).get("duration") or 0.0); width,height=int(video.get("width") or 0),int(video.get("height") or 0)
    cut_times=[]; warnings=[]
    try:
        result=subprocess.run([_exe("ffmpeg"),"-hide_banner","-loglevel","info","-i",str(path),"-vf",f"select='gt(scene,{max(0.05,min(0.95,scene_threshold))})',showinfo","-an","-f","null","-"],text=True,capture_output=True,timeout=max(20,min(150,int(duration*1.8+15))),check=False)
        cut_times=sorted({round(float(x),3) for x in PTS_RE.findall(result.stderr) if 0.05<float(x)<max(0.05,duration-0.05)})
    except Exception as exc: warnings.append(f"scene-detect-fallback: {str(exc)[-240:]}")
    boundaries=[0.0]+cut_times+([duration] if duration>0 else [])
    shot_lengths=[round(boundaries[i+1]-boundaries[i],3) for i in range(len(boundaries)-1) if boundaries[i+1]>boundaries[i]]
    median_reset=statistics.median(shot_lengths) if shot_lengths else duration; cuts_per_minute=(len(cut_times)/duration*60.0) if duration>0 else 0.0
    return {"package":PACKAGE,"version":VERSION,"path":str(path),"durationSeconds":round(duration,3),"width":width,"height":height,"orientation":"portrait" if height>width else "landscape" if width>height else "square","fps":round(_fps(video),3),"audioPresent":any(s.get("codec_type")=="audio" for s in meta.get("streams",[])),"sceneThreshold":scene_threshold,"cutTimesSeconds":cut_times,"sceneCount":len(shot_lengths),"medianVisualResetSeconds":round(float(median_reset),3) if shot_lengths else None,"cutsPerMinute":round(cuts_per_minute,2),"shotLengthsSeconds":shot_lengths[:180],"warnings":warnings}
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--input",required=True); p.add_argument("--output",required=True); p.add_argument("--scene-threshold",type=float,default=0.30); a=p.parse_args()
    report=analyze_reference(Path(a.input),a.scene_threshold); Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
