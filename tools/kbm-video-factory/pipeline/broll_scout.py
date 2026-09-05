#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from typing import Any

from rights_gate import filter_candidates

KEYWORDS = {
    "بیل": "excavator", "مکانیکی": "excavator", "لودر": "wheel loader", "جرثقیل": "mobile crane",
    "دامپتراک": "dump truck", "کامیون": "heavy truck", "ماشین": "heavy machinery", "ماشین‌آلات": "heavy machinery",
    "هیدرولیک": "hydraulic excavator", "جک": "hydraulic cylinder", "کابین": "excavator operator cabin",
    "اپراتور": "heavy equipment operator", "معدن": "open pit mining machinery", "راهسازی": "road construction machinery",
    "ساختمان": "construction site heavy equipment", "اجاره": "heavy equipment rental inspection",
    "تعمیر": "heavy equipment maintenance", "قطعه": "heavy machinery spare parts", "بازرسی": "heavy equipment inspection",
    "خرید": "heavy machinery marketplace", "فروش": "heavy machinery for sale", "معامله": "heavy equipment marketplace",
}

SHOT_ROLE_HINTS = {
    "closeup": ("close up", "close-up", "detail", "hydraulic", "cylinder", "track", "tire", "engine"),
    "detail": ("component", "cabin", "control", "bucket", "boom", "undercarriage", "inspection"),
    "operation": ("working", "loading", "digging", "lifting", "operator", "construction"),
    "context": ("site", "mine", "road", "yard", "fleet", "marketplace"),
}

GENERIC_QUERY_TERMS = {
    "heavy", "machinery", "equipment", "industrial", "cinematic", "commercial", "vertical",
    "video", "photo", "image", "real", "professional", "construction",
}


def _english_query(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    if re.search(r"[a-z]", normalized):
        cleaned = re.sub(r"[^a-z0-9\- ]+", " ", normalized)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            return cleaned[:120]
    terms: list[str] = []
    for fa, en in KEYWORDS.items():
        if fa in normalized and en not in terms:
            terms.append(en)
    return " ".join(terms[:5]) if terms else "heavy machinery industrial construction"


def _query_terms(query: str) -> list[str]:
    return [
        part for part in re.findall(r"[a-z0-9]{3,}", query.lower())
        if part not in GENERIC_QUERY_TERMS
    ]


def _metadata_text(item: dict[str, Any]) -> str:
    # Do not include the search query itself. Hotfix04 accidentally wrote `query`
    # onto each candidate before scoring and then read that same field back here,
    # making unrelated results look perfectly relevant.
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "description", "alt", "tags", "sourceUrl", "creator")
    ).lower()


def _semantic_relevance(item: dict[str, Any], query: str) -> float:
    metadata = _metadata_text(item)
    terms = _query_terms(query)
    if not terms:
        return 0.55
    if not metadata.strip():
        return 0.42
    hits = sum(1 for term in terms if term in metadata)
    if hits == 0:
        return 0.18
    coverage = hits / max(1, len(terms))
    # One strong domain hit is useful but not equivalent to a perfect semantic match.
    return round(min(1.0, 0.32 + (coverage * 0.68)), 4)


def _shot_role(query: str) -> str:
    lowered = query.lower()
    for role, hints in SHOT_ROLE_HINTS.items():
        if any(hint in lowered for hint in hints):
            return role
    return "hero"


