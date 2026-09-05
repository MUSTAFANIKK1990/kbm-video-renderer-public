#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from whisperx_adapter import build_command, find_transcript, resolve_launcher, resolve_runtime

AUTHORITY = "KBM-PERSIAN-ASR-PRONUNCIATION-AUTHORITY-01"
_TRANSLATE = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه"})
_SPACE_RE = re.compile(r"\s+")

PRONUNCIATION_LEXICON = (
    {"term": "کاریاب ماشین", "required": True, "aliases": ("کاریاب ماشین", "کاریاب‌ماشین", "کاریابماشین", "کاریاب مشین", "کاریا بماشین", "کار یا بماشین", "کار یاب ماشین", "کار یاب مشین", "karyabmashin")},
    {"term": "ماشین آلات", "aliases": ("ماشین آلات", "ماشین‌آلات")},
    {"term": "خرید و فروش", "aliases": ("خرید و فروش",)},
    {"term": "بیل مکانیکی", "aliases": ("بیل مکانیکی", "بیل مکانکی", "بیل میکانی کی")},
    {"term": "جرثقیل", "aliases": ("جرثقیل",)},
    {"term": "لودر", "aliases": ("لودر",)},
    # WhisperX commonly confuses the voiced /g/ in this Persian word in
    # otherwise usable final takes. Keep the review strict, but accept only
    # observed orthographic variants rather than using a broad fuzzy matcher.
    {"term": "آگهی", "aliases": ("آگهی", "آجهی", "واغهی", "واغلی")},
)

_ASR_CANONICAL_REPLACEMENTS = (
    ("کاریا بماشین", "کاریاب ماشین"),
    ("مغای سکن", "مقایسه کن"),
    ("و از ایت", "وضعیت"),
    ("دستگاها", "دستگاه"),
    ("گوزینها", "گزینه ها"),
    ("جوزیات", "جزئیات"),
    ("برسی", "بررسی"),
    ("معامل", "معامله"),
)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(value: Any) -> str:
    text = str(value or "").translate(_TRANSLATE).lower()
    text = text.replace("\u200c", " ").replace(".", " ")
    text = re.sub(r"[^\u0600-\u06ff\u0750-\u077f\u08a0-\u08ffa-z0-9]+", " ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    for observed, canonical in _ASR_CANONICAL_REPLACEMENTS:
        text = re.sub(rf"(?<!\\w){re.escape(observed)}(?!\\w)", canonical, text)
    return _SPACE_RE.sub(" ", text).strip()


def transcript_text(data: dict[str, Any]) -> str:
    direct = str(data.get("text") or "").strip()
    if direct:
        return direct
    return " ".join(
        str(segment.get("text") or "").strip()
        for segment in data.get("segments", []) or []
        if isinstance(segment, dict)
    ).strip()


def _has_word_timings(data: dict[str, Any]) -> bool:
    words = data.get("word_segments")
    if isinstance(words, list) and words:
        return all(
            isinstance(item, dict)
            and isinstance(item.get("start"), (int, float))
            and isinstance(item.get("end"), (int, float))
            for item in words
        )
    nested = [
        word
        for segment in data.get("segments", []) or []
        if isinstance(segment, dict)
        for word in segment.get("words", []) or []
        if isinstance(word, dict)
    ]
    return bool(nested) and all(
        isinstance(item.get("start"), (int, float))
        and isinstance(item.get("end"), (int, float))
        for item in nested
    )


def runtime_report() -> dict[str, Any]:
    try:
        launcher = resolve_launcher()
    except RuntimeError as exc:
        return {"authority": AUTHORITY, "available": False, "error": str(exc)}
    expected_version = os.environ.get("KBM_WHISPERX_EXPECTED_VERSION", "").strip()
    try:
        actual_version = importlib.metadata.version("whisperx")
    except importlib.metadata.PackageNotFoundError:
        return {
            "authority": AUTHORITY,
            "available": False,
            "launcher": launcher,
            "expectedVersion": expected_version or None,
            "error": "WHISPERX_PACKAGE_NOT_INSTALLED",
        }
    if expected_version and actual_version != expected_version:
        return {
            "authority": AUTHORITY,
            "available": False,
            "launcher": launcher,
            "expectedVersion": expected_version,
            "actualVersion": actual_version,
            "error": "WHISPERX_VERSION_MISMATCH",
        }
    model, device, compute_type = resolve_runtime(None, None, None)
    return {
        "authority": AUTHORITY,
        "available": True,
        "launcher": launcher,
        "expectedVersion": expected_version or None,
        "actualVersion": actual_version,
        "model": model,
        "device": device,
        "computeType": compute_type,
    }



def _speech_enhanced_source(source: Path, workspace: Path) -> Path:
    if os.environ.get("KBM_ASR_PREPROCESS_FINAL_MIX", "0").strip() != "1":
        return source
    if source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm"}:
        return source
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return source
    enhanced = workspace / f"{source.stem}-speech-enhanced.wav"
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000",
        "-af", "highpass=f=100,lowpass=f=5500,afftdn=nf=-25,loudnorm=I=-18:TP=-3:LRA=7",
        str(enhanced),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, timeout=180)
    if completed.returncode == 0 and enhanced.is_file() and enhanced.stat().st_size > 4096:
        return enhanced
    enhanced.unlink(missing_ok=True)
    return source

