#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import release_runner as base

PACKAGE = "KBM-VIDEO-FACTORY-RUNNER-CUPAI-CINEMATIC-13.1.1"
VERSION = "13.1.1"
_ORIGINAL_VALIDATE_FINAL = base.validate_final_output
_ORIGINAL_REDACT = base._redact
_ORIGINAL_BUILD = base.build_command
_ALLOWED_EDIT_STYLES = {"balanced", "cinematic", "high-energy"}


def validated_pipeline_mode(value: str | None = None) -> str:
    mode = (value if value is not None else os.environ.get(base.PIPELINE_MODE_ENV, "")).strip().lower() or "v4"
    if mode not in {"v2", "v3", "v4", "v41"}:
        raise base.JobError(f"{base.PIPELINE_MODE_ENV} must be v2, v3, v4 or v41")
    return mode


def build_command(root: Path, job: dict[str, Any], input_path: Path, output_path: Path) -> list[str]:
    mode = validated_pipeline_mode(str(job.get("pipelineMode") or "v4"))
    if mode != "v41":
        return _ORIGINAL_BUILD(root, job, input_path, output_path)
    pipeline = (root / "pipeline" / "orchestrator_v41.py").resolve()
    if not pipeline.is_file():
        raise base.JobError("Selected Package 13.1.1 pipeline authority is missing")

    edit_style = os.environ.get("EDIT_STYLE", "high-energy").strip().lower() or "high-energy"
    if edit_style not in _ALLOWED_EDIT_STYLES:
        raise base.JobError("EDIT_STYLE must be balanced, cinematic or high-energy")
    campaign_brief_b64 = os.environ.get("CAMPAIGN_BRIEF_B64", "").strip()
    if len(campaign_brief_b64) > 1600:
        raise base.JobError("CAMPAIGN_BRIEF_B64 is too large")

    command = [
        sys.executable, str(pipeline),
        "--input", str(input_path),
        "--creative-preset", str(job["preset"]),
        "--template", str(job["template"]),
        "--avalai-voice", str(job["voice"]),
        "--max-seconds", str(job["maxSeconds"]),
        "--job", str(job["jobId"]),
        "--output", str(output_path),
        "--package131-mode", os.environ.get("KBM_PACKAGE131_MODE", "maximum"),
        "--edit-style", edit_style,
    ]
    if campaign_brief_b64:
        command.extend(["--campaign-brief-b64", campaign_brief_b64])
    return command


def validate_v41(root: Path, job_id: str) -> dict[str, Any]:
    path = root / "work" / job_id / "package13-1-report.json"
    if not path.is_file():
        raise base.JobError("Package 13.1.1 report is missing")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise base.JobError("Package 13.1.1 report is invalid") from exc

    if (
        report.get("package") != "KBM-VIDEO-FACTORY-CUPAI-LIVE-CREATIVE-HARDENING-13.1.1"
        or report.get("version") != "13.1.1"
        or report.get("pipelineMode") != "v41"
        or report.get("rendered") is not True
        or report.get("gatePass") is not True
    ):
        raise base.JobError("Package 13.1.1 report contract failed")

    brand_preflight = report.get("brandPreflight") if isinstance(report.get("brandPreflight"), dict) else {}
    if brand_preflight.get("configured") is not True or report.get("brandReady") is not True:
        raise base.JobError("Package 13.1.1 brand gate failed")

    voice = report.get("voiceDirector") if isinstance(report.get("voiceDirector"), dict) else {}
    if voice.get("complete") is not True:
        raise base.JobError("Package 13.1.1 voice gate failed")
    if voice.get("durationFit") is not True:
        selected_duration = float(voice.get("selectedDuration") or 0)
        target_duration = float(voice.get("targetSeconds") or 0)
        raise base.JobError(
            f"Package 13.1.1 voice duration gate failed: selected={selected_duration:.2f}s target={target_duration:.2f}s"
        )

    critic = report.get("critic") if isinstance(report.get("critic"), dict) else {}
    if critic.get("criticComplete") is not True:
        raise base.JobError("Package 13.1.1 critic evidence is incomplete")
    threshold = float(os.environ.get("KBM_PACKAGE131_CRITIC_THRESHOLD", "8.0") or 8.0)
    overall = float(critic.get("overall") or 0)
    if critic.get("publishReady") is not True or overall < threshold:
        raise base.JobError(f"Package 13.1.1 critic gate failed: overall={overall:.2f}")

    return {
        "pass": True,
        "cupaiConfigured": bool(report.get("cupaiConfigured")),
        "criticComplete": True,
        "criticOverall": round(overall, 2),
        "publishReady": True,
        "brandReady": True,
        "brandSource": brand_preflight.get("source"),
        "voiceEngine": voice.get("engine"),
        "voiceComplete": True,
        "voiceDurationFit": True,
        "voiceSelectedDuration": voice.get("selectedDuration"),
        "voiceTargetSeconds": voice.get("targetSeconds"),
        "report": str(path),
    }


def validate_final_output(path: Path, max_seconds: float) -> dict[str, Any]:
    result = _ORIGINAL_VALIDATE_FINAL(path, max_seconds)
    if validated_pipeline_mode() == "v41":
        root = Path(__file__).resolve().parents[1]
        job_id = os.environ.get("JOB_ID", "").strip()
        result["package131"] = validate_v41(root, job_id)
    return result


def redact(value: BaseException | str) -> str:
    text = _ORIGINAL_REDACT(value)
    secret = os.environ.get("CUPAI_API_KEY", "")
    if secret:
        text = text.replace(secret, "[redacted]")
    return text


def install() -> None:
    base.PACKAGE = PACKAGE
    base.VERSION = VERSION
    base.validated_pipeline_mode = validated_pipeline_mode
    base.build_command = build_command
    base.validate_final_output = validate_final_output
    base._redact = redact


def main() -> int:
    install()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
