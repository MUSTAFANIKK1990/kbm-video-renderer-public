from __future__ import annotations
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PIPELINE=ROOT/"pipeline"
if str(PIPELINE) not in sys.path: sys.path.insert(0,str(PIPELINE))
from caption_director_fa import professionalize
from editorial_critic import score
from storyboard_director import build_storyboard
from style_dna_compiler import compile_style_dna
from timeline_compiler import compile_timeline
class Package11Tests(unittest.TestCase):
    def test_style_dna_clamps_visual_reset(self):
        style=compile_style_dna([{"medianVisualResetSeconds":4.7,"cutsPerMinute":22}],{"captionProfile":"KBM-CAPTION-BOLD-INDUSTRIAL","brollDensity":"high"},"test"); self.assertEqual(style["visualResetSeconds"],3.0); self.assertEqual(style["editEnergy"],"high")
    def test_storyboard_resets_under_limit(self):
        style={"visualResetSeconds":2.2,"brollDensity":"high","transitions":["hard","push"]}; board=build_storyboard("پروژه داغه. اجاره و خرید و فروش ماشین‌آلات را سریع‌تر انجام بده.",12.0,style); self.assertGreaterEqual(len(board["scenes"]),4); self.assertTrue(all(s["toSeconds"]>s["fromSeconds"] for s in board["scenes"])); self.assertLessEqual(max(s["toSeconds"]-s["fromSeconds"] for s in board["scenes"]),2.75)
    def test_caption_chunks_are_mobile_readable(self):
        cues=[{"text":"این یک زیرنویس فارسی طولانی برای تست موتور حرفه‌ای کاریاب ماشین است","from":0,"to":4,"words":[]}]; out=professionalize(cues,{"maxWords":5}); self.assertGreater(len(out),1); self.assertTrue(all(len(x["text"].split())<=5 for x in out))
    def test_timeline_maps_materialized_broll(self):
        board={"durationSeconds":4,"scenes":[{"id":"a","fromSeconds":0,"toSeconds":2,"kind":"broll","transition":"push"},{"id":"b","fromSeconds":2,"toSeconds":4,"kind":"motion-slide","transition":"hard","copy":"خدمات"}]}; assets={"assets":[{"id":"ext-a","kind":"video","src":"generated/x/external/a.mp4","fallback":"base-video"}],"rights":[{"sceneId":"a","assetId":"ext-a","materialized":True}]}; compiled=compile_timeline(board,assets,30); self.assertEqual(compiled["scenes"][0]["assetId"],"ext-a"); self.assertTrue(compiled["scenes"][1]["suppressCaption"])
    def test_editorial_score_passes_professional_defaults(self):
        thresholds=json.loads((ROOT/"config"/"editorial-thresholds.json").read_text(encoding="utf-8")); props={"scenes":[{"from":0,"to":60,"kind":"video","motion":"punch"},{"from":60,"to":120,"kind":"motion-slide","motion":"slow-push"},{"from":120,"to":180,"kind":"video","motion":"punch"}],"captions":[{"text":"تست","from":0,"to":30}],"captionProfile":{"fontSize":78,"maxLines":2},"soundDesign":{"cues":[]},"proEditDesk":{"enabled":True},"cta":"ثبت آگهی"}; result=score(props,{"visualResetSeconds":2},[],thresholds); self.assertGreaterEqual(result["score"],85); self.assertTrue(result["pass"])
if __name__=="__main__": unittest.main()
