#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from avalai_creative_intelligence import critique_final, enabled

CANDIDATE = "13.1.2-rc.5"
AUTHORITY = "PEP-V41-CRITIC-RECHECK-RESUME-GATE-SEMANTICS-AUTHORITY"
PACKAGE = "KBM-VIDEO-FACTORY-CUPAI-LIVE-CREATIVE-HARDENING-13.1.1"
VERSION = "13.1.1"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gate_blockers(report: dict[str, Any], video: Path, critic: dict[str, Any], threshold: float) -> list[str]:
    blockers: list[str] = []
    base = report.get("package13") if isinstance(report.get("package13"), dict) else {}
    brand_preflight = report.get("brandPreflight") if isinstance(report.get("brandPreflight"), dict) else {}
    voice = report.get("voiceDirector") if isinstance(report.get("voiceDirector"), dict) else {}

    if report.get("package") != PACKAGE or report.get("version") != VERSION or report.get("pipelineMode") != "v41":
        blockers.append("V41_CONTRACT_MISMATCH")
    if not video.is_file():
        blockers.append("OUTPUT_MISSING")
    if brand_preflight.get("configured") is not True or bool(base.get("brandReady")) is not True:
        blockers.append("BRAND_NOT_READY")
    if voice.get("complete") is not True:
        blockers.append("VOICE_NOT_COMPLETE")
    if voice.get("durationFit") is not True:
        blockers.append("VOICE_DURATION_FIT_FAILED")

    if critic.get("criticComplete") is not True:
        blockers.append("CRITIC_INCOMPLETE")
    else:
        overall = float(critic.get("overall") or 0)
        if overall < threshold:
            blockers.append("CRITIC_BELOW_THRESHOLD")
        if critic.get("publishReady") is not True:
            blockers.append("CRITIC_NOT_PUBLISH_READY")

    return blockers


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-run only the Package 13.1.1 CupAI final critic against an existing rendered MP4.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--candidate", default=CANDIDATE)
    parser.add_argument("--source-run-id", default=os.environ.get("SOURCE_RUN_ID", ""))
    parser.add_argument("--source-artifact-id", default=os.environ.get("SOURCE_ARTIFACT_ID", ""))
    parser.add_argument("--source-artifact-digest", default=os.environ.get("SOURCE_ARTIFACT_DIGEST", ""))
    args = parser.parse_args()

    video = Path(args.video).expanduser().resolve()
    work = Path(args.work).expanduser().resolve()
    report_path = work / "package13-1-report.json"
    report = _read_json(report_path, {})
    if not isinstance(report, dict) or not report:
        raise SystemExit("Package 13.1.1 report is missing or invalid")
    if not video.is_file():
        raise SystemExit("Rendered MP4 is missing")
    if not enabled():
        raise SystemExit("CupAI critic is not configured for rc.5 recheck")

    before_sha = _sha256(video)
    previous_final = _read_json(work / "package13-1-cupai-critic.json", {})
    if isinstance(previous_final, dict) and previous_final:
        _write_json(work / "package13-1-cupai-critic-pre-recheck.json", previous_final)

    critic = critique_final(video, work)
    after_sha = _sha256(video)
    unchanged = before_sha == after_sha
    if not unchanged:
        raise SystemExit("Rendered MP4 changed during critic-only recheck")

    threshold = float(os.environ.get("KBM_PACKAGE131_CRITIC_THRESHOLD", "8.0") or 8.0)
    blockers = _gate_blockers(report, video, critic, threshold)
    gate_pass = not blockers

    _write_json(work / "package13-1-cupai-critic-recheck.json", critic)
    _write_json(work / "package13-1-cupai-critic.json", critic)

    states = report.get("states") if isinstance(report.get("states"), list) else []
    states.append({
        "stage": "cupai-final-critic-recheck",
        "state": "PASS" if gate_pass else "BLOCKED",
        "candidate": args.candidate,
        "authority": AUTHORITY,
        "criticComplete": critic.get("criticComplete") is True,
        "overall": critic.get("overall"),
        "publishReady": critic.get("publishReady"),
        "blockers": blockers,
        "sourceVideoSha256": before_sha,
    })

    report["rendered"] = video.is_file()
    report["critic"] = critic
    report["gatePass"] = gate_pass
    report["candidate"] = args.candidate
    report["releaseGateAuthority"] = AUTHORITY
    report["releaseGate"] = {
        "pass": gate_pass,
        "blockers": blockers,
        "threshold": threshold,
        "criticOnlyResume": True,
        "sourceVideoSha256": before_sha,
    }
    report["states"] = states
    _write_json(report_path, report)

    evidence = {
        "candidate": args.candidate,
        "authority": AUTHORITY,
        "package": PACKAGE,
        "version": VERSION,
        "pipelineMode": "v41",
        "criticOnlyResume": True,
        "renderExecuted": False,
        "sourceRunId": str(args.source_run_id),
        "sourceArtifactId": str(args.source_artifact_id),
        "sourceArtifactDigest": str(args.source_artifact_digest),
        "sourceVideoSha256": before_sha,
        "postCriticVideoSha256": after_sha,
        "videoUnchanged": unchanged,
        "criticComplete": critic.get("criticComplete") is True,
        "criticRequestAttempts": critic.get("criticRequestAttempts"),
        "criticFrameSampling": critic.get("frameSampling"),
        "criticFrameCount": critic.get("frameCount"),
        "criticOverall": critic.get("overall"),
        "criticPublishReady": critic.get("publishReady"),
        "criticError": str(critic.get("criticError") or "")[-400:],
        "threshold": threshold,
        "releaseReady": gate_pass,
        "blockers": blockers,
    }
    _write_json(work / "package13-1-critic-recheck-evidence.json", evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if gate_pass else 52


if __name__ == "__main__":
    raise SystemExit(main())
