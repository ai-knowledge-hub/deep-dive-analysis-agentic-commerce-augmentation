from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional

from domain.protocol.types import (
    ProtocolCandidate,
    ProtocolReadinessIssue,
    StructuredQuery,
)
import infrastructure.db.catalog.clients as clients_repo
from infrastructure.protocol.acp_live import discover_live_acp_feed_candidates
from shared.config.env import settings

CURRENT_ACP_VERSION = "2026-04-17"
SUPPORTED_ACP_VERSIONS = {"2026-01-30", CURRENT_ACP_VERSION}


def _is_demo_mode() -> bool:
    mode = (os.getenv("PROTOCOL_MODE") or settings.app_env or "").lower()
    return mode in {"demo", "local"}


def discover_acp_candidates(
    *,
    client_id: str,
    structured_query: StructuredQuery,
    brand_id: Optional[str] = None,
    limit: int = 10,
) -> List[ProtocolCandidate]:
    """Discover ACP candidates from an opted-in feed, then local metadata."""

    live_candidates = discover_live_acp_feed_candidates(
        client_id=client_id,
        structured_query=structured_query,
        brand_id=brand_id,
        limit=limit,
    )
    if live_candidates:
        return live_candidates[:limit]

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

    issues.extend(_validate_acp_version(feed))
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
    if not record.get("item_id"):
        record["item_id"] = record.get("id") or record.get("product_id")
    if not record.get("title"):
        record["title"] = record.get("name")
    if not record.get("brand"):
        record["brand"] = record.get("merchant_name") or record.get("brand_name")
    if not record.get("seller_name"):
        record["seller_name"] = record.get("merchant_name") or record.get("brand")
    if not record.get("url"):
        record["url"] = record.get("offer_url") or record.get("product_url")
    if not record.get("seller_url"):
        record["seller_url"] = record.get("offer_url") or record.get("url")
    if not record.get("api_version"):
        record["api_version"] = record.get("version") or record.get("acp_version")
    if not record.get("image_url") and _is_demo_mode():
        record["image_url"] = (
            record.get("image")
            or record.get("image_src")
            or record.get("offer_url")
            or record.get("url")
        )
    return record


def _validate_acp_version(feed: Dict[str, Any]) -> List[ProtocolReadinessIssue]:
    version = str(feed.get("api_version") or "").strip()
    if not version:
        return [
            ProtocolReadinessIssue(
                field="api_version",
                severity="warning",
                message="ACP API version is not declared.",
                fix=f"Declare API-Version metadata, preferably {CURRENT_ACP_VERSION}.",
            )
        ]
    if version not in SUPPORTED_ACP_VERSIONS:
        return [
            ProtocolReadinessIssue(
                field="api_version",
                severity="warning",
                message=(
                    f"ACP API version {version!r} is not in the supported set "
                    f"{', '.join(sorted(SUPPORTED_ACP_VERSIONS))}."
                ),
                fix=f"Update ACP metadata to {CURRENT_ACP_VERSION} or add compatibility handling.",
            )
        ]
    return []


def _validate_feed_record(feed: Dict[str, Any]) -> List[ProtocolReadinessIssue]:
    issues: List[ProtocolReadinessIssue] = []
    demo_mode = _is_demo_mode()
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
                    severity="warning" if demo_mode else "error",
                    message=(
                        f"Missing required ACP feed field `{field}`."
                        + (" (demo mode warning)." if demo_mode else "")
                    ),
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
    demo_mode = _is_demo_mode()
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
                severity="warning" if demo_mode else "error",
                message=(
                    "Feed update is stale (>120 minutes)."
                    + (" (demo mode warning)." if demo_mode else "")
                ),
                fix="Update feeds at least every 15 minutes; hourly for low-change feeds.",
            )
        )
    elif age_minutes > 15:
        issues.append(
            ProtocolReadinessIssue(
                field="updated_at",
                severity="warning",
                message="Feed update is older than 15 minutes.",
                fix="Update feeds every 15 minutes for high-change feeds.",
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
    for key in ("create_session", "retrieve_session", "update_session", "complete_session"):
        if not endpoints.get(key):
            issues.append(
                ProtocolReadinessIssue(
                    field=f"checkout_endpoints.{key}",
                    severity="error",
                    message=f"Missing ACP checkout endpoint `{key}`.",
                    fix="Expose required checkout endpoints for ACP.",
                )
            )
    capabilities = checkout.get("capabilities") if isinstance(checkout, dict) else None
    if not isinstance(capabilities, dict):
        issues.append(
            ProtocolReadinessIssue(
                field="checkout_capabilities",
                severity="error",
                message="ACP checkout capabilities negotiation metadata is missing.",
                fix=(
                    "Declare seller response capabilities, including interventions "
                    "and payment handlers."
                ),
            )
        )
    else:
        interventions = capabilities.get("interventions")
        if not isinstance(interventions, dict):
            issues.append(
                ProtocolReadinessIssue(
                    field="checkout_capabilities.interventions",
                    severity="warning",
                    message="ACP interventions capability is not declared.",
                    fix="Declare supported/required intervention behavior for checkout sessions.",
                )
            )
        payment = capabilities.get("payment")
        handlers = payment.get("handlers") if isinstance(payment, dict) else None
        if not isinstance(handlers, list) or not handlers:
            issues.append(
                ProtocolReadinessIssue(
                    field="checkout_capabilities.payment.handlers",
                    severity="error",
                    message="ACP payment handler negotiation metadata is missing.",
                    fix="Declare capabilities.payment.handlers for seller checkout responses.",
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
    delegate_payment = (
        profile.get("delegate_payment") if isinstance(profile, dict) else None
    )
    if not isinstance(payment, dict):
        return [
            ProtocolReadinessIssue(
                field="delegated_payment",
                severity="error",
                message="Delegated payment profile missing for checkout-eligible products.",
                fix="Define delegated payment constraints in brand ACP profile.",
            )
        ]
    delegated_enabled = bool(payment.get("delegated") or delegate_payment)
    if not delegated_enabled:
        return [
            ProtocolReadinessIssue(
                field="delegated_payment",
                severity="error",
                message="Delegated payment not enabled.",
                fix="Enable delegated payment to accept agent checkout.",
            )
        ]
    issues: List[ProtocolReadinessIssue] = []
    delegate_endpoint = (
        delegate_payment.get("endpoint")
        if isinstance(delegate_payment, dict)
        else payment.get("delegate_payment_endpoint")
    )
    if delegate_endpoint and not str(delegate_endpoint).startswith("https://"):
        issues.append(
            ProtocolReadinessIssue(
                field="delegate_payment.endpoint",
                severity="error",
                message="ACP Delegate Payment endpoint must use HTTPS.",
                fix="Expose delegate payment tokenization over HTTPS.",
            )
        )
    constraints = (
        payment.get("token_constraints")
        if isinstance(payment.get("token_constraints"), dict)
        else {}
    )
    allowance = (
        delegate_payment.get("allowance")
        if isinstance(delegate_payment, dict)
        and isinstance(delegate_payment.get("allowance"), dict)
        else {}
    )
    if not constraints.get("expires_in_minutes") and not allowance.get("expires_at"):
        issues.append(
            ProtocolReadinessIssue(
                field="token_constraints.expires_in_minutes",
                severity="warning",
                message="Delegated payment token expiry not specified.",
                fix="Set expires_in_minutes or allowance.expires_at for delegated payment tokens.",
            )
        )
    if not constraints.get("max_amount") and not allowance.get("max_amount"):
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
