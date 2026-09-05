#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

FACTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY / "pipeline"))

import avalai_creative_client as ai_client
import tts_client


class AvalAiFullMigrationTests(unittest.TestCase):
    def test_critic_uses_avalai_endpoint_and_model(self) -> None:
        captured = {}

        def fake_json(method, path, *, payload=None, timeout=0, attempts=0):
            captured.update(
                method=method,
                path=path,
                payload=payload,
                timeout=timeout,
                attempts=attempts,
            )
            return {"choices": [{"message": {"content": '{"score": 9, "publishReady": true}'}}]}

        with mock.patch.dict(
            os.environ,
            {
                "AVALAI_API_KEY": "test-only",
                "KBM_AVALAI_VISION_MODEL": "gpt-5.6-sol",
            },
            clear=False,
        ), mock.patch.object(ai_client, "_json", side_effect=fake_json):
            result = ai_client.chat_json("Critique this reel")

        self.assertEqual(ai_client.BASE_URL, "https://api.avalai.ir/v1")
        self.assertEqual(ai_client.API_KEY_ENV, "AVALAI_API_KEY")
        self.assertEqual(captured["path"], "/chat/completions")
        self.assertEqual(captured["payload"]["model"], "gpt-5.6-sol")
        self.assertTrue(result["publishReady"])

    def test_active_tts_defaults_to_avalai_gemini(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"KBM_TTS_PROVIDER": "", "AVALAI_API_KEY": ""},
            clear=False,
        ):
            self.assertEqual(tts_client._provider()[0], "avalai")
            self.assertEqual(tts_client.DEFAULT_MODEL, "gemini-2.5-pro-tts")

    def test_no_legacy_openai_mini_tts_in_active_defaults(self) -> None:
        self.assertNotEqual(tts_client.DEFAULT_MODEL, "gpt-4o-mini-tts")
        self.assertNotEqual(tts_client.DEFAULT_MODEL, "text-to-speech-multilingual-v2")

    def test_video_generation_remains_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "CUPAI_VIDEO_GENERATION_DISABLED_UNVERIFIED_CONTRACT"
        ):
            ai_client.generate_video(
                "test", Path(tempfile.gettempdir()) / "never-created.mp4", safety_identifier="test"
            )


if __name__ == "__main__":
    unittest.main()
