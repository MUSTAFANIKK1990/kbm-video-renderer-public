#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def expand(value: str, context: dict[str, str]) -> str:
    for key, replacement in context.items():
        value = value.replace("{" + key + "}", replacement)
    return value


def run_command(command: list[str], context: dict[str, str], required: bool) -> bool:
    expanded = [expand(part, context) for part in command]
    executable = expanded[0]
    if shutil.which(executable) is None:
        message = f"Missing executable: {executable}"
        if required:
            raise RuntimeError(message)
        print(f"SKIP: {message}")
        return False

    print("RUN:", " ".join(expanded))
    completed = subprocess.run(expanded, check=False)
    if completed.returncode != 0:
        if required:
            raise RuntimeError(f"Stage failed with exit code {completed.returncode}")
        print(f"SKIP/FAIL: optional stage exited {completed.returncode}")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="KBM Video Factory preprocessing pipeline")
    parser.add_argument("--input", required=True, help="Raw input video")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).with_name("pipeline.example.json")),
        help="Pipeline JSON configuration",
    )
    parser.add_argument("--workdir", default=None, help="Override work directory")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 2

    config_path = Path(args.config).expanduser().resolve()
    config: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))

    workdir = Path(args.workdir or config.get("workdir", "./work")).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    context = {
        "input": str(input_path),
        "workdir": str(workdir),
    }

    report: list[dict[str, Any]] = []
    for stage in config.get("stages", []):
        stage_id = stage.get("id", "unnamed")
        if not stage.get("enabled", False):
            report.append({"id": stage_id, "status": "disabled"})
            continue

        if "command" not in stage:
            report.append({"id": stage_id, "status": "external-adapter"})
            print(f"EXTERNAL: {stage_id} - {stage.get('notes', '')}")
            continue

        try:
            ok = run_command(
                list(stage["command"]),
                context,
                bool(stage.get("required", False)),
            )
            report.append({"id": stage_id, "status": "ok" if ok else "skipped"})
        except RuntimeError as exc:
            report.append({"id": stage_id, "status": "failed", "error": str(exc)})
            (workdir / "pipeline-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(str(exc), file=sys.stderr)
            return 1

    (workdir / "pipeline-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Pipeline report: {workdir / 'pipeline-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
