from __future__ import annotations

from datetime import datetime, timezone
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
    """ACP readiness checks (feed + checkout + delegated payment readiness)."""
    issues: List[ProtocolReadinessIssue] = []

    product = candidate.raw.get("product") if isinstance(candidate.raw, dict) else {}
    metadata = product.get("metadata") if isinstance(product, dict) else {}
    feed = _normalize_feed_record(metadata or {})

    issues.extend(_validate_feed_record(feed))
    issues.extend(_validate_feed_freshness(feed))
    issues.extend(_validate_brand_checkout_readiness(candidate, feed))
    issues.extend(_validate_brand_payment_readiness(candidate, feed))

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
    readiness_score = _compute_readiness_score(issues)
    issues.append(
        ProtocolReadinessIssue(
            field="acp_readiness_score",
            severity="info",
            message=f"ACP readiness score: {readiness_score}/100.",
        )
    )
    return issues


def _normalize_feed_record(metadata: Dict[str, Any]) -> Dict[str, Any]:
    acp = metadata.get("acp") if isinstance(metadata.get("acp"), dict) else {}
    record = dict(metadata)
    record.update(acp)
    return record


def _validate_feed_record(feed: Dict[str, Any]) -> List[ProtocolReadinessIssue]:
    issues: List[ProtocolReadinessIssue] = []
    required_fields = [
        "item_id",
        "title",
        "description",
        "url",
        "image_url",
        "price",
        "availability",
        "brand",
        "is_eligible_search",
        "is_eligible_checkout",
        "seller_name",
        "seller_url",
    ]
    for field in required_fields:
        if not feed.get(field):
            issues.append(
                ProtocolReadinessIssue(
                    field=field,
                    severity="error",
                    message=f"Missing required ACP feed field `{field}`.",
                    fix=f"Provide `{field}` in ACP feed metadata.",
                )
            )

    if feed.get("is_eligible_checkout") and not feed.get("is_eligible_search"):
        issues.append(
            ProtocolReadinessIssue(
                field="is_eligible_checkout",
                severity="error",
                message="is_eligible_checkout requires is_eligible_search=true.",
                fix="Enable search eligibility before checkout.",
            )
        )

    availability = feed.get("availability")
    if availability and availability not in {
        "in_stock",
        "out_of_stock",
        "pre_order",
        "backorder",
        "unknown",
    }:
        issues.append(
            ProtocolReadinessIssue(
                field="availability",
                severity="warning",
                message=f"Availability value `{availability}` is not a supported enum.",
                fix="Use one of: in_stock, out_of_stock, pre_order, backorder, unknown.",
            )
        )

    price = feed.get("price")
    if isinstance(price, str) and not _price_has_currency(price):
        issues.append(
            ProtocolReadinessIssue(
                field="price",
                severity="warning",
                message="Price should include ISO currency (e.g., `79.99 USD`).",
                fix="Include currency code in price.",
            )
        )
    if price is None:
        issues.append(
            ProtocolReadinessIssue(
                field="price",
                severity="warning",
                message="Missing price; agents cannot enforce budget constraints.",
                fix="Provide price in feed metadata.",
            )
        )
    return issues


def _validate_feed_freshness(feed: Dict[str, Any]) -> List[ProtocolReadinessIssue]:
    issues: List[ProtocolReadinessIssue] = []
    updated_at = (
        feed.get("updated_at")
        or feed.get("last_updated")
        or feed.get("feed_updated_at")
    )
    if not updated_at:
        issues.append(
            ProtocolReadinessIssue(
                field="updated_at",
                severity="warning",
                message="Missing updated_at; freshness cannot be verified.",
                fix="Include updated_at in feed records to track freshness.",
            )
        )
        return issues
    try:
        parsed = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
    except ValueError:
        issues.append(
            ProtocolReadinessIssue(
                field="updated_at",
                severity="warning",
                message="updated_at is not valid ISO 8601.",
                fix="Use ISO 8601 timestamps (e.g., 2026-01-28T12:00:00Z).",
            )
        )
        return issues

    now = datetime.now(timezone.utc)
    age_minutes = (now - parsed.astimezone(timezone.utc)).total_seconds() / 60.0
    if age_minutes > 120:
        issues.append(
            ProtocolReadinessIssue(
                field="updated_at",
                severity="error",
                message="Feed update is stale (>120 minutes).",
                fix="Update feeds at least every 15 minutes; hourly for low-change catalogs.",
            )
        )
    elif age_minutes > 15:
        issues.append(
            ProtocolReadinessIssue(
                field="updated_at",
                severity="warning",
                message="Feed update is older than 15 minutes.",
                fix="Update feeds every 15 minutes for high-change catalogs.",
            )
        )
    return issues


