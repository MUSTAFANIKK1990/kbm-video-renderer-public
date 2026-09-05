#!/usr/bin/env python3
"""Private GitHub Release runner for the free Android-first KBM video pipeline."""

from __future__ import annotations

import datetime as dt
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PACKAGE = "KBM-VIDEO-FACTORY-RUNNER-ACTIVATION-E2E-13"
VERSION = "0.13.0"
PIPELINE_MODE_ENV = "KBM_PIPELINE_MODE"
GITHUB_API = "https://api.github.com"
GITHUB_UPLOAD_HOST = "uploads.github.com"
GITHUB_API_VERSION = "2026-03-10"
MAX_API_BYTES = 2 * 1024 * 1024
MAX_INPUT_BYTES = 95 * 1024 * 1024
MAX_OUTPUT_BYTES = 500 * 1024 * 1024
MAX_ERROR_CHARS = 800
JOB_ID_RE = re.compile(r"^[a-f0-9-]{36}$")
REPOSITORY_RE = re.compile(r"^([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})$")
EXTENSION_RE = re.compile(r"^(mp4|mov|m4v|mkv|webm)$")
PRESET_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
ALLOWED_TEMPLATES = {
    "KBM-V01-INFOGRAPHIC",
    "KBM-V02-PRESENTER-UI",
    "KBM-V03-MACHINE-REVIEW",
    "KBM-V04-MOTION-POSTER",
    "KBM-V05-TECHNICAL-VFX",
    "KBM-V06-STORY-REVEAL",
}
ALLOWED_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"}
ALLOWED_420_PIXEL_FORMATS = {"yuv420p", "yuvj420p"}


class JobError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def log(event: str, **fields: object) -> None:
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


def _required(name: str, max_length: int = 500) -> str:
    value = os.environ.get(name, "").strip()
    if not value or len(value) > max_length:
        raise JobError(f"Missing or invalid environment value: {name}")
    return value


def _positive_int(name: str) -> int:
    raw = _required(name, 30)
    try:
        value = int(raw)
    except ValueError as exc:
        raise JobError(f"Invalid integer: {name}") from exc
    if value < 1:
        raise JobError(f"Invalid integer: {name}")
    return value