def _score(item: dict[str, Any], expected_type: str, query: str) -> float:
    w, h = float(item.get("width") or 0), float(item.get("height") or 0)
    portrait = 1.0 if h > w and h >= 1080 else 0.72 if h > w and h >= 720 else 0.42 if h >= 720 else 0.0
    resolution = min(1.0, (w * h) / (1080 * 1920)) if w and h else 0.0
    duration = float(item.get("duration") or 0)
    duration_fit = 1.0 if expected_type == "image" else (1.0 if 2 <= duration <= 18 else 0.75 if 18 < duration <= 35 else 0.35 if duration else 0.2)
    type_fit = 1.0 if str(item.get("mediaType")) == expected_type else 0.0
    provider_confidence = {"cupai-generated": 0.95, "pexels": 0.90, "pixabay": 0.86, "iran-gateway": 0.82}.get(str(item.get("provider")), 0.70)
    semantic = _semantic_relevance(item, query)
    cinematic = min(1.0, (portrait * 0.45) + (resolution * 0.35) + (duration_fit * 0.20))
    score = (
        semantic * 0.38
        + cinematic * 0.18
        + resolution * 0.12
        + portrait * 0.09
        + duration_fit * 0.05
        + provider_confidence * 0.08
        + type_fit * 0.10
    )
    return round(max(0.0, min(1.0, score)), 4)


def _machine_sale_query(media_type: str, role: str, index: int = 0) -> str:
    presets = {
        "hero": "excavator for sale dealer yard clean hero shot",
        "operation": "excavator digging loading working construction site action",
        "context": "heavy equipment dealer yard excavator fleet marketplace",
        "closeup": "excavator hydraulic cylinder track close up inspection",
        "detail": "excavator cabin controls engine bucket detail inspection",
    }
    base = presets.get(role, presets["hero"])
    if media_type == "image" and role == "operation":
        base = "excavator working construction site action side view"
    if index:
        base += f" angle {index + 1}"
    return base


