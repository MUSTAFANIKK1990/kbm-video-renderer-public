#!/usr/bin/env python3
from __future__ import annotations

import github_video_monitor as base


def _blocker_action(message: str) -> str:
    upper = message.upper()
    actions: list[str] = []
    if "CUPAI_CREDIT_EXHAUSTED" in upper or ("CREDIT" in upper and "CUPAI" in upper):
        actions.append("اعتبار CupAI را بررسی/شارژ کنید و Workflow را مجدد اجرا کنید.")
    if "VOICE_DYNAMICS_LOW" in upper:
        actions.append("Voice Dynamics/Take Selection را اصلاح و نریشن را دوباره ارزیابی کنید؛ این مورد Provider Blocker نیست.")
    elif "VOICE_" in upper or "NARRATION" in upper:
        actions.append("Voice Director / Narration را بر اساس Evidence همان Run اصلاح و مجدد اجرا کنید.")
    if "VISUAL_STAGNATION" in upper or "SHOTVARIETY" in upper or "PACING" in upper:
        actions.append("Asset Diversity، Shot Rotation و Pacing تدوین را اصلاح و Final Critic را دوباره اجرا کنید.")
    if "CRITIC_HOOK" in upper:
        actions.append("Hook دو ثانیه اول باید در Renderer تقویت و دوباره Critic شود.")
    if "BRANDVISIBILITY" in upper:
        actions.append("Brand Lockup/End Card را در Safe Zone برجسته‌تر کنید و Critic را تکرار کنید.")
    if "CTASTRENGTH" in upper:
        actions.append("CTA نهایی را مستقیم‌تر و Action-oriented کنید و Critic را تکرار کنید.")
    if "AUDIO_LUFS" in upper or "AUDIO_CLIPPING" in upper or "AUDIO_" in upper:
        actions.append("Audio Mastering و Quality Gate را اصلاح/تکرار کنید.")
    if "RIGHTS" in upper:
        actions.append("Rights Evidence دارایی مشکل‌دار را تکمیل کنید.")
    if "RENDER" in upper:
        actions.append("Render dependency/asset را رفع و Remotion Render را مجدد اجرا کنید.")
    if not actions:
        actions.append("Root Cause این مرحله را رفع کنید و Workflow را مجدد اجرا کنید.")
    # Keep the Issue table readable while preserving multi-cause diagnosis.
    deduped: list[str] = []
    for item in actions:
        if item not in deduped:
            deduped.append(item)
    return " ".join(deduped[:4])


base._blocker_action = _blocker_action

if __name__ == "__main__":
    raise SystemExit(base.main())
