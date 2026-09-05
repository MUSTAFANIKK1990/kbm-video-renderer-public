#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from typing import Any
from asset_router import route_assets
from broll_scout import scout
from caption_director_fa import professionalize
from editorial_critic import score as editorial_score
from quality_control import inspect_output
from reference_analyzer import analyze_reference
from render_router import render as render_with_fallback
from sound_designer_v2 import build_sound_plan
from storyboard_director import build_storyboard
from style_dna_compiler import compile_style_dna, load_registry
from timeline_compiler import compile_timeline, maybe_export_otio
PACKAGE="KBM-VIDEO-FACTORY-PRO-EDIT-DESK-REFERENCE-DIRECTOR-11"; VERSION="0.11.0"
def _write(path:Path,value:Any)->None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
def _arg_value(args:list[str],name:str,default:str)->str:
    try: return args[args.index(name)+1]
    except (ValueError,IndexError): return default
def _run_v2(root:Path,args:list[str])->int:
    command=[sys.executable,str(root/"pipeline"/"orchestrator_v2.py"),*args]
    if "--no-render" not in command: command.append("--no-render")
    return subprocess.run(command,cwd=root,check=False).returncode
def main()->int:
    p=argparse.ArgumentParser(add_help=False); p.add_argument("--reference",action="append",default=[]); p.add_argument("--reference-profile",default=None); p.add_argument("--reference-scene-threshold",type=float,default=0.30); p.add_argument("--enable-broll",action="store_true"); p.add_argument("--materialize-broll",action="store_true"); p.add_argument("--disable-pro-desk",action="store_true"); pro,base_args=p.parse_known_args()
    root=Path(__file__).resolve().parents[1]; job=_arg_value(base_args,"--job","kbm-smart-editor"); job="".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in job).strip("-")[:80] or "kbm-smart-editor"; work=root/"work"/job; public_job=root/"public"/"generated"/job; no_render="--no-render" in base_args
    rc=_run_v2(root,base_args)
    if rc!=0: return rc
    base_report=json.loads((work/"job-report.json").read_text(encoding="utf-8")); props_path=work/"render-props.json"; props=json.loads(props_path.read_text(encoding="utf-8"))
    if pro.disable_pro_desk:
        if no_render: return 0
        return subprocess.run([sys.executable,str(root/"pipeline"/"orchestrator_v2.py"),*base_args],cwd=root,check=False).returncode
    states=[]; analyses=[]
    for ref in pro.reference:
        try: analyses.append(analyze_reference(Path(ref),pro.reference_scene_threshold)); states.append({"stage":"reference-analyzer","state":"PASS","path":ref})
        except Exception as exc: states.append({"stage":"reference-analyzer","state":"FALLBACK","path":ref,"reason":str(exc)[-300:]})
    profile_id,registry_profile=load_registry(root,pro.reference_profile); style=compile_style_dna(analyses,registry_profile,profile_id); _write(work/"style-dna.json",style); states.append({"stage":"style-dna","state":"PASS","styleId":profile_id})
    brief_path=work/"creative-brief.json"; brief=json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else {}; script=str(brief.get("voiceoverScript") or "").strip(); fps=30; duration_frames=int(props.get("durationInFrames") or 1); duration=max(0.1,duration_frames/fps)
    storyboard=build_storyboard(script,duration,style); _write(work/"pro-storyboard.json",storyboard); states.append({"stage":"storyboard-director","state":"PASS","scenes":len(storyboard.get("scenes",[]))})
    scout_report=scout(storyboard,enabled=bool(pro.enable_broll or pro.materialize_broll)); _write(work/"broll-scout.json",scout_report); asset_report=route_assets(scout_report,public_job/"external",materialize=bool(pro.materialize_broll))
    for asset in asset_report.get("assets",[]): asset["src"]=f"generated/{job}/external/{asset['src']}"
    _write(work/"rights-manifest.json",asset_report.get("rights",[])); _write(work/"asset-routing.json",asset_report); states.append({"stage":"broll-scout","state":"PASS" if scout_report.get("candidates") else "FALLBACK","candidates":len(scout_report.get("candidates",[]))})
    compiled=compile_timeline(storyboard,asset_report,fps=fps); _write(work/"pro-timeline.json",compiled); otio=maybe_export_otio(compiled,work/"pro-timeline.otio"); states.append({"stage":"timeline-compiler","state":"PASS","otio":otio.get("status")})
    profiles=json.loads((root/"config"/"caption-profiles.json").read_text(encoding="utf-8")); caption_profile=profiles.get(style.get("captionProfile")) or profiles["KBM-CAPTION-BOLD-INDUSTRIAL"]; pro_captions=professionalize(list(props.get("captions") or []),caption_profile)
    sound_profiles=json.loads((root/"config"/"sound-design-profiles.json").read_text(encoding="utf-8")); sound_profile=sound_profiles.get(style.get("soundProfile")) or sound_profiles["industrial-pro"]; sound=build_sound_plan(storyboard,sound_profile); _write(work/"sound-design-plan.json",sound)
    props.update({"captions":pro_captions,"captionPolicy":"single-lane","captionProfile":caption_profile,"scenes":compiled.get("scenes",[]),"assets":compiled.get("assets",[]),"soundDesign":sound,"proEditDesk":{"enabled":True,"package":PACKAGE,"version":VERSION,"styleId":profile_id,"visualResetSeconds":style.get("visualResetSeconds"),"referenceCount":len(analyses),"brollEnabled":bool(pro.enable_broll or pro.materialize_broll)}}); _write(props_path,props)
    thresholds=json.loads((root/"config"/"editorial-thresholds.json").read_text(encoding="utf-8")); pre_score=editorial_score(props,style,asset_report.get("rights",[]),thresholds); _write(work/"editorial-preflight.json",pre_score)
    report={"package":PACKAGE,"version":VERSION,"job":job,"basePackageReport":str(work/"job-report.json"),"styleDNA":str(work/"style-dna.json"),"storyboard":str(work/"pro-storyboard.json"),"rightsManifest":str(work/"rights-manifest.json"),"props":str(props_path),"states":states,"preflight":pre_score,"rendered":False}
    if no_render: _write(work/"pro-edit-desk-report.json",report); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0
    source=Path(str(base_report.get("effectiveSource") or "")).expanduser().resolve(); output=Path(str(base_report.get("output") or root/"out"/f"{job}.mp4")).expanduser().resolve()
    try:
        render_report,remotion_error=render_with_fallback(root=root,source=source,props_path=props_path,template=str(props.get("templateId") or "KBM-V03-MACHINE-REVIEW"),output=output,duration_frames=duration_frames,allow_remotion=True); report["rendered"]=True; report["renderer"]=render_report; states.append({"stage":"render","state":"FALLBACK" if remotion_error else "PASS","reason":remotion_error[-300:] if remotion_error else None})
    except Exception as exc: states.append({"stage":"render","state":"FAILED","reason":str(exc)[-400:]}); _write(work/"pro-edit-desk-report.json",report); return 12
    try: qc=inspect_output(output); report["qc"]=qc; states.append({"stage":"quality-control","state":"PASS" if qc.get("pass") else "WARNING"})
    except Exception as exc: states.append({"stage":"quality-control","state":"WARNING","reason":str(exc)[-300:]})
    report["editorial"]=editorial_score(props,style,asset_report.get("rights",[]),thresholds); report["states"]=states; report["output"]=str(output); _write(work/"editorial-report.json",report["editorial"]); _write(work/"pro-edit-desk-report.json",report); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