def _redact(value: BaseException | str) -> str:
    text = str(value)
    for secret_name in (
        "GITHUB_TOKEN",
        "KBM_GATEWAY_TOKEN",
        "PEXELS_API_KEY",
        "PIXABAY_API_KEY",
        "KBM_IRAN_MEDIA_SEARCH_TOKEN",
    ):
        secret = os.environ.get(secret_name, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[-MAX_ERROR_CHARS:]


def validated_pipeline_mode(value: str | None = None) -> str:
    mode = (value if value is not None else os.environ.get(PIPELINE_MODE_ENV, "")).strip().lower() or "v2"
    if mode not in {"v2", "v3", "v4"}:
        raise JobError(f"{PIPELINE_MODE_ENV} must be v2, v3 or v4")
    return mode


def repository_parts() -> tuple[str, str]:
    match = REPOSITORY_RE.fullmatch(_required("GITHUB_REPOSITORY", 150))
    if not match:
        raise JobError("GITHUB_REPOSITORY is invalid")
    return match.group(1), match.group(2)


def github_headers(token: str, accept: str = "application/vnd.github+json") -> dict[str, str]:
    return {
        "Accept": accept,
        "Authorization": f"Bearer {token}",
        "User-Agent": "kbm-video-actions-free-13",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def _read_bounded(response: Any, limit: int = MAX_API_BYTES) -> bytes:
    declared = int(response.headers.get("Content-Length", "0") or 0)
    if declared > limit:
        raise JobError("GitHub response is too large")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise JobError("GitHub response is too large")
        chunks.append(chunk)
    return b"".join(chunks)


def api_request(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
    *,
    accept: str = "application/vnd.github+json",
    allow_not_found: bool = False,
) -> tuple[int, bytes, Any]:
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = github_headers(token, accept)
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{GITHUB_API}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, _read_bounded(response), response.headers
    except urllib.error.HTTPError as exc:
        if allow_not_found and exc.code == 404:
            return exc.code, b"", exc.headers
        raise JobError(f"GitHub API {method} {path} failed with HTTP {exc.code}") from exc


def api_json(method: str, path: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    _status, body, _headers = api_request(method, path, token, payload)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise JobError("GitHub API returned invalid JSON") from exc


def list_release_assets(owner: str, repo: str, release_id: int, token: str) -> list[dict[str, Any]]:
    value = api_json("GET", f"/repos/{owner}/{repo}/releases/{release_id}/assets?per_page=100", token)
    if not isinstance(value, list):
        raise JobError("Release asset list is invalid")
    return [item for item in value if isinstance(item, dict)]


def delete_asset(owner: str, repo: str, asset_id: int, token: str) -> None:
    api_request("DELETE", f"/repos/{owner}/{repo}/releases/assets/{asset_id}", token, allow_not_found=True)


def _validate_asset_redirect(location: str) -> str:
    parsed = urllib.parse.urlparse(location)
    allowed = parsed.hostname == "objects.githubusercontent.com" or bool(parsed.hostname and parsed.hostname.endswith(".githubusercontent.com"))
    if parsed.scheme != "https" or not allowed:
        raise JobError("GitHub returned an unsafe asset redirect")
    return location


def download_asset(owner: str, repo: str, asset_id: int, token: str, destination: Path, expected_size: int) -> None:
    request = urllib.request.Request(
        f"{GITHUB_API}/repos/{owner}/{repo}/releases/assets/{asset_id}",
        headers=github_headers(token, "application/octet-stream"),
    )
    opener = urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=120)
    except urllib.error.HTTPError as exc:
        if exc.code != 302:
            raise JobError(f"Input download failed with HTTP {exc.code}") from exc
        location = _validate_asset_redirect(exc.headers.get("Location", ""))
        response = urllib.request.urlopen(urllib.request.Request(location), timeout=120)

    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with response, destination.open("wb") as target:
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_INPUT_BYTES:
                raise JobError("Input asset exceeds the free runner limit")
            target.write(chunk)
    if total != expected_size or total < 1:
        raise JobError("Downloaded input size does not match GitHub metadata")


def _upload_stream(
    owner: str,
    repo: str,
    release_id: int,
    token: str,
    asset_name: str,
    source: bytes | Path,
    content_type: str,
) -> dict[str, Any]:
    size = len(source) if isinstance(source, bytes) else source.stat().st_size
    if size < 1 or size > MAX_OUTPUT_BYTES:
        raise JobError("Upload asset size is invalid")
    query = urllib.parse.urlencode({"name": asset_name})
    path = f"/repos/{owner}/{repo}/releases/{release_id}/assets?{query}"
    connection = http.client.HTTPSConnection(GITHUB_UPLOAD_HOST, timeout=300)
    connection.putrequest("POST", path)
    for name, value in github_headers(token).items():
        connection.putheader(name, value)
    connection.putheader("Content-Type", content_type)
    connection.putheader("Content-Length", str(size))
    connection.endheaders()
    if isinstance(source, bytes):
        connection.send(source)
    else:
        with source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                connection.send(chunk)
    response = connection.getresponse()
    body = _read_bounded(response)
    connection.close()
    if response.status != 201:
        raise JobError(f"Release asset upload failed with HTTP {response.status}")
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise JobError("Release upload returned invalid JSON") from exc
    if not isinstance(value, dict) or value.get("name") != asset_name or int(value.get("size", -1)) != size:
        raise JobError("Release upload verification failed")
    return value


def replace_asset(
    owner: str,
    repo: str,
    release_id: int,
    token: str,
    asset_name: str,
    source: bytes | Path,
    content_type: str,
) -> dict[str, Any]:
    for asset in list_release_assets(owner, repo, release_id, token):
        if asset.get("name") == asset_name and isinstance(asset.get("id"), int):
            delete_asset(owner, repo, int(asset["id"]), token)
    return _upload_stream(owner, repo, release_id, token, asset_name, source, content_type)


def validated_job() -> dict[str, Any]:
    job_id = _required("JOB_ID", 36)
    extension = _required("INPUT_EXTENSION", 10).lower()
    preset = _required("CREATIVE_PRESET", 100)
    template = _required("KBM_TEMPLATE", 80)
    voice = _required("KBM_VOICE", 30)
    release_id = _positive_int("RELEASE_ID")
    input_asset_id = _positive_int("INPUT_ASSET_ID")
    max_seconds = _positive_int("MAX_SECONDS")
    pipeline_mode = validated_pipeline_mode()
    if not JOB_ID_RE.fullmatch(job_id):
        raise JobError("JOB_ID is invalid")
    if not EXTENSION_RE.fullmatch(extension):
        raise JobError("INPUT_EXTENSION is invalid")
    if not PRESET_RE.fullmatch(preset):
        raise JobError("CREATIVE_PRESET is invalid")
    if template not in ALLOWED_TEMPLATES:
        raise JobError("KBM_TEMPLATE is invalid")
    if voice not in ALLOWED_VOICES:
        raise JobError("KBM_VOICE is invalid")
    if not 5 <= max_seconds <= 90:
        raise JobError("MAX_SECONDS is invalid")
    gateway_url = _required("KBM_GATEWAY_URL", 500)
    if not gateway_url.startswith("https://"):
        raise JobError("KBM_GATEWAY_URL must use HTTPS")
    _required("KBM_GATEWAY_TOKEN", 5000)
    return {
        "jobId": job_id,
        "extension": extension,
        "preset": preset,
        "template": template,
        "voice": voice,
        "releaseId": release_id,
        "inputAssetId": input_asset_id,
        "maxSeconds": max_seconds,
        "pipelineMode": pipeline_mode,
    }


def build_command(root: Path, job: dict[str, Any], input_path: Path, output_path: Path) -> list[str]:
    mode = validated_pipeline_mode(str(job.get("pipelineMode") or "v2"))
    filenames = {
        "v2": "orchestrator_v2.py",
        "v3": "orchestrator_v3.py",
        "v4": "orchestrator_v4.py",
    }
    filename = filenames[mode]
    pipeline = (root / "pipeline" / filename).resolve()
    if not pipeline.is_file():
        raise JobError(f"Selected pipeline authority is missing: {filename}")
    return [
        sys.executable,
        str(pipeline),
        "--input", str(input_path),
        "--creative-preset", str(job["preset"]),
        "--template", str(job["template"]),
        "--avalai-voice", str(job["voice"]),
        "--max-seconds", str(job["maxSeconds"]),
        "--job", str(job["jobId"]),
        "--output", str(output_path),
    ]


def _fps(value: str) -> float:
    try:
        left, right = value.split("/", 1)
        return float(left) / max(1.0, float(right))
    except Exception:
        return 0.0


def validate_final_output(path: Path, max_seconds: float) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size < 1024:
        raise JobError("Pipeline did not create a valid MP4")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise JobError("ffprobe is unavailable for final QC")
    raw = subprocess.check_output(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        text=True,
        timeout=30,
    )
    data = json.loads(raw)
    streams = data.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if not isinstance(video, dict):
        raise JobError("Final QC: missing video stream")
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    fps = _fps(str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"))
    pixel_format = str(video.get("pix_fmt") or "")
    failures: list[str] = []
    if str(video.get("codec_name")) != "h264":
        failures.append("video codec")
    if pixel_format not in ALLOWED_420_PIXEL_FORMATS:
        failures.append("pixel format")
    if int(video.get("width") or 0) != 1080 or int(video.get("height") or 0) != 1920:
        failures.append("geometry")
    if not 29.5 <= fps <= 30.5:
        failures.append("fps")
    if not isinstance(audio, dict) or str(audio.get("codec_name")) != "aac":
        failures.append("audio codec")
    if duration <= 0 or duration > float(max_seconds) + 0.25:
        failures.append("duration")
    if failures:
        raise JobError("Final QC failed: " + ", ".join(failures))
    return {
        "pass": True,
        "durationSeconds": round(duration, 3),
        "width": 1080,
        "height": 1920,
        "fps": round(fps, 3),
        "videoCodec": "h264",
        "pixelFormat": pixel_format,
        "audioCodec": "aac",
        "bytes": path.stat().st_size,
    }


def validate_v3_editorial(root: Path, job_id: str, minimum_score: float = 85.0) -> dict[str, Any]:
    path = root / "work" / job_id / "pro-edit-desk-report.json"
    if not path.is_file():
        raise JobError("V3 editorial report is missing")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JobError("V3 editorial report is invalid") from exc
    editorial = report.get("editorial")
    if (
        report.get("package") != "KBM-VIDEO-FACTORY-PRO-EDIT-DESK-REFERENCE-DIRECTOR-11"
        or report.get("rendered") is not True
        or not isinstance(editorial, dict)
    ):
        raise JobError("V3 editorial report contract failed")
    score = float(editorial.get("score") or 0.0)
    passed = bool(editorial.get("pass")) and score >= minimum_score
    if not passed:
        raise JobError(f"V3 editorial QC failed: score={score:.1f}")
    return {"pass": True, "score": round(score, 1), "minimumScore": minimum_score, "report": str(path)}


def validate_v4_editorial(root: Path, job_id: str) -> dict[str, Any]:
    path = root / "work" / job_id / "package13-report.json"
    if not path.is_file():
        raise JobError("V4 Package 13 report is missing")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JobError("V4 Package 13 report is invalid") from exc
    editorial = report.get("editorial")
    if (
        report.get("package") != "KBM-VIDEO-FACTORY-FULL-CINEMATIC-EDITORIAL-13"
        or report.get("version") != "0.13.0"
        or report.get("pipelineMode") != "v4"
        or report.get("rendered") is not True
        or not isinstance(editorial, dict)
    ):
        raise JobError("V4 Package 13 report contract failed")
    score = float(editorial.get("score") or 0.0)
    return {
        "pass": True,
        "score": round(score, 1),
        "brandReady": bool(report.get("brandReady")),
        "rights": report.get("rights") if isinstance(report.get("rights"), dict) else {},
        "report": str(path),
    }


def _input_asset(assets: list[dict[str, Any]], job: dict[str, Any]) -> dict[str, Any]:
    expected_name = f"input-{job['jobId']}.{job['extension']}"
    for asset in assets:
        if asset.get("id") == job["inputAssetId"] and asset.get("name") == expected_name and asset.get("state") == "uploaded":
            size = int(asset.get("size", 0))
            if 1 <= size <= MAX_INPUT_BYTES:
                return asset
    raise JobError("Input asset metadata does not match the job")


def run_render() -> int:
    token = _required("GITHUB_TOKEN", 5000)
    owner, repo = repository_parts()
    job = validated_job()
    root = Path(__file__).resolve().parents[1]
    assets = list_release_assets(owner, repo, job["releaseId"], token)
    input_asset = _input_asset(assets, job)
    job_dir = Path(tempfile.mkdtemp(prefix=f"kbm-{job['jobId']}-"))
    input_path = job_dir / f"input.{job['extension']}"
    output_path = job_dir / "final.mp4"
    log_path = job_dir / "pipeline.log"
    final_name = f"final-{job['jobId']}.mp4"
    failure_name = f"failure-{job['jobId']}.json"
    try:
        log("pipeline_selected", jobId=job["jobId"], pipeline=job["pipelineMode"], package=PACKAGE, version=VERSION)
        log("job_downloading", jobId=job["jobId"])
        download_asset(owner, repo, job["inputAssetId"], token, input_path, int(input_asset["size"]))
        command = build_command(root, job, input_path, output_path)
        log("render_started", jobId=job["jobId"], pipeline=job["pipelineMode"])
        with log_path.open("w", encoding="utf-8") as output:
            result = subprocess.run(
                command,
                cwd=root,
                env=os.environ.copy(),
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                timeout=3200,
                check=False,
            )
        if result.returncode != 0:
            raise JobError(f"Pipeline exited with code {result.returncode}")
        qc = validate_final_output(output_path, float(job["maxSeconds"]))
        log(
            "technical_qc_pass",
            jobId=job["jobId"],
            pipeline=job["pipelineMode"],
            durationSeconds=qc["durationSeconds"],
            pixelFormat=qc["pixelFormat"],
            bytes=qc["bytes"],
        )
        if job["pipelineMode"] == "v3":
            editorial = validate_v3_editorial(root, job["jobId"])
            log("editorial_qc_pass", jobId=job["jobId"], pipeline="v3", score=editorial["score"])
        elif job["pipelineMode"] == "v4":
            editorial = validate_v4_editorial(root, job["jobId"])
            log(
                "package13_contract_pass",
                jobId=job["jobId"],
                pipeline="v4",
                score=editorial["score"],
                brandReady=editorial["brandReady"],
            )
        replace_asset(owner, repo, job["releaseId"], token, final_name, output_path, "video/mp4")
        delete_asset(owner, repo, job["inputAssetId"], token)
        for asset in list_release_assets(owner, repo, job["releaseId"], token):
            if asset.get("name") == failure_name and isinstance(asset.get("id"), int):
                delete_asset(owner, repo, int(asset["id"]), token)
        log("release_uploaded", jobId=job["jobId"], pipeline=job["pipelineMode"], bytes=output_path.stat().st_size)
        log("job_ready", jobId=job["jobId"], bytes=output_path.stat().st_size)
        return 0
    except Exception as exc:
        message = _redact(exc)
        payload = json.dumps(
            {
                "ok": False,
                "state": "failed",
                "code": "RENDER_FAILED",
                "pipelineMode": job.get("pipelineMode"),
                "package": PACKAGE,
                "version": VERSION,
                "message": message,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        try:
            replace_asset(owner, repo, job["releaseId"], token, failure_name, payload, "application/json")
        except Exception as report_error:
            log("failure_report_error", jobId=job["jobId"], message=_redact(report_error))
        log("job_failed", jobId=job["jobId"], pipeline=job.get("pipelineMode"), message=message)
        return 1


def _parse_github_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_expired_release(release: dict[str, Any], cutoff: dt.datetime) -> bool:
    created = _parse_github_time(release.get("created_at"))
    tag = release.get("tag_name")
    return bool(
        release.get("draft") is True
        and isinstance(tag, str)
        and tag.startswith("kbm-job-")
        and created
        and created < cutoff
    )


def run_cleanup() -> int:
    token = _required("GITHUB_TOKEN", 5000)
    owner, repo = repository_parts()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=48)
    removed = 0
    for page in range(1, 6):
        releases = api_json("GET", f"/repos/{owner}/{repo}/releases?per_page=100&page={page}", token)
        if not isinstance(releases, list):
            raise JobError("Release list is invalid")
        if not releases:
            break
        for release in releases:
            if not isinstance(release, dict) or not is_expired_release(release, cutoff):
                continue
            release_id = release.get("id")
            tag = release.get("tag_name")
            if not isinstance(release_id, int) or not isinstance(tag, str):
                continue
            api_request("DELETE", f"/repos/{owner}/{repo}/releases/{release_id}", token, allow_not_found=True)
            api_request(
                "DELETE",
                f"/repos/{owner}/{repo}/git/refs/tags/{urllib.parse.quote(tag, safe='')}",
                token,
                allow_not_found=True,
            )
            removed += 1
    log("cleanup_complete", removed=removed)
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if mode == "render":
            return run_render()
        if mode == "cleanup":
            return run_cleanup()
        raise JobError("Usage: release_runner.py render|cleanup")
    except Exception as exc:
        log("runner_error", message=_redact(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
