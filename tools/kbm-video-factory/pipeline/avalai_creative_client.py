#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = os.environ.get("KBM_AI_BASE_URL", "https://api.avalai.ir/v1").strip().rstrip("/")
API_KEY_ENV = os.environ.get("KBM_AI_API_KEY_ENV", "AVALAI_API_KEY").strip() or "AVALAI_API_KEY"
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_MEDIA_BYTES = 120 * 1024 * 1024
RETRYABLE = {408, 429, 500, 502, 503, 504}


def configured() -> bool:
    return bool(os.environ.get(API_KEY_ENV, "").strip())


def _api_key() -> str:
    value = os.environ.get(API_KEY_ENV, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {API_KEY_ENV}")
    return value


def _safe_excerpt(text: str, limit: int = 320) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer ***", cleaned, flags=re.I)
    return cleaned[:limit]


def classify_cupai_error(error: Exception | str) -> dict[str, Any]:
    text = str(error)
    lowered = text.lower()
    code = "CUPAI_REQUEST_FAILED"
    retryable = False
    quota_blocked = False
    if "insufficient_quota" in lowered or "quota" in lowered and "insufficient" in lowered:
        code = "CUPAI_INSUFFICIENT_QUOTA"
        quota_blocked = True
    elif (
        "cupai_tts_channel_unavailable" in lowered
        or "no available channels for model" in lowered
        or "no api keys specified for model" in lowered
    ):
        code = "CUPAI_TTS_CHANNEL_UNAVAILABLE"
    elif "http 429" in lowered or "rate limit" in lowered:
        code = "CUPAI_RATE_LIMITED"
        retryable = True
    elif any(f"http {status}" in lowered for status in (408, 500, 502, 503, 504)):
        code = "CUPAI_UPSTREAM_RETRYABLE"
        retryable = True
    elif "http 401" in lowered or "unauthorized" in lowered or "invalid api" in lowered:
        code = "CUPAI_AUTH_FAILED"
    elif "http 403" in lowered or "cloudflare" in lowered or "cdn-cgi" in lowered or "html_gateway" in lowered:
        code = "CUPAI_EDGE_BLOCKED"
    elif "timed out" in lowered or "time-out" in lowered or "timeout" in lowered or "network error" in lowered:
        code = "CUPAI_NETWORK_RETRYABLE"
        retryable = True
    elif "unsupported" in lowered or "unknown parameter" in lowered:
        code = "CUPAI_UNSUPPORTED_PARAMETER"
    elif "invalid" in lowered or "bad request" in lowered or "http 400" in lowered:
        code = "CUPAI_INVALID_REQUEST"
    return {
        "code": code,
        "retryable": retryable,
        "quotaBlocked": quota_blocked,
        "reason": _safe_excerpt(text),
    }


def _request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 120.0,
    attempts: int = 2,
    accept: str = "application/json",
) -> tuple[bytes, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Accept": accept,
        "User-Agent": "KBM-Video-Factory/13.1.1",
    }
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    last = "AI gateway request failed"
    bounded_attempts = max(1, min(3, int(attempts)))
    for attempt in range(1, bounded_attempts + 1):
        request = urllib.request.Request(f"{BASE_URL}{path}", data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_type = str(response.headers.get("content-type", "")).lower()
                declared = int(response.headers.get("content-length", "0") or 0)
                limit = MAX_MEDIA_BYTES if not content_type.startswith("application/json") else MAX_JSON_BYTES
                if declared > limit:
                    raise RuntimeError("AI gateway response exceeded size limit")
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise RuntimeError("CupAI response exceeded size limit")
                return data, response.headers
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            last = f"CupAI HTTP {exc.code}: {_safe_excerpt(detail, 700)}"
            if exc.code not in RETRYABLE or attempt >= bounded_attempts:
                raise RuntimeError(last) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = f"AI gateway network error: {exc}"
            if attempt >= bounded_attempts:
                raise RuntimeError(last) from exc
        time.sleep(min(3.0, 0.75 * attempt))
    raise RuntimeError(last)


def _json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 120.0,
    attempts: int = 2,
) -> dict[str, Any]:
    raw, _headers = _request(method, path, payload=payload, timeout=timeout, attempts=attempts)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI gateway returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("AI gateway returned an invalid object")
    return value


def _extract_chat_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return ""


def _parse_json_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].lstrip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError("AI gateway did not return a JSON object")
    try:
        value = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI gateway returned malformed JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("AI gateway structured response is invalid")
    return value


