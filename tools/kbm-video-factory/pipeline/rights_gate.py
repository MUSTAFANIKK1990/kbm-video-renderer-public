#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from typing import Any

APPROVED_LICENSES = {
    "PEXELS",
    "PIXABAY",
    "CC0",
    "CC-BY",
    "KBM-OWNED",
    "KBM-GENERATED",
    "KBM-APPROVED",
    "FIRST-PARTY-SITE-CAPTURE",
}
APPROVED_PROVIDER_HOSTS = {
    "pexels": {"images.pexels.com", "videos.pexels.com"},
    "pixabay": {"cdn.pixabay.com", "pixabay.com", "www.pixabay.com"},
}
FIRST_PARTY_PROVIDERS = {"karyabmashin-live-site", "kbm-owned", "kbm-generated"}


def evaluate(item: dict[str, Any]) -> dict[str, Any]:
    license_id = str(item.get("license") or "").strip().upper()
    provider = str(item.get("provider") or "").strip().lower()
    download_url = str(item.get("downloadUrl") or "").strip()
    source_url = str(item.get("sourceUrl") or "").strip()
    parsed = urllib.parse.urlparse(download_url) if download_url else None
    host = parsed.hostname if parsed else None
    reasons: list[str] = []

    if license_id not in APPROVED_LICENSES:
        reasons.append("license-not-approved")

    first_party = provider in FIRST_PARTY_PROVIDERS or license_id in {"KBM-OWNED", "KBM-GENERATED", "FIRST-PARTY-SITE-CAPTURE"}
    if first_party:
        if provider == "karyabmashin-live-site" and not source_url.startswith("https://karyabmashin.ir/"):
            reasons.append("first-party-site-source-mismatch")
    else:
        if not download_url.startswith("https://"):
            reasons.append("download-url-not-https")
        if provider in APPROVED_PROVIDER_HOSTS and host not in APPROVED_PROVIDER_HOSTS[provider]:
            reasons.append("provider-host-mismatch")
        if not source_url.startswith("https://"):
            reasons.append("source-url-missing")
        if provider not in APPROVED_PROVIDER_HOSTS and license_id not in {"KBM-APPROVED", "CC0", "CC-BY"}:
            reasons.append("external-provider-requires-explicit-rights")

    return {
        "approved": not reasons,
        "license": license_id or "UNKNOWN",
        "provider": provider or "unknown",
        "sourceUrl": source_url or None,
        "downloadHost": host,
        "firstParty": first_party,
        "reasons": reasons,
    }


def filter_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    approved: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in candidates:
        decision = evaluate(candidate)
        enriched = {**candidate, "rightsDecision": decision}
        (approved if decision["approved"] else rejected).append(enriched)
    return approved, rejected
