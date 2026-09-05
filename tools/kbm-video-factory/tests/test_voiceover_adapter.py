from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from voiceover_adapter import (  # noqa: E402
    GATEWAY_TOKEN_ENV,
    _gateway_endpoint,
    synthesize_avalai_gateway,
)


class FakeResponse:
    def __init__(self, payload: bytes, content_type: str = "audio/mpeg") -> None:
        self.payload = payload
        self.status = 200
        self.headers = {
            "content-type": content_type,
            "x-avalai-request-id": "test-request-id",
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self.payload if limit < 0 else self.payload[:limit]


class AvalaiGatewayAdapterTests(unittest.TestCase):
    def test_gateway_endpoint_adds_tts_path(self) -> None:
        self.assertEqual(
            _gateway_endpoint("https://gateway.example.workers.dev/"),
            "https://gateway.example.workers.dev/v1/tts",
        )

    def test_gateway_endpoint_rejects_insecure_url(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "HTTPS"):
            _gateway_endpoint("http://gateway.example.test/v1/tts")

    def test_dry_run_does_not_require_or_disclose_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            report = synthesize_avalai_gateway(
                "متن تست",
                Path("voiceover.mp3"),
                gateway_url="https://gateway.example.workers.dev",
                dry_run=True,
            )
        self.assertFalse(report["tokenConfigured"])
        self.assertNotIn("token", {key.lower() for key in report if key != "tokenEnvironment"})

    def test_success_writes_audio_atomically(self) -> None:
        payload = b"ID3" + (b"a" * 1024)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voiceover.mp3"
            with patch.dict(os.environ, {GATEWAY_TOKEN_ENV: "test-secret"}, clear=True):
                with patch("voiceover_adapter.urlrequest.urlopen", return_value=FakeResponse(payload)):
                    report = synthesize_avalai_gateway(
                        "بیل مکانیکی آماده کار است.",
                        output,
                        gateway_url="https://gateway.example.workers.dev/v1/tts",
                    )
            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual(report["status"], "generated")
            self.assertEqual(report["attemptsUsed"], 1)
            self.assertNotIn("test-secret", str(report))

    def test_retries_one_transient_504(self) -> None:
        error = HTTPError(
            "https://gateway.example.workers.dev/v1/tts",
            504,
            "Gateway Timeout",
            {},
            io.BytesIO(b'{"error":"UPSTREAM_TIMEOUT"}'),
        )
        payload = b"ID3" + (b"b" * 1024)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voiceover.mp3"
            with patch.dict(os.environ, {GATEWAY_TOKEN_ENV: "test-secret"}, clear=True):
                with patch(
                    "voiceover_adapter.urlrequest.urlopen",
                    side_effect=[error, FakeResponse(payload)],
                ) as mocked:
                    with patch("voiceover_adapter.time.sleep", return_value=None):
                        report = synthesize_avalai_gateway(
                            "متن تست",
                            output,
                            gateway_url="https://gateway.example.workers.dev",
                            attempts=2,
                        )
            self.assertEqual(mocked.call_count, 2)
            self.assertEqual(report["attemptsUsed"], 2)

    def test_missing_token_fails_without_network_request(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("voiceover_adapter.urlrequest.urlopen") as mocked:
                with self.assertRaisesRegex(RuntimeError, GATEWAY_TOKEN_ENV):
                    synthesize_avalai_gateway(
                        "متن تست",
                        Path("voiceover.mp3"),
                        gateway_url="https://gateway.example.workers.dev",
                    )
        mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
