#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse

PACKAGE = "KBM-VIDEO-FACTORY-AVALAI-GATEWAY-TTS-06"
GATEWAY_TOKEN_ENV = "KBM_GATEWAY_TOKEN"
GATEWAY_URL_ENV = "KBM_GATEWAY_URL"
GATEWAY_RETRY_STATUSES = {502, 503, 504}
MAX_GATEWAY_AUDIO_BYTES = 25 * 1024 * 1024


def _gateway_endpoint(value: str) -> str:
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("AvalAI Gateway URL must be a valid HTTPS URL")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise RuntimeError("AvalAI Gateway URL must not contain credentials, query parameters or fragments")
    path = parsed.path.rstrip("/")
    if not path:
        path = "/v1/tts"
    elif path != "/v1/tts":
        raise RuntimeError("AvalAI Gateway URL path must be /v1/tts or empty")
    return parsed._replace(path=path, params="", query="", fragment="").geturl()


def synthesize_avalai_gateway(
    script: str,
    output: Path,
    *,
    gateway_url: str,
    voice: str = "alloy",
    timeout_seconds: float = 120.0,
    attempts: int = 2,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not script.strip():
        raise RuntimeError("Voiceover script is empty")
    endpoint = _gateway_endpoint(gateway_url)
    token = os.environ.get(GATEWAY_TOKEN_ENV, "").strip()
    timeout_seconds = max(10.0, min(300.0, float(timeout_seconds)))
    attempts = max(1, min(3, int(attempts)))
    output = output.expanduser().resolve()

    report: dict[str, Any] = {
        "package": PACKAGE,
        "engine": "avalai-gateway",
        "provider": "AvalAI",
        "model": "gateway-managed",
        "language": "fa-IR",
        "script": script,
        "output": str(output),
        "gateway": endpoint,
        "voice": voice,
        "timeoutSeconds": timeout_seconds,
        "maxAttempts": attempts,
        "tokenEnvironment": GATEWAY_TOKEN_ENV,
        "tokenConfigured": bool(token),
        "dryRun": dry_run,
    }
    if dry_run:
        return report
    if not token:
        raise RuntimeError(f"Missing required environment variable: {GATEWAY_TOKEN_ENV}")

    body = json.dumps({"text": script.strip(), "voice": voice}, ensure_ascii=False).encode("utf-8")
    request = urlrequest.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "audio/mpeg",
            "User-Agent": "KBM-Video-Factory/06",
        },
    )

    last_error = "unknown gateway error"
    for attempt in range(1, attempts + 1):
        try:
            with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                content_type = str(response.headers.get("content-type") or "").lower()
                audio = response.read(MAX_GATEWAY_AUDIO_BYTES + 1)
                if status < 200 or status >= 300:
                    raise RuntimeError(f"AvalAI Gateway returned HTTP {status}")
                if not content_type.startswith("audio/"):
                    raise RuntimeError(
                        f"AvalAI Gateway returned an invalid content type: {content_type or 'missing'}"
                    )
                if len(audio) <= 256:
                    raise RuntimeError("AvalAI Gateway returned an empty or invalid audio file")
                if len(audio) > MAX_GATEWAY_AUDIO_BYTES:
                    raise RuntimeError("AvalAI Gateway audio response exceeded the size limit")

                output.parent.mkdir(parents=True, exist_ok=True)
                temporary = output.with_suffix(output.suffix + ".tmp")
                temporary.write_bytes(audio)
                temporary.replace(output)
                report.update(
                    {
                        "status": "generated",
                        "attemptsUsed": attempt,
                        "contentType": content_type,
                        "sizeBytes": len(audio),
                        "requestId": response.headers.get("x-avalai-request-id"),
                    }
                )
                return report
        except urlerror.HTTPError as exc:
            status = int(exc.code)
            detail = exc.read(512).decode("utf-8", errors="replace").strip()
            last_error = f"AvalAI Gateway returned HTTP {status}: {detail or exc.reason}"
            if status not in GATEWAY_RETRY_STATUSES or attempt >= attempts:
                raise RuntimeError(last_error) from exc
        except (urlerror.URLError, TimeoutError, socket.timeout) as exc:
            last_error = f"AvalAI Gateway request failed: {exc.reason if isinstance(exc, urlerror.URLError) else exc}"
            if attempt >= attempts:
                raise RuntimeError(last_error) from exc

        time.sleep(min(2.0, 0.75 * attempt))

    raise RuntimeError(last_error)