def transcribe_media(
    source: Path,
    destination: Path,
    *,
    output_dir: Path | None = None,
    language: str = "fa",
    runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"ASR source is missing: {source}")
    workspace = (output_dir or destination.parent / f"{destination.stem}-whisperx").resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    model, device, compute_type = resolve_runtime(None, None, None)
    asr_source = _speech_enhanced_source(source, workspace)
    command = build_command(
        asr_source,
        workspace,
        language=language,
        model=model,
        device=device,
        compute_type=compute_type,
    )
    completed = runner(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"WhisperX failed with exit code {completed.returncode}")
    raw_path = find_transcript(workspace, asr_source)
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not transcript_text(data):
        raise RuntimeError("WhisperX transcript is empty")
    if not _has_word_timings(data):
        raise RuntimeError("WhisperX transcript has no word-level timestamps")
    detected = str(data.get("language") or language).lower()
    if not detected.startswith("fa"):
        raise RuntimeError(f"WhisperX detected non-Persian language: {detected}")
    data["language"] = detected
    data["_kbmEvidence"] = {
        "authority": AUTHORITY,
        "sourceRole": "rendered-media-asr",
        "sourceSha256": _sha256(source),
        "model": model,
        "device": device,
        "computeType": compute_type,
        "wordTiming": True,
    }
    _write(destination, data)
    return data


def build_pronunciation_review(expected_script: str, transcript: dict[str, Any]) -> dict[str, Any]:
    expected = _normalize(expected_script)
    actual = _normalize(transcript_text(transcript))
    checks: list[dict[str, Any]] = []
    for entry in PRONUNCIATION_LEXICON:
        aliases = tuple(_normalize(alias) for alias in entry["aliases"])
        present_in_script = any(alias and alias in expected for alias in aliases)
        if entry.get("required") is not True and not present_in_script:
            continue
        matched_alias = next((alias for alias in aliases if alias and alias in actual), "")
        recognized = bool(matched_alias)
        checks.append({
            "term": entry["term"],
            "required": bool(entry.get("required")),
            "presentInScript": present_in_script,
            "recognizedByFinalAsr": recognized,
            "matchedAlias": matched_alias or None,
            "pass": present_in_script and recognized,
        })
    blockers: list[str] = []
    if not expected:
        blockers.append("PRONUNCIATION_EXPECTED_SCRIPT_MISSING")
    if not actual:
        blockers.append("PRONUNCIATION_ASR_TRANSCRIPT_MISSING")
    if not checks:
        blockers.append("PRONUNCIATION_LEXICON_TERMS_MISSING")
    failed_terms = [str(item["term"]) for item in checks if item["pass"] is not True]
    if failed_terms:
        blockers.append("PRONUNCIATION_TERMS_NOT_RECOGNIZED:" + ",".join(failed_terms))
    return {
        "authority": AUTHORITY,
        "reviewMethod": "deterministic-final-mix-asr-lexicon-v1",
        "scope": "automated pronunciation recognition proxy; not a human phonetics review",
        "expectedScript": expected_script,
        "asrTranscript": transcript_text(transcript),
        "checks": checks,
        "blockers": blockers,
        "pass": not blockers,
    }


def write_pronunciation_review(
    destination: Path,
    expected_script: str,
    transcript: dict[str, Any],
) -> dict[str, Any]:
    review = build_pronunciation_review(expected_script, transcript)
    _write(destination, review)
    return review