def _requests(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    diversity_enabled = os.environ.get("KBM_CAMP_MEDIA_DIVERSITY", "0").strip().lower() in {"1", "true", "yes", "on"}
    profile = os.environ.get("KBM_CAMP_MEDIA_PROFILE", "").strip().lower()

    for index, scene in enumerate(storyboard.get("scenes", [])):
        if not isinstance(scene, dict):
            continue
        kind = str(scene.get("kind") or "video")
        if kind not in {"broll", "image", "poster", "infographic"}:
            continue
        media_type = "image" if kind in {"image", "poster", "infographic"} else "video"
        copy = str(scene.get("copy") or "").strip()
        search_query = str(scene.get("searchQuery") or "").strip()
        query = _english_query(search_query or copy or "heavy machinery")
        role = _shot_role(query)
        # The generic campaign writer produced `cinematic heavy machinery industrial construction`
        # for both Hotfix04 storyboard scenes. Under CAMP machine-sale mode replace that vague
        # query with an explicit sales/operation visual intent before provider search.
        if diversity_enabled and (profile == "machine-sale" or "خرید" in copy or "فروش" in copy):
            useful = _query_terms(query)
            if len(useful) <= 1:
                role = "operation" if media_type == "video" else "hero"
                query = _machine_sale_query(media_type, role, index)
        requests.append({
            "id": f"media-{scene['id']}",
            "sceneId": scene["id"],
            "mediaType": media_type,
            "queryFa": (copy or search_query or "ماشین آلات سنگین")[:140],
            "query": query,
            "shotRole": role,
            "required": False,
        })

    if diversity_enabled:
        existing_ids = {str(item.get("id") or "") for item in requests}
        supplements = [
            ("operation-a", "video", "operation", "نمای واقعی کار و حرکت بیل مکانیکی", "excavator digging loading working construction site action"),
            ("context-yard", "video", "context", "نمای محوطه فروش و ناوگان ماشین آلات", "heavy equipment dealer yard excavator fleet marketplace"),
            ("inspection", "image", "closeup", "بازرسی جک هیدرولیک و زیربندی", "excavator hydraulic cylinder track close up inspection"),
            ("cabin-detail", "image", "detail", "جزئیات کابین و کنترل ماشین", "excavator cabin controls interior detail inspection"),
            ("operation-b", "video", "operation", "بیل مکانیکی در حال بارگیری یا حفاری", "excavator loading truck digging working action"),
            ("hero-sale", "image", "hero", "نمای کامل دستگاه آماده فروش", "excavator for sale dealer yard clean hero shot"),
        ]
        for suffix, media_type, role, query_fa, query in supplements:
            if len(requests) >= 7:
                break
            request_id = f"media-camp-diversity-{suffix}"
            if request_id in existing_ids:
                continue
            requests.append({
                "id": request_id,
                "sceneId": f"camp-diversity-{suffix}",
                "mediaType": media_type,
                "queryFa": query_fa,
                "query": query,
                "shotRole": role,
                "required": False,
            })
            existing_ids.add(request_id)
    return requests


def _collect(provider: Any, name: str, req: dict[str, Any], query: str, candidates: list[dict[str, Any]], states: list[dict[str, Any]]) -> None:
    results = provider.search_images(query, per_page=8) if req["mediaType"] == "image" else provider.search_videos(query, per_page=10)
    kept = 0
    low_semantic = 0
    for raw in results:
        item = dict(raw)
        semantic = round(_semantic_relevance(item, query), 4)
        item.update({
            "requestId": req["id"],
            "sceneId": req["sceneId"],
            "query": query,
            "shotRole": req.get("shotRole") or "hero",
            "semanticRelevance": semantic,
        })
        item["score"] = _score(item, str(req["mediaType"]), query)
        # If provider metadata/URL clearly contradicts the query, do not let high resolution
        # or portrait orientation push it to the front of the routed asset list.
        if semantic < 0.28:
            low_semantic += 1
            continue
        candidates.append(item)
        kept += 1
    states.append({
        "provider": name,
        "state": "PASS",
        "sceneId": req["sceneId"],
        "count": len(results),
        "kept": kept,
        "semanticRejected": low_semantic,
    })


def _failure(name: str, scene_id: str, exc: Exception) -> dict[str, Any]:
    if name == "cupai-generated":
        try:
            from avalai_creative_client import classify_cupai_error
            return {"provider": name, "state": "FALLBACK", "sceneId": scene_id, **classify_cupai_error(exc)}
        except Exception:
            pass
    text = str(exc)
    lowered = text.lower()
    code = "PROVIDER_REQUEST_FAILED"
    retryable = False
    if "429" in lowered or "rate" in lowered and "limit" in lowered:
        code, retryable = "PROVIDER_RATE_LIMITED", True
    elif "timeout" in lowered or "timed out" in lowered or "network" in lowered:
        code, retryable = "PROVIDER_NETWORK_RETRYABLE", True
    elif "401" in lowered or "403" in lowered or "auth" in lowered:
        code = "PROVIDER_AUTH_FAILED"
    return {"provider": name, "state": "FALLBACK", "sceneId": scene_id, "code": code, "retryable": retryable, "quotaBlocked": False, "reason": text[-260:]}


def _provider_health(states: list[dict[str, Any]]) -> dict[str, Any]:
    names = sorted({str(item.get("provider") or "unknown") for item in states})
    health: dict[str, Any] = {}
    for name in names:
        rows = [item for item in states if str(item.get("provider") or "") == name]
        health[name] = {
            "pass": sum(1 for item in rows if item.get("state") == "PASS"),
            "fallback": sum(1 for item in rows if item.get("state") == "FALLBACK"),
            "skipped": sum(1 for item in rows if item.get("state") == "SKIPPED"),
            "quotaBlocked": any(bool(item.get("quotaBlocked")) for item in rows),
            "codes": sorted({str(item.get("code")) for item in rows if item.get("code")}),
        }
    return health


def _diversity_summary(approved: list[dict[str, Any]]) -> dict[str, Any]:
    roles: dict[str, int] = {}
    providers: dict[str, int] = {}
    identities: set[str] = set()
    for item in approved:
        role = str(item.get("shotRole") or "hero")
        provider = str(item.get("provider") or "unknown")
        identity = f"{provider}|{item.get('providerId') or item.get('sourceUrl') or ''}"
        roles[role] = roles.get(role, 0) + 1
        providers[provider] = providers.get(provider, 0) + 1
        identities.add(identity)
    return {
        "shotRoleCounts": roles,
        "providerCounts": providers,
        "uniqueCandidateCount": len(identities),
        "hasHero": roles.get("hero", 0) > 0,
        "hasOperation": roles.get("operation", 0) > 0,
        "hasContext": roles.get("context", 0) > 0,
        "hasCloseupOrDetail": roles.get("closeup", 0) + roles.get("detail", 0) > 0,
        "semanticFloorPass": all(float(item.get("semanticRelevance") or 0.0) >= 0.28 for item in approved) if approved else False,
    }


def scout(storyboard: dict[str, Any], enabled: bool = False) -> dict[str, Any]:
    requests = _requests(storyboard)
    candidates: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    if not enabled:
        return {"enabled": False, "requests": requests, "candidates": [], "rejected": [], "states": [{"provider": "all", "state": "SKIPPED", "reason": "network media research disabled"}], "providerHealth": {}, "diversity": {}}

    from providers import iran_media_provider, pexels_provider, pixabay_provider
    stock_providers = [("pexels", pexels_provider), ("pixabay", pixabay_provider), ("iran-gateway", iran_media_provider)]
    skip_once: set[str] = set()
    for req in requests:
        for name, provider in stock_providers:
            if not provider.configured():
                if name not in skip_once:
                    states.append({"provider": name, "state": "SKIPPED", "reason": "provider credentials not configured"})
                    skip_once.add(name)
                continue
            try:
                query = str(req["queryFa"] if name == "iran-gateway" else req["query"])
                _collect(provider, name, req, query, candidates, states)
            except Exception as exc:
                states.append(_failure(name, str(req["sceneId"]), exc))

    approved, rejected = filter_candidates(candidates)
    approved_request_ids = {str(x.get("requestId") or "") for x in approved}

    cupai_enabled = os.environ.get("KBM_PACKAGE131_CUPAI_MEDIA", "0").strip().lower() in {"1", "true", "yes", "on"}
    generate_always = os.environ.get("KBM_PACKAGE131_CUPAI_GENERATE_ALWAYS", "0").strip().lower() in {"1", "true", "yes", "on"}
    if cupai_enabled:
        try:
            from providers import cupai_generated_provider
            if cupai_generated_provider.configured():
                generated: list[dict[str, Any]] = []
                for req in requests:
                    if not generate_always and str(req["id"]) in approved_request_ids:
                        continue
                    try:
                        _collect(cupai_generated_provider, "cupai-generated", req, str(req["query"]), generated, states)
                    except Exception as exc:
                        states.append(_failure("cupai-generated", str(req["sceneId"]), exc))
                gen_approved, gen_rejected = filter_candidates(generated)
                approved.extend(gen_approved)
                rejected.extend(gen_rejected)
            else:
                states.append({"provider": "cupai-generated", "state": "SKIPPED", "reason": "direct CupAI generated media not configured"})
        except Exception as exc:
            states.append(_failure("cupai-generated", "provider-init", exc))

    approved.sort(
        key=lambda x: (
            float(x.get("semanticRelevance") or 0.0),
            float(x.get("score") or 0.0),
        ),
        reverse=True,
    )
    configured_names = [name for name, provider in stock_providers if provider.configured()]
    if cupai_enabled:
        configured_names.append("cupai-generated")
    health = _provider_health(states)
    diversity = _diversity_summary(approved)
    return {
        "enabled": True,
        "requests": requests,
        "candidates": approved,
        "rejected": rejected,
        "states": states,
        "providerHealth": health,
        "diversity": diversity,
        "researchSummary": {
            "requests": len(requests),
            "approved": len(approved),
            "rejectedByRights": len(rejected),
            "providersConfigured": configured_names,
            "providersHealthy": [name for name, value in health.items() if value.get("pass", 0) > 0],
            "providersQuotaBlocked": [name for name, value in health.items() if value.get("quotaBlocked")],
            "shotRoleCounts": diversity.get("shotRoleCounts", {}),
            "uniqueCandidateCount": diversity.get("uniqueCandidateCount", 0),
            "semanticFloorPass": diversity.get("semanticFloorPass", False),
        },
    }