def synthesize_piper(
    script: str,
    output: Path,
    *,
    model: Path,
    config: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not script.strip():
        raise RuntimeError("Voiceover script is empty")
    model = model.expanduser().resolve()
    if not model.exists():
        raise RuntimeError(f"Piper model not found: {model}")
    if config is not None:
        config = config.expanduser().resolve()
        if not config.exists():
            raise RuntimeError(f"Piper config not found: {config}")

    piper = shutil.which("piper")
    if not piper and not dry_run:
        raise RuntimeError("Piper executable is not available on PATH")
    piper = piper or "piper"

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [piper, "--model", str(model), "--output_file", str(output)]
    if config is not None:
        command += ["--config", str(config)]

    report = {
        "package": PACKAGE,
        "engine": "piper",
        "language": "fa-IR",
        "script": script,
        "output": str(output),
        "model": str(model),
        "config": str(config) if config else None,
        "command": command,
        "dryRun": dry_run,
    }
    if dry_run:
        return report

    print("RUN:", " ".join(command))
    subprocess.run(command, input=script, text=True, check=True)
    if not output.exists() or output.stat().st_size <= 0:
        raise RuntimeError("Piper did not produce a voiceover file")
    return report


def synthesize_chatterbox_fa(
    script: str,
    output: Path,
    *,
    farsi_tts_root: Path,
    model_path: Path | None = None,
    python_executable: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Use ddehghan/farsi-tts Chatterbox Persian adapter without vendoring model weights.

    The external repository exposes `python src/generate.py INPUT.json -m chatterbox`
    and writes generated WAV files under `<input-stem>/..._chatterbox.wav`.
    This adapter keeps KBM isolated from third-party model/code copies while providing
    a verified path for higher-naturalness Persian narration.
    """
    if not script.strip():
        raise RuntimeError("Voiceover script is empty")

    root = farsi_tts_root.expanduser().resolve()
    generator = root / "src" / "generate.py"
    if not generator.exists():
        raise RuntimeError(f"farsi-tts generate.py not found: {generator}")

    if model_path is not None:
        model_path = model_path.expanduser().resolve()
        if not model_path.exists():
            raise RuntimeError(f"Chatterbox Persian model not found: {model_path}")

    python = python_executable or sys.executable
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    request_path = output.parent / "chatterbox-fa-request.json"
    request_path.write_text(
        json.dumps([{"filename": "kbm-voiceover.wav", "text": script}], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    command = [python, str(generator), str(request_path), "-m", "chatterbox"]
    if model_path is not None:
        command += ["--model-path", str(model_path)]

    generated = request_path.parent / request_path.stem / "kbm-voiceover_chatterbox.wav"
    report = {
        "package": PACKAGE,
        "engine": "chatterbox-fa",
        "language": "fa-IR",
        "script": script,
        "output": str(output),
        "externalRoot": str(root),
        "model": str(model_path) if model_path else None,
        "command": command,
        "expectedGeneratedFile": str(generated),
        "dryRun": dry_run,
        "voiceStyle": "natural conversational Persian; not an imitation of any proprietary ChatGPT voice",
    }
    if dry_run:
        return report

    print("RUN:", " ".join(command))
    subprocess.run(command, cwd=str(root), check=True)
    if not generated.exists() or generated.stat().st_size <= 0:
        raise RuntimeError(f"Chatterbox Persian did not produce expected file: {generated}")
    shutil.copyfile(generated, output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize KBM Persian voiceover")
    parser.add_argument(
        "--engine",
        choices=["avalai-gateway", "piper", "chatterbox-fa"],
        default="piper",
    )
    parser.add_argument("--script", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--farsi-tts-root", default=None)
    parser.add_argument("--gateway-url", default=None)
    parser.add_argument("--voice", default="alloy")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--report", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        if args.engine == "avalai-gateway":
            gateway_url = args.gateway_url or os.environ.get(GATEWAY_URL_ENV, "")
            if not gateway_url:
                raise RuntimeError(
                    f"--gateway-url or environment variable {GATEWAY_URL_ENV} is required"
                )
            result = synthesize_avalai_gateway(
                args.script,
                Path(args.output),
                gateway_url=gateway_url,
                voice=args.voice,
                timeout_seconds=args.timeout_seconds,
                attempts=args.attempts,
                dry_run=args.dry_run,
            )
        elif args.engine == "chatterbox-fa":
            if not args.farsi_tts_root:
                raise RuntimeError("--farsi-tts-root is required for chatterbox-fa")
            result = synthesize_chatterbox_fa(
                args.script,
                Path(args.output),
                farsi_tts_root=Path(args.farsi_tts_root),
                model_path=Path(args.model) if args.model else None,
                dry_run=args.dry_run,
            )
        else:
            if not args.model:
                raise RuntimeError("--model is required for piper")
            result = synthesize_piper(
                args.script,
                Path(args.output).expanduser().resolve(),
                model=Path(args.model),
                config=Path(args.config) if args.config else None,
                dry_run=args.dry_run,
            )

        if args.report:
            report = Path(args.report).expanduser().resolve()
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"VOICEOVER FAILED: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
