#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from audio_mastering import master_for_reels
from avalai_creative_intelligence import critique_final
from cinematic_ad_protocol import release_gate
from orchestrator_camp import _rights_evidence, _visual_evidence
from render_router import render as render_with_fallback

AUTHORITY = "KBM-CAMP-CREATIVE-REPAIR-AUTHORITY-01"
SOURCE_JOB = "camp-machine-sale-hotfix06"
REPAIR_JOB = "camp-machine-sale-creative-repair-01"
SOURCE_VIDEO = "out/camp-machine-sale-20s-hotfix06.mp4"
EXPECTED_ARTIFACT_ID = "9757678320"
EXPECTED_ARTIFACT_DIGEST = "sha256:f65ee12f9dfd255b2d67f5d1577578015fcd6005dd51f6469d751bfc6d1fb0e6"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_preserved_mix(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
        "-map", "0:a:0", "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(destination),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=180)
    if result.returncode != 0 or not destination.is_file() or destination.stat().st_size < 4096:
        raise RuntimeError(f"PRESERVED_MIX_EXTRACTION_FAILED:{result.stderr[-400:]}")


def normalize_assets(asset_report: dict[str, Any], website_capture: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in asset_report.get("assets", []) if isinstance(asset_report.get("assets"), list) else []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if str(item.get("provider") or "").lower() == "avalai-generated":
            item["provider"] = "cupai-generated"
            item["providerMigration"] = "historical-kbm-owned-artifact-reuse"
        output.append(item)
    output.append({
        "id": "website-walkthrough",
        "kind": "video",
        "src": f"generated/{SOURCE_JOB}/camp-website-walkthrough.mp4",
        "provider": "karyabmashin-live-site",
        "sourceUrl": "https://karyabmashin.ir/",
        "license": "FIRST-PARTY-SITE-CAPTURE",
        "rightsDecision": {"approved": True, "license": "FIRST-PARTY-SITE-CAPTURE", "provider": "karyabmashin-live-site", "firstParty": True, "reasons": []},
    })
    missing = []
    for item in output:
        src = str(item.get("src") or "")
        if src and not (Path(__file__).resolve().parents[1] / "public" / src).is_file():
            missing.append(src)
    if missing or not website_capture.is_file():
        raise RuntimeError(f"REPAIR_ASSET_CAPSULE_INCOMPLETE:{missing}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded CAMP creative repair using one immutable released artifact capsule")
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--output", default=f"out/{REPAIR_JOB}.mp4")
    parser.add_argument("--work", default=f"work/{REPAIR_JOB}")
    parser.add_argument("--expected-video-sha256", required=True)
    parser.add_argument("--source-artifact-id", default=EXPECTED_ARTIFACT_ID)
    parser.add_argument("--source-artifact-digest", default=EXPECTED_ARTIFACT_DIGEST)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source_root = Path(args.source_root).expanduser().resolve()
    source_work = source_root / "work" / SOURCE_JOB
    source_video = source_root / SOURCE_VIDEO
    output = (root / args.output).resolve()
    work = (root / args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)

    if str(args.source_artifact_id) != EXPECTED_ARTIFACT_ID or str(args.source_artifact_digest) != EXPECTED_ARTIFACT_DIGEST:
        raise SystemExit("SOURCE_ARTIFACT_AUTHORITY_MISMATCH")
    if not source_video.is_file():
        raise SystemExit("SOURCE_FINAL_MP4_MISSING")
    source_sha = sha256(source_video)
    if source_sha != args.expected_video_sha256:
        raise SystemExit(f"SOURCE_FINAL_MP4_SHA256_MISMATCH:{source_sha}")

    required = {
        "brief": source_work / "camp-brief.json",
        "voice": source_work / "package13-1-voice-manifest.json",
        "routing": source_work / "package13-asset-routing.json",
        "rights": source_work / "camp-rights-evidence.json",
        "visual": source_work / "camp-visual-evidence.json",
        "website": root / "public" / "generated" / SOURCE_JOB / "camp-website-walkthrough.mp4",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise SystemExit(f"SOURCE_EVIDENCE_MISSING:{','.join(missing)}")

    asset_report = read_json(required["routing"], {})
    assets = normalize_assets(asset_report, required["website"])
    preserved_mix = root / "public" / "generated" / REPAIR_JOB / "preserved-final-mix.wav"
    extract_preserved_mix(source_video, preserved_mix)

    logo = "https://karyabmashin.ir/wp-content/plugins/kbm-visual-assets/assets/media/kbm-visual-system-v3/ipui25/brand/kbm-logo-transparent.png"
    props = {
        "media": assets[0]["src"],
        "narration": f"generated/{REPAIR_JOB}/preserved-final-mix.wav",
        "narrationVolume": 1,
        "durationInFrames": 600,
        "accent": "#F4B400",
        "background": "#071827",
        "cta": "وارد سایت شو؛ آگهی ماشینت را همین حالا ثبت کن",
        "captionPolicy": "single-lane",
        "captionProfile": {"bottom": 340, "outlinePx": 5, "pill": True, "fontSize": 50},
        "brand": {
            "name": "کاریاب ماشین", "site": "KARYABMASHIN.IR", "logoSrc": logo,
            "requireLogo": True, "endCard": True, "endCardRequired": True,
            "persistentBug": False, "prominence": "strong",
        },
        "assets": assets,
        "camp": {
            "enabled": True, "package": "KBM-VIDEO-FACTORY-CAMP-13.2",
            "version": "13.2.0-creative-repair-01", "authority": AUTHORITY,
            "vertical": "machine-sale", "topic": "خرید و فروش ماشین‌آلات سنگین",
            "durationSeconds": 20, "maxRepairPasses": 0,
        },
        "editorial": {
            "repairPass": 2,
            "repairFlags": {"hook": True, "pacing": True, "caption": True, "cta": True},
            "repairActions": [
                "strengthen actionable CTA", "vary caption layout", "enlarge website proof",
                "add directional motion and entry transitions",
            ],
            "repairAuthority": AUTHORITY,
            "preserveMixedAudio": True,
            "maxUnchangedSeconds": 1.85,
            "legacyCornerBadgeMasked": True,
            "brandLayerPolicy": "single-active-lockup",
            "shotRoleContract": {"hero": 1, "closeup": 1, "detail": 1, "operation": 2, "context": 1, "website": 1, "cta": 1},
        },
        "muted": True,
        "volume": 0,
    }
    props_path = work / "render-props.json"
    write_json(props_path, props)

    output.unlink(missing_ok=True)
    renderer, render_error = render_with_fallback(
        root=root, source=source_video, props_path=props_path,
        template="KBM-V03-MACHINE-REVIEW", output=output,
        duration_frames=600, allow_remotion=True, require_remotion=True,
    )
    renderer.update({"renderError": render_error, "repairPass": 2, "outputRole": "camp-creative-repair-final"})
    if not output.is_file():
        raise SystemExit("CREATIVE_REPAIR_RENDER_OUTPUT_MISSING")

    master = master_for_reels(output, target_lufs=-14.0, target_lra=7.0, true_peak=-1.5)
    critic = critique_final(output, work)
    brief = read_json(required["brief"], {})
    voice = read_json(required["voice"], {})
    voice.update({
        "engine": "immutable-final-mix-reuse", "provider": "artifact-reuse",
        "sourceAudioMuted": True, "narrationTrackCount": 1,
        "audioSourceVideoSha256": source_sha,
    })
    rights = _rights_evidence(props, asset_report)
    visual = _visual_evidence(props, critic, asset_report, True)
    report = release_gate(
        video=output, brief=brief, renderer=renderer, voice=voice,
        critic=critic, rights=rights, visual=visual,
    )
    output_sha = sha256(output)
    evidence = {
        "authority": AUTHORITY,
        "sourceArtifactId": EXPECTED_ARTIFACT_ID,
        "sourceArtifactDigest": EXPECTED_ARTIFACT_DIGEST,
        "sourceVideoSha256": source_sha,
        "outputVideoSha256": output_sha,
        "videoChanged": output_sha != source_sha,
        "ttsExecuted": False,
        "mediaResearchExecuted": False,
        "mediaGenerationExecuted": False,
        "preservedFinalMix": True,
        "renderer": renderer,
        "audioMaster": master,
        "critic": critic,
        "rights": rights,
        "visual": visual,
        "gatePass": report.get("gatePass"),
        "releaseReady": report.get("releaseReady"),
        "blockers": report.get("blockers"),
    }
    write_json(work / "camp-creative-repair-evidence.json", evidence)
    write_json(work / "camp-release-report.json", report)
    write_json(work / "camp-critic.json", critic)
    write_json(work / "camp-rights-evidence.json", rights)
    write_json(work / "camp-visual-evidence.json", visual)
    write_json(work / "camp-renderer.json", renderer)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if report.get("gatePass") is True else 73


if __name__ == "__main__":
    raise SystemExit(main())
