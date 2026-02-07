from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from application.services.query_battery_types import GeneratedQuery


@dataclass(frozen=True)
class IntentCapsule:
    domain_vertical: Optional[str]
    product_name: str
    product_description: Optional[str]
    product_features: List[str]
    use_cases: List[str]
    constraints: Dict[str, Any]
    audience_archetypes: List[str]
    intent_labels: List[str]
    memory_snippets: List[str]
    memory_artifact_ids: List[str]


def generate_llm_queries(
    *,
    capsule: IntentCapsule,
    generate_fn: Callable[[str], str],
    limit: int,
    min_per_archetype: int,
    include_protocol: bool,
    query_type_hint: str,
    banned_terms: Optional[List[str]] = None,
    include_description: bool = True,
) -> List[GeneratedQuery]:
    prompt = _build_prompt(
        capsule=capsule,
        limit=limit,
        min_per_archetype=min_per_archetype,
        include_protocol=include_protocol,
        query_type_hint=query_type_hint,
        banned_terms=banned_terms or [],
        include_description=include_description,
    )
    try:
        raw = generate_fn(prompt)
    except Exception:
        return []
    parsed = _parse_response(raw)
    results = [
        GeneratedQuery(
            query_text=item["query_text"],
            query_type=item.get("query_type") or query_type_hint,
            intent_archetype=item.get("intent_archetype"),
            constraints=item.get("constraints"),
            weight=1.0,
        )
        for item in parsed
        if item.get("query_text")
    ]
    if not banned_terms:
        return results
    lowered_banned = {term.lower() for term in banned_terms if term}
    filtered: List[GeneratedQuery] = []
    for item in results:
        query_lower = item.query_text.lower()
        if any(term in query_lower for term in lowered_banned):
            continue
        filtered.append(item)
    return filtered


def _build_prompt(
    *,
    capsule: IntentCapsule,
    limit: int,
    min_per_archetype: int,
    include_protocol: bool,
    query_type_hint: str,
    banned_terms: List[str],
    include_description: bool,
) -> str:
    payload = {
        "task": "generate_query_battery",
        "capsule": {
            "domain_vertical": capsule.domain_vertical,
            "product_name": capsule.product_name,
            "product_description": capsule.product_description
            if include_description
            else None,
            "product_features": capsule.product_features,
            "use_cases": capsule.use_cases,
            "constraints": capsule.constraints,
            "audience_archetypes": capsule.audience_archetypes,
            "intent_labels": capsule.intent_labels,
            "memory_snippets": capsule.memory_snippets,
            "memory_artifact_ids": capsule.memory_artifact_ids,
        },
        "rules": {
            "max_queries": limit,
            "min_per_archetype": min_per_archetype,
            "include_protocol_queries": include_protocol,
            "query_type_hint": query_type_hint,
            "return_format": "json",
            "banned_terms": banned_terms,
        },
    }
    return (
        "You are a marketing intent analyst. Generate search queries that reflect "
        "intent and audience behavior, not branded or product-specific copy. "
        "Do NOT include brand names, product names, internal model names, or direct feature keywords from the product description. "
        "Translate concrete specs into objective, user-facing descriptors (e.g., 'lightweight cushioned running shoes'). "
        "Avoid exact or near-exact matches for banned_terms. "
        "If context is sparse, prefer broader intent-first phrasing instead of inventing details. "
        "Return ONLY JSON with shape: "
        '{"queries":[{"query_text": "...", "query_type": "coverage|market|adversarial|protocol", '
        '"intent_archetype": "...", "constraints": {...}}]}. '
        "Do not include commentary.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_response(raw: str) -> List[Dict[str, Any]]:
    if not raw:
        return []
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    queries = payload.get("queries")
    if not isinstance(queries, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for item in queries:
        if not isinstance(item, dict):
            continue
        query_text = str(item.get("query_text") or "").strip()
        if len(query_text.split()) < 3:
            continue
        cleaned.append(
            {
                "query_text": query_text,
                "query_type": item.get("query_type"),
                "intent_archetype": item.get("intent_archetype"),
                "constraints": item.get("constraints")
                if isinstance(item.get("constraints"), dict)
                else None,
            }
        )
    return cleaned


__all__ = ["IntentCapsule", "generate_llm_queries"]
