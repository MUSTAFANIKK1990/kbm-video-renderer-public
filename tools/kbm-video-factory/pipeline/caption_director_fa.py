#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
def professionalize(captions:list[dict[str,Any]],profile:dict[str,Any])->list[dict[str,Any]]:
    max_words=max(2,min(8,int(profile.get("maxWords",5)))); output=[]
    for cue in captions:
        text=str(cue.get("text") or "").strip()
        if not text: continue
        words=text.split()
        if len(words)<=max_words: output.append(dict(cue)); continue
        start,end=float(cue.get("from",0)),float(cue.get("to",0)); groups=[words[i:i+max_words] for i in range(0,len(words),max_words)]; span=max(1.0,end-start); weights=[max(1,sum(len(w) for w in g)) for g in groups]; total=sum(weights); cursor=start
        for gi,(group,weight) in enumerate(zip(groups,weights)):
            next_time=end if gi==len(groups)-1 else cursor+span*weight/total; output.append({"text":" ".join(group),"from":round(cursor,3),"to":round(next_time,3),"words":[]}); cursor=next_time
    return output
