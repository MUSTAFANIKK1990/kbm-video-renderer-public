#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def detect_gpu() -> bool:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return False
    result = subprocess.run([nvidia_smi, "-L"], capture_output=True, text=True, check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def resolve_runtime(
    model: str | None,
    device: str | None,
    compute_type: str | None,
) -> tuple[str, str, str]:
    gpu = detect_gpu()
    resolved_device = device or os.getenv("KBM_WHISPERX_DEVICE") or ("cuda" if gpu else "cpu")
    resolved_model = model or os.getenv("KBM_WHISPERX_MODEL") or ("large-v3" if resolved_device == "cuda" else "small")
    resolved_compute = compute_type or os.getenv("KBM_WHISPERX_COMPUTE_TYPE") or (
        "float16" if resolved_device == "cuda" else "int8"
    )
    return resolved_model, resolved_device, resolved_compute


def resolve_launcher() -> list[str]:
    executable = shutil.which("whisperx")
    if executable:
        return [executable]
    if importlib.util.find_spec("whisperx") is not None:
        return [sys.executable, "-m", "whisperx"]
    raise RuntimeError(
        "WhisperX is not installed. Install it in a dedicated Python environment, then retry."
    )


def build_command(
    source: Path,
    output_dir: Path,
    *,
    language: str,
    model: str,
    device: str,
    compute_type: str,
) -> list[str]:
    return [
        *resolve_launcher(),
        str(source),
        "--language",
        language,
        "--model",
        model,
        "--device",
        device,
        "--compute_type",
        compute_type,
        "--vad_method",
        os.getenv("KBM_WHISPERX_VAD_METHOD", "silero"),
        "--vad_onset",
        os.getenv("KBM_WHISPERX_VAD_ONSET", "0.25"),
        "--vad_offset",
        os.getenv("KBM_WHISPERX_VAD_OFFSET", "0.20"),
        "--output_format",
        "json",
        "--output_dir",
        str(output_dir),
    ]


def find_transcript(output_dir: Path, source: Path) -> Path:
    preferred = output_dir / f"{source.stem}.json"
    if preferred.exists():
        return preferred
    candidates = sorted(output_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"WhisperX completed but no JSON transcript was found in {output_dir}")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WhisperX for Persian KBM captions")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--language", default="fa")
    parser.add_argument("--model", default=None)
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None)
    parser.add_argument("--compute-type", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        print(f"Input not found: {source}", file=sys.stderr)
        return 2

    model, device, compute_type = resolve_runtime(args.model, args.device, args.compute_type)
    try:
        command = build_command(
            source,
            output_dir,
            language=args.language,
            model=model,
            device=device,
            compute_type=compute_type,
        )
    except RuntimeError as exc:
        if args.dry_run:
            command = [
                "whisperx",
                str(source),
                "--language",
                args.language,
                "--model",
                model,
                "--device",
                device,
                "--compute_type",
                compute_type,
                "--output_format",
                "json",
                "--output_dir",
                str(output_dir),
            ]
        else:
            print(str(exc), file=sys.stderr)
            return 3

    report: dict[str, Any] = {
        "input": str(source),
        "outputDir": str(output_dir),
        "language": args.language,
        "model": model,
        "device": device,
        "computeType": compute_type,
        "command": command,
        "dryRun": args.dry_run,
    }

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("RUN:", " ".join(command))
    completed = subprocess.run(command, check=False)
    report["exitCode"] = completed.returncode
    if completed.returncode != 0:
        (output_dir / "adapter-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return completed.returncode

    try:
        transcript = find_transcript(output_dir, source)
    except RuntimeError as exc:
        report["error"] = str(exc)
        (output_dir / "adapter-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(str(exc), file=sys.stderr)
        return 4

    report["transcript"] = str(transcript)
    (output_dir / "adapter-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