def chat_json(
    prompt: str,
    *,
    images: list[Path] | None = None,
    model: str | None = None,
    max_images: int = 6,
    attempts: int = 2,
) -> dict[str, Any]:
    model = model or os.environ.get("KBM_AVALAI_VISION_MODEL", "gpt-5.6-sol").strip() or "gpt-5.6-sol"
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image in (images or [])[: max(1, min(max_images, 8))]:
        data = image.read_bytes()
        if len(data) > 8 * 1024 * 1024:
            continue
        mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
        encoded = base64.b64encode(data).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}", "detail": "low"}})
    response = _json(
        "POST",
        "/chat/completions",
        payload={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a senior commercial reel editor. Return only valid JSON. Never invent factual product specifications."},
                {"role": "user", "content": content},
            ],
        },
        timeout=180,
        attempts=attempts,
    )
    return _parse_json_text(_extract_chat_text(response))


def _validate_audio_response(raw: bytes, headers: Any) -> None:
    content_type = str(headers.get("content-type", "") or "").lower()
    prefix = raw[:512].decode("utf-8", errors="ignore").lower()
    if "text/html" in content_type or "<html" in prefix or "<!doctype html" in prefix or "cdn-cgi" in prefix:
        raise RuntimeError("CUPAI_TTS_HTML_GATEWAY_RESPONSE: direct TTS returned an HTML edge/gateway response")
    if len(raw) < 1024:
        raise RuntimeError("CupAI TTS response is empty")
    if content_type and not any(token in content_type for token in ("audio/", "application/octet-stream", "binary/octet-stream")):
        raise RuntimeError(f"CUPAI_TTS_UNEXPECTED_CONTENT_TYPE: {content_type[:120]}")


def synthesize_speech(
    text: str,
    destination: Path,
    *,
    voice: str = "alloy",
    instructions: str = "با لحن تبلیغاتی حرفه‌ای، طبیعی، مطمئن و پرانرژی فارسی صحبت کن.",
    model: str | None = None,
) -> dict[str, Any]:
    if not text.strip():
        raise RuntimeError("CupAI TTS input is empty")
    if len(text) > 5000:
        raise RuntimeError("CupAI TTS input is too long")
    model = model or os.environ.get("KBM_CUPAI_TTS_MODEL", "text-to-speech-multilingual-v2").strip() or "text-to-speech-multilingual-v2"
    payload = {
        "model": model,
        "voice": voice,
        "input": text,
        "instructions": instructions[:1200],
        "response_format": "mp3",
    }
    try:
        raw, headers = _request("POST", "/audio/speech", payload=payload, timeout=240, attempts=3, accept="audio/mpeg")
        _validate_audio_response(raw, headers)
    except Exception as first:
        diagnostic = classify_cupai_error(first)
        if diagnostic["code"] not in {"CUPAI_INVALID_REQUEST", "CUPAI_UNSUPPORTED_PARAMETER"}:
            raise RuntimeError(f"{diagnostic['code']}: {diagnostic['reason']}") from first
        compatibility_payload = {k: v for k, v in payload.items() if k != "instructions"}
        try:
            raw, headers = _request("POST", "/audio/speech", payload=compatibility_payload, timeout=240, attempts=2, accept="audio/mpeg")
            _validate_audio_response(raw, headers)
        except Exception as second:
            second_diagnostic = classify_cupai_error(second)
            raise RuntimeError(f"{second_diagnostic['code']}: {second_diagnostic['reason']}") from second

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return {
        "provider": "cupai",
        "model": model,
        "voice": voice,
        "kind": "speech",
        "path": str(destination),
        "bytes": len(raw),
        "contentType": headers.get("content-type"),
    }


def generate_image(prompt: str, destination: Path, *, model: str | None = None) -> dict[str, Any]:
    model = model or os.environ.get("KBM_CUPAI_IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2"
    response = _json(
        "POST",
        "/images/generations",
        payload={
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1536",
            "quality": os.environ.get("KBM_CUPAI_IMAGE_QUALITY", "medium"),
            "response_format": "b64_json",
        },
        timeout=240,
    )
    data = response.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise RuntimeError("CupAI image response is missing data")
    encoded = data[0].get("b64_json")
    if not isinstance(encoded, str) or not encoded:
        raise RuntimeError("CupAI image response did not include b64_json")
    binary = base64.b64decode(encoded)
    if len(binary) < 1024 or len(binary) > 30 * 1024 * 1024:
        raise RuntimeError("CupAI generated image size is invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(binary)
    return {"provider": "cupai", "model": model, "kind": "image", "path": str(destination), "bytes": len(binary)}


def create_video(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Fail closed: CupAI video async response/polling contract is not yet source-verified."""
    raise RuntimeError("CUPAI_VIDEO_GENERATION_DISABLED_UNVERIFIED_CONTRACT")


def wait_video(*args: Any, **kwargs: Any) -> dict[str, Any]:
    raise RuntimeError("CUPAI_VIDEO_GENERATION_DISABLED_UNVERIFIED_CONTRACT")


def generate_video(*args: Any, **kwargs: Any) -> dict[str, Any]:
    raise RuntimeError("CUPAI_VIDEO_GENERATION_DISABLED_UNVERIFIED_CONTRACT")


# Temporary source-compatibility alias; no AvalAI endpoint or credential is used.
classify_avalai_error = classify_cupai_error
