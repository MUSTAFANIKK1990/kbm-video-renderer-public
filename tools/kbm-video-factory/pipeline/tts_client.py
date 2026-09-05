#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROVIDERS = {
    "cupai": {
        "base_url": "https://api.cupai.ir/v1",
        "api_key_env": "CUPAI_API_KEY",
        "model_env": "KBM_CUPAI_TTS_MODEL",
    },
    "avalai": {
        "base_url": "https://api.avalai.ir/v1",
        "api_key_env": "AVALAI_API_KEY",
        "model_env": "KBM_AVALAI_TTS_MODEL",
    },
}
DEFAULT_MODEL = "gemini-2.5-pro-tts"
MAX_AUDIO_BYTES = 32 * 1024 * 1024
RETRYABLE = {408, 429, 500, 502, 503, 504}
CHANNEL_UNAVAILABLE_TOKENS = ("no available channels for model", "no api keys specified for model")


def _provider() -> tuple[str, dict[str, str]]:
    name = os.environ.get("KBM_TTS_PROVIDER", "avalai").strip().lower() or "avalai"
    config = PROVIDERS.get(name)
    if not config:
        raise RuntimeError(f"TTS_PROVIDER_UNSUPPORTED: {name[:40]}")
    return name, config


def _api_key(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {env_name}")
    return value


def _safe_excerpt(text: str, limit: int = 500) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer ***", cleaned, flags=re.I)
    return cleaned[:limit]


def _is_channel_unavailable(status: int, detail: str) -> bool:
    normalized = detail.lower()
    return status in {403, 424} and any(token in normalized for token in CHANNEL_UNAVAILABLE_TOKENS)


def _validate_audio(raw: bytes, headers: Any, provider: str) -> None:
    content_type = str(headers.get("content-type", "") or "").lower()
    prefix = raw[:512].decode("utf-8", errors="ignore").lower()
    if "text/html" in content_type or "<html" in prefix or "<!doctype html" in prefix or "cdn-cgi" in prefix:
        raise RuntimeError(f"{provider.upper()}_TTS_HTML_GATEWAY_RESPONSE")
    if len(raw) < 1024:
        raise RuntimeError(f"{provider.upper()}_TTS_EMPTY_AUDIO")
    if content_type and not any(token in content_type for token in ("audio/", "application/octet-stream", "binary/octet-stream")):
        raise RuntimeError(f"{provider.upper()}_TTS_UNEXPECTED_CONTENT_TYPE: {content_type[:120]}")


def _request_speech(provider: str, config: dict[str, str], payload: dict[str, Any], *, attempts: int) -> tuple[bytes, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {_api_key(config['api_key_env'])}",
        "Accept": "audio/mpeg",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "KBM-Video-Factory/TTS-Provider-01",
    }
    last = f"{provider} TTS request failed"
    for attempt in range(1, max(1, min(3, attempts)) + 1):
        request = urllib.request.Request(
            f"{config['base_url']}/audio/speech",
            data=body,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                declared = int(response.headers.get("content-length", "0") or 0)
                if declared > MAX_AUDIO_BYTES:
                    raise RuntimeError(f"{provider.upper()}_TTS_RESPONSE_TOO_LARGE")
                raw = response.read(MAX_AUDIO_BYTES + 1)
                if len(raw) > MAX_AUDIO_BYTES:
                    raise RuntimeError(f"{provider.upper()}_TTS_RESPONSE_TOO_LARGE")
                _validate_audio(raw, response.headers, provider)
                return raw, response.headers
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            last = f"{provider} HTTP {exc.code}: {_safe_excerpt(detail)}"
            # A configured key can still be routed to a provider group without a live
            # TTS channel. This is not retryable and must not spend the remaining takes.
            if _is_channel_unavailable(exc.code, detail):
                raise RuntimeError(f"{provider.upper()}_TTS_CHANNEL_UNAVAILABLE: {last}") from exc
            if exc.code not in RETRYABLE or attempt >= attempts:
                raise RuntimeError(last) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = f"{provider} network error: {_safe_excerpt(str(exc))}"
            if attempt >= attempts:
                raise RuntimeError(last) from exc
        time.sleep(min(3.0, 0.75 * attempt))
    raise RuntimeError(last)



def _local_persian_tts_fallback(text: str, destination: Path) -> dict[str, Any]:
    espeak = shutil.which("espeak-ng")
    ffmpeg = shutil.which("ffmpeg")
    if not espeak or not ffmpeg:
        raise RuntimeError("LOCAL_PERSIAN_TTS_FALLBACK_UNAVAILABLE")
    destination.parent.mkdir(parents=True, exist_ok=True)
    wave = destination.with_suffix(".local-fallback.wav")
    try:
        speech = subprocess.run(
            [espeak, "-v", "fa", "-s", "142", "-p", "48", "-a", "180", "-w", str(wave), text],
            check=False, capture_output=True, text=True, timeout=180,
        )
        if speech.returncode != 0 or not wave.is_file() or wave.stat().st_size < 1024:
            raise RuntimeError("LOCAL_PERSIAN_TTS_SYNTHESIS_FAILED: " + _safe_excerpt(speech.stderr))
        encode = subprocess.run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(wave),
                "-af", "highpass=f=80,lowpass=f=9000,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:a", "libmp3lame", "-b:a", "192k", str(destination),
            ],
            check=False, capture_output=True, text=True, timeout=180,
        )
        if encode.returncode != 0 or not destination.is_file() or destination.stat().st_size < 1024:
            raise RuntimeError("LOCAL_PERSIAN_TTS_ENCODING_FAILED: " + _safe_excerpt(encode.stderr))
    finally:
        wave.unlink(missing_ok=True)
    return {
        "provider": "kbm-local-offline-tts",
        "model": "espeak-ng-fa",
        "voice": "fa",
        "kind": "speech",
        "path": str(destination),
        "bytes": destination.stat().st_size,
        "contentType": "audio/mpeg",
    }

def synthesize_speech(
    text: str,
    destination: Path,
    *,
    voice: str = "alloy",
    instructions: str = "با لحن تبلیغاتی حرفه‌ای، طبیعی، مطمئن و پرانرژی فارسی صحبت کن.",
    model: str | None = None,
) -> dict[str, Any]:
    if not text.strip():
        raise RuntimeError("TTS input is empty")
    if len(text) > 5000:
        raise RuntimeError("TTS input is too long")

    provider, config = _provider()
    selected_model = model or os.environ.get(config["model_env"], DEFAULT_MODEL).strip() or DEFAULT_MODEL
    payload = {
        "model": selected_model,
        "voice": voice,
        "input": text,
        "instructions": instructions[:1200],
        "response_format": "mp3",
    }
    try:
        try:
            raw, headers = _request_speech(provider, config, payload, attempts=3)
        except RuntimeError as first:
            lowered = str(first).lower()
            if "http 400" not in lowered and "unsupported" not in lowered and "unknown parameter" not in lowered:
                raise
            compatibility_payload = {key: value for key, value in payload.items() if key != "instructions"}
            raw, headers = _request_speech(provider, config, compatibility_payload, attempts=2)
    except RuntimeError:
        if os.environ.get("KBM_LOCAL_TTS_FALLBACK", "1").strip() == "1":
            return _local_persian_tts_fallback(text, destination)
        raise

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return {
        "provider": provider,
        "model": selected_model,
        "voice": voice,
        "kind": "speech",
        "path": str(destination),
        "bytes": len(raw),
        "contentType": headers.get("content-type"),
    }
