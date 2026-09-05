#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from avalai_creative_intelligence import critique_final, enabled
from cinematic_ad_protocol import release_gate

AUTHORITY = "KBM-CAMP-HOTFIX06-CUPAI-CRITIC-ONLY-RESUME-AUTHORITY-01"
SOURCE_AUTHORITY = "KBM-CAMP-FINAL-GATE-HOTFIX-06-BRAND-CTA-AUTHORITY"
EXPECTED_BLOCKER = "CRITIC_INCOMPLETE"
REQUIRED_PRECRITIC_CHECKS = ("technical", "renderer", "voice", "audio", "rights", "visual")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"INVALID_REQUIRED_JSON:{path.name}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"INVALID_REQUIRED_JSON_OBJECT:{path.name}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    if report.get("gatePass") is not False or report.get("releaseReady") is not False:
        errors.append("SOURCE_REPORT_NOT_BLOCKED")
    if blockers != [EXPECTED_BLOCKER]:
        errors.append("SOURCE_REPORT_BLOCKERS_NOT_CRITIC_ONLY")
    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    for name in REQUIRED_PRECRITIC_CHECKS:
        check = checks.get(name) if isinstance(checks.get(name), dict) else {}
        if check.get("pass") is not True or check.get("blockers"):
            errors.append(f"SOURCE_{name.upper()}_NOT_PASS")
    critic = checks.get("critic") if isinstance(checks.get("critic"), dict) else {}
    if critic.get("pass") is not False or critic.get("blockers") != [EXPECTED_BLOCKER]:
        errors.append("SOURCE_CRITIC_STATE_MISMATCH")
    return errors


def run_resume(
    *,
    video: Path,
    work: Path,
    source_run_id: str,
    source_artifact_id: str,
    source_artifact_digest: str,
) -> dict[str, Any]:
    video = video.expanduser().resolve()
    work = work.expanduser().resolve()
    if not video.is_file() or video.stat().st_size <= 0:
        raise SystemExit("SOURCE_FINAL_MP4_MISSING")
    source_report = _read_json(work / "camp-release-report.json")
    source_errors = validate_source_report(source_report)
    if source_errors:
        raise SystemExit(",".join(source_errors))
    if not enabled():
        raise SystemExit("CUPAI_CRITIC_NOT_CONFIGURED")

    before_sha = _sha256(video)
    previous_critic = _read_json(work / "camp-critic.json")
    _write_json(work / "camp-critic-pre-resume.json", previous_critic)

    critic = critique_final(video, work)
    after_sha = _sha256(video)
    if before_sha != after_sha:
        raise SystemExit("SOURCE_FINAL_MP4_CHANGED_DURING_CRITIC_RESUME")
    _write_json(work / "camp-critic-resume.json", critic)
    _write_json(work / "camp-critic.json", critic)

    report = release_gate(
        video=video,
        brief=_read_json(work / "camp-brief.json"),
        renderer=_read_json(work / "camp-renderer.json"),
        voice=_read_json(work / "package13-1-voice-manifest.json"),
        critic=critic,
        rights=_read_json(work / "camp-rights-evidence.json"),
        visual=_read_json(work / "camp-visual-evidence.json"),
    )
    report["resume"] = {
        "authority": AUTHORITY,
        "sourceAuthority": SOURCE_AUTHORITY,
        "criticOnlyResume": True,
        "renderExecuted": False,
        "mediaResearchExecuted": False,
        "voiceExecuted": False,
        "sourceRunId": str(source_run_id),
        "sourceArtifactId": str(source_artifact_id),
        "sourceArtifactDigest": str(source_artifact_digest),
        "sourceVideoSha256": before_sha,
        "postCriticVideoSha256": after_sha,
        "videoUnchanged": True,
        "criticComplete": critic.get("criticComplete") is True,
        "criticRequestAttempts": critic.get("criticRequestAttempts"),
    }
    _write_json(work / "camp-release-report.json", report)

    evidence = {
        "authority": AUTHORITY,
        "sourceAuthority": SOURCE_AUTHORITY,
        "criticOnlyResume": True,
        "renderExecuted": False,
        "sourceRunId": str(source_run_id),
        "sourceArtifactId": str(source_artifact_id),
        "sourceArtifactDigest": str(source_artifact_digest),
        "sourceVideoSha256": before_sha,
        "postCriticVideoSha256": after_sha,
        "videoUnchanged": True,
        "criticComplete": critic.get("criticComplete") is True,
        "criticErrorCode": (
            "CUPAI_INSUFFICIENT_QUOTA"
            if "insufficient_quota" in str(critic.get("criticError") or "").lower()
            else None
        ),
        "gatePass": report.get("gatePass") is True,
        "releaseReady": report.get("releaseReady") is True,
        "blockers": report.get("blockers") or [],
    }
    _write_json(work / "camp-critic-resume-evidence.json", evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume only the CAMP Hotfix06 final critic against the immutable rendered MP4.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--source-run-id", default=os.environ.get("SOURCE_RUN_ID", ""))
    parser.add_argument("--source-artifact-id", default=os.environ.get("SOURCE_ARTIFACT_ID", ""))
    parser.add_argument("--source-artifact-digest", default=os.environ.get("SOURCE_ARTIFACT_DIGEST", ""))
    args = parser.parse_args()
    evidence = run_resume(
        video=Path(args.video),
        work=Path(args.work),
        source_run_id=args.source_run_id,
        source_artifact_id=args.source_artifact_id,
        source_artifact_digest=args.source_artifact_digest,
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["gatePass"] and evidence["releaseReady"] else 73


if __name__ == "__main__":
    raise SystemExit(main())
