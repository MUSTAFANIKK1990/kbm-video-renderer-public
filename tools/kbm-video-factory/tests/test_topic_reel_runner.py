#!/usr/bin/env python3
from __future__ import annotations
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline"))
import topic_reel_runner
class TopicReelRunnerTests(unittest.TestCase):
    def test_topic_query_routes_to_licensed_industrial_search(self) -> None:
        self.assertIn("excavator", topic_reel_runner.source_query_for_topic("فروش بیل مکانیکی کوماتسو"))
        self.assertIn("workshop", topic_reel_runner.source_query_for_topic("تعمیر ماشین‌آلات سنگین"))
    def test_topic_command_keeps_camp_and_multilingual_tts_contract(self) -> None:
        command = topic_reel_runner.build_camp_command(ROOT, topic="فروش بیل مکانیکی", vertical="machine-sale", duration=20, goal="conversion", cta="ثبت آگهی", website_url="https://karyabmashin.ir/machine-sales/", source=ROOT / "out" / "source.mp4", output=ROOT / "out" / "output.mp4", job="topic-test", voice="onyx", edit_style="high-energy")
        self.assertIn(str(ROOT / "pipeline" / "orchestrator_camp.py"), command)
        self.assertIn("--camp-website-required", command)
        self.assertEqual(topic_reel_runner.TTS_MODEL, "text-to-speech-multilingual-v2")
    def test_manual_topic_workflow_is_no_publish_and_uses_cupai_tts(self) -> None:
        workflow = (REPO / ".github" / "workflows" / "kbm-topic-reel-no-publish.yml").read_text(encoding="utf-8")
        self.assertIn("KBM_EXTERNAL_PUBLISH: '0'", workflow)
        self.assertIn("KBM_CUPAI_TTS_MODEL: text-to-speech-multilingual-v2", workflow)
        self.assertIn("topic_reel_runner.py", workflow)
        self.assertNotIn("gpt-4o-mini-tts", workflow)
if __name__ == "__main__":
    unittest.main()
