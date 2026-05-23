from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from domain.protocol.scoring import score_structured_match
from domain.protocol.types import (
    ProtocolCandidate,
    ProtocolType,
    StructuredQuery,
)


@dataclass(frozen=True)
class ProtocolDiscoveryResult:
    query: StructuredQuery
    candidates: List[Dict[str, Any]]
    summary: Dict[str, Any]


class ProtocolDiscoveryService:
    """Protocol-layer discovery (Layer 2).

    Mock-first: queries DB-backed product records via adapters that emulate
    ACP/UCP discovery behavior. Later the adapters can call real endpoints.
    """

    def __init__(
        self,
        *,
        discover_acp_fn,
        discover_ucp_fn,
        validate_acp_fn,
        validate_ucp_fn,
    ) -> None:
        self._discover_acp = discover_acp_fn
        self._discover_ucp = discover_ucp_fn
        self._validate_acp = validate_acp_fn
        self._validate_ucp = validate_ucp_fn

    def discover(
        self,
        *,
        client_id: str,
        query: str,
        protocol: Optional[ProtocolType] = None,
        brand_id: Optional[str] = None,
        limit: int = 10,
        inferred_intent: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        structured = build_structured_query(
            query=query, inferred_intent=inferred_intent
        )

        candidates: List[ProtocolCandidate] = []
        if protocol in (None, "acp"):
            candidates.extend(
                self._discover_acp(
                    client_id=client_id,
                    brand_id=brand_id,
                    structured_query=structured,
                    limit=limit,
                )
            )
        if protocol in (None, "ucp"):
            candidates.extend(
                self._discover_ucp(
                    client_id=client_id,
                    brand_id=brand_id,
                    structured_query=structured,
                    limit=limit,
                )
            )

        out: List[Dict[str, Any]] = []
        errors = 0
        warnings = 0
        for candidate in candidates[:limit]:
            discovery_source = _candidate_discovery_source(candidate)
            issues = (
                self._validate_acp(candidate)
                if candidate.protocol == "acp"
                else self._validate_ucp(candidate)
            )
            match = score_structured_match(structured, candidate)
            for issue in issues:
                if issue.severity == "error":
                    errors += 1
                if issue.severity == "warning":
                    warnings += 1
            out.append(
                {
                    "id": candidate.id,
                    "name": candidate.name,
                    "description": candidate.description,
                    "protocol": candidate.protocol,
                    "offer_url": candidate.offer_url,
                    "merchant_name": candidate.merchant_name,
                    "price": candidate.price,
                    "currency": candidate.currency,
                    "availability": candidate.availability,
                    "available_for_sale": candidate.available_for_sale,
                    "inventory_quantity": candidate.inventory_quantity,
                    "attributes": candidate.attributes,
                    "discovery_source": discovery_source,
                    "structured_match": {
                        "score": match.score,
                        "matched": match.matched,
                        "missing": match.missing,
                        "notes": match.notes,
                    },
                    "readiness_issues": [issue.__dict__ for issue in issues],
                }
            )

        # Sort by structured score descending
        out.sort(
            key=lambda item: float(
                item.get("structured_match", {}).get("score") or 0.0
            ),
            reverse=True,
        )

        return {
            "structured_query": structured.__dict__,
            "candidates": out[:limit],
            "summary": {
                "count": len(out[:limit]),
                "errors": errors,
                "warnings": warnings,
                "source_counts": _source_counts(out[:limit]),
            },
        }


def build_structured_query(
    *, query: str, inferred_intent: Optional[Dict[str, Any]] = None
) -> StructuredQuery:
    text = (query or "").strip()
    price_max = _extract_price_max(text)
    required_attributes = _extract_attributes(text)

    # If intent provides explicit constraints, merge them in (best-effort).
    if inferred_intent:
        constraints = (
            inferred_intent.get("constraints")
            or inferred_intent.get("context_signals")
            or []
        )
        if isinstance(constraints, list):
            for c in constraints:
                if isinstance(c, str):
                    required_attributes.extend(_extract_attributes(c))
                    if price_max is None:
                        price_max = _extract_price_max(c)

    # Dedupe attributes
    seen = set()
    attrs: List[str] = []
    for attr in required_attributes:
        k = attr.strip().lower()
        if k and k not in seen:
            seen.add(k)
            attrs.append(attr)

    return StructuredQuery(
        query_text=text, price_max=price_max, required_attributes=attrs
    )


def _extract_price_max(text: str) -> Optional[float]:
    # Common patterns: "under $200", "≤£75", "max 150", "up to 300"
    patterns = [
        r"(?:under|less than|below|up to|max(?:imum)?|<=|≤)\s*[$£€]?\s*(\d+(?:\.\d+)?)",
        r"[$£€]\s*(\d+(?:\.\d+)?)\s*(?:or less|max(?:imum)?|and under)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _extract_attributes(text: str) -> List[str]:
    # Minimal keyword→attribute mapping (expand later with ontology/taxonomy).
    mapping = {
        "anti-glare": "anti_glare",
        "glare": "anti_glare",
        "noise cancelling": "active_noise_cancellation",
        "noise-cancelling": "active_noise_cancellation",
        "anc": "active_noise_cancellation",
        "waterproof": "waterproof",
        "water resistant": "water_resistant",
        "wide": "wide_fit",
        "wide fit": "wide_fit",
        "delivery": "delivery_available",
        "in stock": "in_stock",
    }
    lower = text.lower()
    attrs: List[str] = []
    for token, attr in mapping.items():
        if token in lower:
            attrs.append(attr)
    return attrs


def _candidate_discovery_source(candidate: ProtocolCandidate) -> str:
    raw_source = candidate.raw.get("source") if isinstance(candidate.raw, dict) else None
    if isinstance(raw_source, str) and raw_source.strip():
        return raw_source.strip()
    return f"{candidate.protocol}_local_metadata"


def _source_counts(candidates: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for candidate in candidates:
        source = str(candidate.get("discovery_source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


__all__ = ["ProtocolDiscoveryService", "build_structured_query"]
