from __future__ import annotations

from typing import Any, Dict, List, Optional

from domain.protocol.types import (
    ProtocolCandidate,
    ProtocolReadinessIssue,
    StructuredQuery,
)
from infrastructure.db import clients as clients_repo


def discover_acp_candidates(
    *,
    client_id: str,
    structured_query: StructuredQuery,
    brand_id: Optional[str] = None,
    limit: int = 10,
) -> List[ProtocolCandidate]:
    """Mock-first ACP discovery.

    Today: use DB products as the “ACP feed”.
    Later: replace with real ACP feed/search endpoint calls.
    """

    products: List[Dict[str, Any]] = []
    if brand_id:
        products = clients_repo.list_products(brand_id=brand_id)
    else:
        # Client-wide search is a reasonable stand-in for “feed search”
        products = clients_repo.search_products_for_client(
            client_id=client_id, query=structured_query.query_text, limit=limit
        )

    candidates: List[ProtocolCandidate] = []
    for product in products[:limit]:
        meta = product.get("metadata") or {}
        acp_meta = meta.get("acp") or {}
        attributes = acp_meta.get("attributes") or meta.get("attributes") or {}
        candidates.append(
            ProtocolCandidate(
                id=product["id"],
                name=product.get("name") or "",
                description=product.get("description") or "",
                protocol="acp",
                offer_url=_pick(acp_meta, meta, "offer_url", "url"),
                merchant_name=_pick(acp_meta, meta, "merchant_name"),
                price=_pick_number(acp_meta, meta, "price"),
                currency=_pick(acp_meta, meta, "currency"),
                availability=_pick(acp_meta, meta, "availability"),
                available_for_sale=_pick_bool(acp_meta, meta, "available_for_sale"),
                inventory_quantity=_pick_int(acp_meta, meta, "inventory_quantity"),
                attributes=attributes if isinstance(attributes, dict) else {},
                raw={"product": product},
            )
        )
    return candidates


def validate_acp_candidate(
    candidate: ProtocolCandidate,
) -> List[ProtocolReadinessIssue]:
    """ACP readiness checks (minimal)."""
    issues: List[ProtocolReadinessIssue] = []

    if not candidate.offer_url:
        issues.append(
            ProtocolReadinessIssue(
                field="offer_url",
                severity="error",
                message="Missing offer_url required for ACP checkout flows.",
                fix="Provide a canonical offer URL for the product.",
            )
        )
    if candidate.price is None:
        issues.append(
            ProtocolReadinessIssue(
                field="price",
                severity="warning",
                message="Missing price; agents cannot enforce budget constraints.",
                fix="Provide price in feed metadata (e.g., metadata.acp.price).",
            )
        )
    if not candidate.availability and candidate.available_for_sale is None:
        issues.append(
            ProtocolReadinessIssue(
                field="availability",
                severity="warning",
                message="Missing availability; agents prefer real-time stock signals.",
                fix="Provide availability or available_for_sale flag in ACP feed.",
            )
        )

    enable_search = _truthy(
        candidate.raw.get("product", {})
        .get("metadata", {})
        .get("acp", {})
        .get("enable_search")
    )
    enable_checkout = _truthy(
        candidate.raw.get("product", {})
        .get("metadata", {})
        .get("acp", {})
        .get("enable_checkout")
    )
    if not enable_search:
        issues.append(
            ProtocolReadinessIssue(
                field="enable_search",
                severity="info",
                message="ACP enable_search flag not set; product may not be discoverable via feed search.",
                fix="Set metadata.acp.enable_search=true for searchable items.",
            )
        )
    if not enable_checkout:
        issues.append(
            ProtocolReadinessIssue(
                field="enable_checkout",
                severity="info",
                message="ACP enable_checkout flag not set; agent checkout may be disabled.",
                fix="Set metadata.acp.enable_checkout=true if checkout is supported.",
            )
        )
    return issues


def _pick(primary: Dict[str, Any], fallback: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in primary and primary.get(key) is not None:
            return primary.get(key)
        if key in fallback and fallback.get(key) is not None:
            return fallback.get(key)
    return None


def _pick_number(
    primary: Dict[str, Any], fallback: Dict[str, Any], key: str
) -> Optional[float]:
    value = _pick(primary, fallback, key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_int(
    primary: Dict[str, Any], fallback: Dict[str, Any], key: str
) -> Optional[int]:
    value = _pick(primary, fallback, key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pick_bool(
    primary: Dict[str, Any], fallback: Dict[str, Any], key: str
) -> Optional[bool]:
    value = _pick(primary, fallback, key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False
