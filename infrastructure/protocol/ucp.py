from __future__ import annotations

from typing import Any, Dict, List, Optional

from domain.protocol.types import (
    ProtocolCandidate,
    ProtocolReadinessIssue,
    StructuredQuery,
)
import infrastructure.db.catalog.clients as clients_repo
from infrastructure.protocol.ucp_profile import validate_ucp_profile


def discover_ucp_candidates(
    *,
    client_id: str,
    structured_query: StructuredQuery,
    brand_id: Optional[str] = None,
    limit: int = 10,
) -> List[ProtocolCandidate]:
    """Mock-first UCP discovery.

    Today: use DB products as the “UCP discovery service”.
    Later: replace with:
    - capability manifest discovery (brand metadata contains endpoints)
    - real discovery endpoint queries
    """

    products: List[Dict[str, Any]] = []
    if brand_id:
        products = clients_repo.list_products(brand_id=brand_id)
    else:
        products = clients_repo.search_products_for_client(
            client_id=client_id, query=structured_query.query_text, limit=limit
        )

    candidates: List[ProtocolCandidate] = []
    for product in products[:limit]:
        meta = product.get("metadata") or {}
        ucp_meta = meta.get("ucp") or {}
        attributes = ucp_meta.get("attributes") or meta.get("attributes") or {}
        candidates.append(
            ProtocolCandidate(
                id=product["id"],
                name=product.get("name") or "",
                description=product.get("description") or "",
                protocol="ucp",
                offer_url=_pick(ucp_meta, meta, "offer_url", "url"),
                merchant_name=_pick(ucp_meta, meta, "merchant_name"),
                price=_pick_number(ucp_meta, meta, "price"),
                currency=_pick(ucp_meta, meta, "currency"),
                availability=_pick(ucp_meta, meta, "availability"),
                available_for_sale=_pick_bool(ucp_meta, meta, "available_for_sale"),
                inventory_quantity=_pick_int(ucp_meta, meta, "inventory_quantity"),
                attributes=attributes if isinstance(attributes, dict) else {},
                raw={"product": product},
            )
        )
    return candidates


def validate_ucp_candidate(
    candidate: ProtocolCandidate,
) -> List[ProtocolReadinessIssue]:
    issues: List[ProtocolReadinessIssue] = []
    if not candidate.offer_url:
        issues.append(
            ProtocolReadinessIssue(
                field="offer_url",
                severity="error",
                message="Missing offer_url; UCP products typically include a landing URL.",
                fix="Provide offer_url in metadata.ucp.offer_url.",
            )
        )
    if candidate.price is None:
        issues.append(
            ProtocolReadinessIssue(
                field="price",
                severity="warning",
                message="Missing price; UCP discovery results should be price-aware.",
                fix="Provide price in metadata.ucp.price.",
            )
        )
    if candidate.available_for_sale is None and not candidate.availability:
        issues.append(
            ProtocolReadinessIssue(
                field="available_for_sale",
                severity="warning",
                message="Missing availability/available_for_sale; UCP discovery benefits from real-time inventory.",
                fix="Provide available_for_sale or availability in metadata.ucp.",
            )
        )
    issues.extend(_validate_brand_ucp_profile(candidate))
    return issues


def _validate_brand_ucp_profile(
    candidate: ProtocolCandidate,
) -> List[ProtocolReadinessIssue]:
    product = candidate.raw.get("product") if isinstance(candidate.raw, dict) else None
    brand_id = product.get("brand_id") if isinstance(product, dict) else None
    if not brand_id:
        return [
            ProtocolReadinessIssue(
                field="brand_id",
                severity="warning",
                message="Missing brand_id; cannot validate UCP business profile.",
                fix="Associate product with a brand to enable UCP validation.",
            )
        ]
    brand = clients_repo.get_brand(brand_id=brand_id)
    if not brand:
        return [
            ProtocolReadinessIssue(
                field="brand",
                severity="warning",
                message="Brand not found; cannot validate UCP business profile.",
                fix="Ensure brand exists and is linked to this product.",
            )
        ]
    meta = brand.get("metadata") or {}
    ucp_profile = meta.get("ucp_profile")
    if not isinstance(ucp_profile, dict):
        return [
            ProtocolReadinessIssue(
                field="ucp_profile",
                severity="error",
                message="Missing UCP business profile for brand.",
                fix="Add brands.metadata_json.ucp_profile (/.well-known/ucp equivalent).",
            )
        ]
    report = validate_ucp_profile(ucp_profile)
    return report.issues


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
