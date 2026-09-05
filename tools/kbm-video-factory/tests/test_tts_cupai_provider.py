#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import avalai_voice_director as voice_director
import tts_client


class _Response:
    def __init__(self) -> None:
        self.headers = {"content-type": "audio/mpeg", "content-length": "2048"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int) -> bytes:
        return b"ID3" + (b"0" * 2045)


class AvalAiTtsProviderTests(unittest.TestCase):
    def test_routes_active_tts_to_avalai(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["authorization"] = request.headers.get("Authorization")
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _Response()

        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ,
            {"KBM_TTS_PROVIDER": "avalai", "AVALAI_API_KEY": "avalai-test-key"},
            clear=False,
        ), mock.patch.object(tts_client.urllib.request, "urlopen", side_effect=fake_urlopen):
            report = tts_client.synthesize_speech(
                "سلام کاریاب ماشین", Path(temporary) / "voice.mp3", voice="alloy"
            )

        self.assertEqual(captured["url"], "https://api.avalai.ir/v1/audio/speech")
        self.assertEqual(captured["authorization"], "Bearer avalai-test-key")
        self.assertEqual(captured["payload"]["model"], "gemini-2.5-pro-tts")
        self.assertEqual(report["provider"], "avalai")
        self.assertEqual(report["bytes"], 2048)

    def test_missing_avalai_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ, {"KBM_TTS_PROVIDER": "avalai", "AVALAI_API_KEY": ""}, clear=False
        ):
            with self.assertRaisesRegex(RuntimeError, "AVALAI_API_KEY"):
                tts_client.synthesize_speech("سلام", Path(temporary) / "voice.mp3")

    def test_unknown_provider_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ, {"KBM_TTS_PROVIDER": "untrusted"}, clear=False
        ):
            with self.assertRaisesRegex(RuntimeError, "TTS_PROVIDER_UNSUPPORTED"):
                tts_client.synthesize_speech("سلام", Path(temporary) / "voice.mp3")

    def test_unavailable_channel_is_not_retried(self) -> None:
        calls = 0

        def unavailable(request, timeout):
            nonlocal calls
            calls += 1
            body = b'{"error":{"message":"There are no available channels for model gemini-2.5-pro-tts with api type audio/speech"}}'
            raise urllib.error.HTTPError(
                request.full_url, 424, "Failed Dependency", {}, io.BytesIO(body)
            )

        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ, {"KBM_TTS_PROVIDER": "avalai", "AVALAI_API_KEY": "avalai-test-key"},
            clear=False,
        ), mock.patch.object(tts_client.urllib.request, "urlopen", side_effect=unavailable):
            with self.assertRaisesRegex(RuntimeError, "AVALAI_TTS_CHANNEL_UNAVAILABLE"):
                tts_client.synthesize_speech(
                    "سلام کاریاب ماشین", Path(temporary) / "voice.mp3"
                )

        self.assertEqual(calls, 1)

    def test_voice_director_stops_remaining_takes_when_channel_is_unavailable(self) -> None:
        error = RuntimeError(
            "AVALAI_TTS_CHANNEL_UNAVAILABLE: avalai HTTP 424: no available channels for model"
        )
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            os.environ, {"KBM_PERSIAN_QUALITY_GATE": "1"}, clear=False
        ), mock.patch.object(voice_director, "synthesize_speech", side_effect=error) as synth:
            with self.assertRaisesRegex(
                RuntimeError, "CUPAI_TTS_ALL_TAKES_FAILED: CUPAI_TTS_CHANNEL_UNAVAILABLE"
            ):
                voice_director.direct_voice(
                    "کاریاب ماشین، آگهی فروش ماشین‌آلات سنگین را سریع‌تر به خریدار واقعی برسان.",
                    Path(temporary),
                    voice="alloy",
                    max_seconds=15,
                    maximum=True,
                )
            manifest = json.loads(
                (Path(temporary) / "package13-1-voice-manifest.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(synth.call_count, 1)
        self.assertEqual(manifest["attemptedTakeCount"], 1)
        self.assertTrue(manifest["providerChannelBlocked"])


if __name__ == "__main__":
    unittest.main()
