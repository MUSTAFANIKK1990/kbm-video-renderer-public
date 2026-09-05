#!/usr/bin/env python3
from __future__ import annotations

import math
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

import cinematic_website_20s_131 as base

# rc7 final-quality hotfix. Keep the same bounded package/candidate, sharpen
# question -> pain -> solution -> CTA cadence, and align the final mobile
# readability / shot-focus pass with the critic evidence contract.
NARRATION_SCRIPT = "ماشینت اجاره نرفته؟ خسته شدی؟ وقتشه بیشتر دیده بشی! وارد کاریاب ماشین شو؛ آگهی‌ات رو ثبت کن، مستقیم‌تر به متقاضی برس. همین حالا: KARYABMASHIN.IR"

if len(NARRATION_SCRIPT.split()) > 24:
    raise SystemExit("RC7_NARRATION_WORD_BUDGET_EXCEEDED")

_original_generate_sfx = base._generate_sfx
_original_build_props = base._build_props
_original_render = base.render_with_fallback


def _generate_final_sfx(public_dir: Path) -> None:
    """Extend the existing first-party SFX with a restrained industrial rhythm bed.

    The bed is synthetic/procedural, contains no third-party music, and stays
    intentionally low under narration. Final integrated loudness is mastered
    after render so the critic receives an active but non-clipped mix.
    """
    _original_generate_sfx(public_dir)
    sr = 48000
    total = int(sr * base.TARGET_SECONDS)
    rng = random.Random(131207)
    samples: list[float] = []
    for i in range(total):
        t = i / sr
        beat_phase = t % 0.5
        off_phase = (t + 0.25) % 0.5
        kick_env = math.exp(-18.0 * beat_phase)
        kick = math.sin(2 * math.pi * 58.0 * t) * kick_env * 0.13
        sub = math.sin(2 * math.pi * 46.0 * t) * (0.024 + 0.010 * math.sin(2 * math.pi * 0.5 * t))
        pulse_env = 0.5 + 0.5 * math.sin(2 * math.pi * 2.0 * t)
        pulse = math.sin(2 * math.pi * 116.0 * t) * pulse_env * 0.010
        hat_env = math.exp(-72.0 * off_phase)
        hat = (rng.random() * 2.0 - 1.0) * hat_env * 0.020
        transition = 0.0
        for center in (8.40, 14.10):
            distance = center - t
            if 0.0 < distance < 0.75:
                transition += (1.0 - distance / 0.75) * math.sin(2 * math.pi * (240.0 + 300.0 * (1.0 - distance / 0.75)) * t) * 0.010
        samples.append(kick + sub + pulse + hat + transition)
    base._write_pcm(public_dir / "rc7-bed.wav", samples, sr)


def _build_final_props(*, source_sha: str, website_sha: str, logo_url: str, narration_url: str, source_critic: dict[str, Any]) -> dict[str, Any]:
    props = _original_build_props(
        source_sha=source_sha,
        website_sha=website_sha,
        logo_url=logo_url,
        narration_url=narration_url,
        source_critic=source_critic,
    )
    props["subtitle"] = "ماشینت را در بازار تخصصی ماشین‌آلات بیشتر دیده کن"
    props["cta"] = "همین حالا وارد KARYABMASHIN.IR شو و آگهی ماشینت را ثبت کن."
    props["narrationVolume"] = 1.06
    sound = dict(props.get("soundDesign") or {})
    sound.update({
        "targetLufs": -14,
        "truePeakDb": -1.0,
        "voicePriority": True,
        "mastering": "post-render-loudnorm",
        "bed": "procedural-industrial-rhythm",
        "cues": [
            {"atSeconds": 0.0, "kind": "impact", "gainDb": -9},
            {"atSeconds": 1.45, "kind": "whoosh", "gainDb": -15},
            {"atSeconds": 3.15, "kind": "whoosh", "gainDb": -15},
            {"atSeconds": 5.35, "kind": "micro-click", "gainDb": -16},
            {"atSeconds": 8.40, "kind": "website-transition", "gainDb": -12},
            {"atSeconds": 8.75, "kind": "browser-click", "gainDb": -14},
            {"atSeconds": 11.95, "kind": "browser-click", "gainDb": -16},
            {"atSeconds": 14.20, "kind": "cta-impact", "gainDb": -10},
        ],
    })
    props["soundDesign"] = sound
    rc7 = dict(props.get("rc7") or {})
    effects = list(rc7.get("cinematicEffects") or [])
    for effect in (
        "beat-synced-hard-cuts",
        "shot-size-variation",
        "source-leadin-trim",
        "accelerated-complete-website-walkthrough",
        "procedural-industrial-rhythm-bed",
        "integrated-loudness-mastering",
        "high-contrast-mobile-captions",
        "centered-domain-cta",
        "cta-pulse",
    ):
        if effect not in effects:
            effects.append(effect)
    rc7.update({
        "cinematicEffects": effects,
        "websitePlaybackRate": 1.60,
        "machineFootageSeconds": 8.50,
        "websiteScreenSeconds": 5.70,
        "endCardSeconds": 5.80,
        "finalPolish": True,
        "mobileReadabilityPolish": True,
    })
    props["rc7"] = rc7
    return props


def _render_and_master(**kwargs: Any):
    renderer, render_error = _original_render(**kwargs)
    output = Path(kwargs.get("output") or "")
    if renderer.get("fallback") is True or not output.is_file():
        return renderer, render_error

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return renderer, f"{render_error or ''}; RC7_AUDIO_MASTERING_FFMPEG_MISSING".strip("; ")

    mastered = output.with_name(f"{output.stem}-mastered{output.suffix}")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(output),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-c:v",
        "copy",
        "-af",
        "loudnorm=I=-14:TP=-1.0:LRA=7",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(mastered),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=180)
    if result.returncode == 0 and mastered.is_file() and mastered.stat().st_size > 0:
        mastered.replace(output)
        patched = dict(renderer)
        patched["audioMastering"] = "loudnorm-I-14-TP-1-LRA-7"
        patched["finalPolish"] = True
        return patched, render_error

    mastered.unlink(missing_ok=True)
    diagnostic = (result.stderr or "RC7_AUDIO_MASTERING_FAILED")[-500:]
    combined = f"{render_error or ''}; RC7_AUDIO_MASTERING_FAILED: {diagnostic}".strip("; ")
    return renderer, combined


base.NARRATION_SCRIPT = NARRATION_SCRIPT
base._generate_sfx = _generate_final_sfx
base._build_props = _build_final_props
base.render_with_fallback = _render_and_master

if __name__ == "__main__":
    raise SystemExit(base.main())