def _validate_brand_checkout_readiness(
    candidate: ProtocolCandidate, feed: Dict[str, Any]
) -> List[ProtocolReadinessIssue]:
    if not feed.get("is_eligible_checkout"):
        return []
    product = candidate.raw.get("product") if isinstance(candidate.raw, dict) else {}
    brand_id = product.get("brand_id") if isinstance(product, dict) else None
    if not brand_id:
        return [
            ProtocolReadinessIssue(
                field="brand_id",
                severity="warning",
                message="Missing brand_id; cannot validate ACP checkout readiness.",
                fix="Associate product with a brand to validate checkout readiness.",
            )
        ]
    brand = clients_repo.get_brand(brand_id=brand_id)
    if not brand:
        return [
            ProtocolReadinessIssue(
                field="brand",
                severity="warning",
                message="Brand not found; cannot validate ACP checkout readiness.",
                fix="Ensure brand exists and is linked to this product.",
            )
        ]
    meta = brand.get("metadata") or {}
    profile = (
        meta.get("acp_profile") if isinstance(meta.get("acp_profile"), dict) else {}
    )
    checkout = profile.get("checkout") if isinstance(profile, dict) else None
    endpoints = checkout.get("endpoints") if isinstance(checkout, dict) else None
    if not isinstance(endpoints, dict):
        return [
            ProtocolReadinessIssue(
                field="checkout_endpoints",
                severity="error",
                message="Missing ACP checkout endpoints for eligible checkout products.",
                fix="Define checkout endpoints (create/update session) in brand ACP profile.",
            )
        ]
    issues: List[ProtocolReadinessIssue] = []
    for key in ("create_session", "update_session"):
        if not endpoints.get(key):
            issues.append(
                ProtocolReadinessIssue(
                    field=f"checkout_endpoints.{key}",
                    severity="error",
                    message=f"Missing ACP checkout endpoint `{key}`.",
                    fix="Expose required checkout endpoints for ACP.",
                )
            )
    webhooks = checkout.get("webhooks") if isinstance(checkout, dict) else None
    if not webhooks:
        issues.append(
            ProtocolReadinessIssue(
                field="checkout_webhooks",
                severity="warning",
                message="Checkout webhooks not declared.",
                fix="Declare checkout webhook endpoints for order lifecycle events.",
            )
        )
    return issues


def _validate_brand_payment_readiness(
    candidate: ProtocolCandidate, feed: Dict[str, Any]
) -> List[ProtocolReadinessIssue]:
    if not feed.get("is_eligible_checkout"):
        return []
    product = candidate.raw.get("product") if isinstance(candidate.raw, dict) else {}
    brand_id = product.get("brand_id") if isinstance(product, dict) else None
    if not brand_id:
        return []
    brand = clients_repo.get_brand(brand_id=brand_id)
    if not brand:
        return []
    meta = brand.get("metadata") or {}
    profile = (
        meta.get("acp_profile") if isinstance(meta.get("acp_profile"), dict) else {}
    )
    payment = profile.get("payment") if isinstance(profile, dict) else None
    if not isinstance(payment, dict):
        return [
            ProtocolReadinessIssue(
                field="delegated_payment",
                severity="error",
                message="Delegated payment profile missing for checkout-eligible products.",
                fix="Define delegated payment constraints in brand ACP profile.",
            )
        ]
    if not payment.get("delegated"):
        return [
            ProtocolReadinessIssue(
                field="delegated_payment",
                severity="error",
                message="Delegated payment not enabled.",
                fix="Enable delegated payment to accept agent checkout.",
            )
        ]
    issues: List[ProtocolReadinessIssue] = []
    constraints = (
        payment.get("token_constraints")
        if isinstance(payment.get("token_constraints"), dict)
        else {}
    )
    if not constraints.get("expires_in_minutes"):
        issues.append(
            ProtocolReadinessIssue(
                field="token_constraints.expires_in_minutes",
                severity="warning",
                message="Delegated payment token expiry not specified.",
                fix="Set token expiry for delegated payment tokens.",
            )
        )
    if not constraints.get("max_amount"):
        issues.append(
            ProtocolReadinessIssue(
                field="token_constraints.max_amount",
                severity="warning",
                message="Delegated payment max_amount not specified.",
                fix="Set max_amount for delegated tokens.",
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


def _price_has_currency(price: str) -> bool:
    parts = price.strip().split()
    if len(parts) < 2:
        return False
    return len(parts[-1]) == 3 and parts[-1].isalpha()


def _compute_readiness_score(issues: List[ProtocolReadinessIssue]) -> int:
    score = 100
    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    if error_count:
        score -= min(60, 10 * error_count)
    if warning_count:
        score -= min(25, 5 * warning_count)
    return max(0, min(100, score))
