from __future__ import annotations

import json
import os
from typing import Any, Dict
import urllib.error
import urllib.parse
import urllib.request

from domain.protocol.types import ProtocolCandidate, StructuredQuery
import infrastructure.db.catalog.clients as clients_repo
from infrastructure.protocol.ucp_profile import validate_ucp_profile

CATALOG_SEARCH_CAPABILITY = "dev.ucp.shopping.catalog.search"
DEFAULT_HTTP_TIMEOUT_SECONDS = 8


def discover_live_ucp_catalog_candidates(
    *,
    client_id: str,
    structured_query: StructuredQuery,
    brand_id: str | None,
    limit: int,
) -> list[ProtocolCandidate]:
    if not brand_id:
        return []
    brand = clients_repo.get_brand(brand_id=brand_id)
    if not brand or brand.get("client_id") != client_id:
        return []
    metadata = brand.get("metadata") if isinstance(brand.get("metadata"), dict) else {}
    live_config = _ucp_live_discovery_config(metadata)
    if not live_config:
        return []
    profile = _load_ucp_business_profile(live_config)
    if not profile:
        return []
    report = validate_ucp_profile(profile)
    if any(issue.severity == "error" for issue in report.issues):
        return []
    endpoint = _catalog_search_endpoint(profile)
    if not endpoint:
        return []
    response = _post_catalog_search(
        endpoint=endpoint,
        query=structured_query,
        limit=limit,
        agent_profile_url=live_config.get("agent_profile_url"),
        timeout_seconds=int(
            live_config.get("timeout_seconds") or DEFAULT_HTTP_TIMEOUT_SECONDS
        ),
    )
    products = response.get("products") if isinstance(response, dict) else None
    if not isinstance(products, list):
        return []
    candidates = []
    for product in products[:limit]:
        if isinstance(product, dict):
            candidates.append(
                _candidate_from_catalog_product(
                    product,
                    brand=brand,
                    endpoint=endpoint,
                    profile=profile,
                    response=response,
                )
            )
    return candidates


def _ucp_live_discovery_config(metadata: Dict[str, Any]) -> Dict[str, Any] | None:
    ucp = metadata.get("ucp") if isinstance(metadata.get("ucp"), dict) else {}
    config = (
        ucp.get("live_discovery")
        if isinstance(ucp.get("live_discovery"), dict)
        else {}
    )
    enabled = _truthy(
        config.get("enabled")
        or ucp.get("live_discovery_enabled")
        or metadata.get("ucp_live_discovery_enabled")
    )
    if not enabled:
        return None
    profile_url = (
        config.get("profile_url")
        or ucp.get("profile_url")
        or metadata.get("ucp_profile_url")
    )
    inline_profile = metadata.get("ucp_profile")
    if not isinstance(profile_url, str) and not isinstance(inline_profile, dict):
        return None
    return {
        "profile_url": profile_url if isinstance(profile_url, str) else None,
        "inline_profile": inline_profile if isinstance(inline_profile, dict) else None,
        "agent_profile_url": config.get("agent_profile_url")
        or ucp.get("agent_profile_url")
        or metadata.get("ucp_agent_profile_url"),
        "timeout_seconds": config.get("timeout_seconds"),
    }


def _load_ucp_business_profile(config: Dict[str, Any]) -> Dict[str, Any] | None:
    inline_profile = config.get("inline_profile")
    if isinstance(inline_profile, dict):
        return inline_profile
    profile_url = str(config.get("profile_url") or "").strip()
    if not profile_url:
        return None
    payload = _fetch_json(profile_url, timeout_seconds=DEFAULT_HTTP_TIMEOUT_SECONDS)
    return payload if isinstance(payload, dict) else None


def _catalog_search_endpoint(profile: Dict[str, Any]) -> str | None:
    ucp = profile.get("ucp") if isinstance(profile.get("ucp"), dict) else {}
    capabilities = (
        ucp.get("capabilities") if isinstance(ucp.get("capabilities"), dict) else {}
    )
    if CATALOG_SEARCH_CAPABILITY not in capabilities:
        return None
    rest_endpoint = _rest_service_endpoint(ucp)
    if not rest_endpoint:
        return None
    return f"{rest_endpoint.rstrip('/')}/catalog/search"


def _rest_service_endpoint(ucp: Dict[str, Any]) -> str | None:
    services = ucp.get("services")
    if not isinstance(services, dict):
        return None
    for entries in services.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if (
                isinstance(entry, dict)
                and entry.get("transport") == "rest"
                and isinstance(entry.get("endpoint"), str)
            ):
                endpoint = str(entry["endpoint"]).strip()
                return endpoint if endpoint.startswith("https://") else None
    return None


def _post_catalog_search(
    *,
    endpoint: str,
    query: StructuredQuery,
    limit: int,
    agent_profile_url: Any,
    timeout_seconds: int,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "query": query.query_text,
        "pagination": {"limit": max(1, min(limit, 50))},
    }
    filters: Dict[str, Any] = {}
    if query.price_max is not None:
        filters["price"] = {"max": int(query.price_max * 100)}
    if query.required_attributes:
        filters["tags"] = query.required_attributes
    if filters:
        body["filters"] = filters
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if isinstance(agent_profile_url, str) and agent_profile_url.strip():
        headers["UCP-Agent"] = f'profile="{agent_profile_url.strip()}"'
    return _fetch_json(
        endpoint,
        method="POST",
        body=body,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )


def _fetch_json(
    url: str,
    *,
    method: str = "GET",
    body: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return {}
    if not _host_allowed(parsed.hostname):
        return {}
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "User-Agent": "AgenticCommerceControlPlane/1.0",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            if not _response_url_allowed(url, response):
                return {}
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type.lower():
                return {}
            raw = response.read(1_000_000)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _response_url_allowed(requested_url: str, response: Any) -> bool:
    final_url = requested_url
    geturl = getattr(response, "geturl", None)
    if callable(geturl):
        final_url = str(geturl() or requested_url)
    requested = urllib.parse.urlparse(requested_url)
    final = urllib.parse.urlparse(final_url)
    if final.scheme != "https" or not final.hostname:
        return False
    if final.hostname.lower() != str(requested.hostname or "").lower():
        return False
    return _host_allowed(final.hostname)


def _host_allowed(hostname: str) -> bool:
    if os.getenv("PROTOCOL_ALLOW_ALL_HOSTS", "0").lower() in {"1", "true", "yes"}:
        return True
    allowlist_raw = os.getenv("PROTOCOL_FETCH_ALLOWLIST") or os.getenv(
        "WEB_FETCH_ALLOWLIST",
        "",
    )
    allowlist = [
        entry.strip().lower() for entry in allowlist_raw.split(",") if entry.strip()
    ]
    host = hostname.lower()
    return any(host == entry or host.endswith(f".{entry}") for entry in allowlist)


def _candidate_from_catalog_product(
    product: Dict[str, Any],
    *,
    brand: Dict[str, Any],
    endpoint: str,
    profile: Dict[str, Any],
    response: Dict[str, Any],
) -> ProtocolCandidate:
    variant = _first_variant(product)
    price, currency = _catalog_price(product, variant)
    available = _catalog_available(variant)
    attributes = _catalog_attributes(product, variant)
    description = _catalog_text(product.get("description"))
    variant_description = _catalog_text(variant.get("description")) if variant else ""
    return ProtocolCandidate(
        id=str(product.get("id") or variant.get("id") or ""),
        name=str(product.get("title") or product.get("handle") or ""),
        description=description or variant_description,
        protocol="ucp",
        offer_url=product.get("url") if isinstance(product.get("url"), str) else None,
        merchant_name=str(brand.get("name") or ""),
        price=price,
        currency=currency,
        availability=(
            "in_stock"
            if available is True
            else "out_of_stock"
            if available is False
            else None
        ),
        available_for_sale=available,
        inventory_quantity=_pick_int(variant, "inventory_quantity"),
        attributes=attributes,
        raw={
            "source": "ucp_catalog_search",
            "brand_id": brand.get("id"),
            "catalog_search_endpoint": endpoint,
            "product": product,
            "ucp": response.get("ucp"),
            "profile_version": (
                profile.get("ucp", {}).get("version")
                if isinstance(profile.get("ucp"), dict)
                else None
            ),
        },
    )


def _first_variant(product: Dict[str, Any]) -> Dict[str, Any]:
    variants = product.get("variants")
    if isinstance(variants, list):
        for variant in variants:
            if isinstance(variant, dict):
                return variant
    return {}


def _catalog_price(
    product: Dict[str, Any], variant: Dict[str, Any]
) -> tuple[float | None, str | None]:
    price_obj = variant.get("price") if isinstance(variant.get("price"), dict) else None
    if not price_obj:
        range_obj = (
            product.get("price_range")
            if isinstance(product.get("price_range"), dict)
            else {}
        )
        price_obj = (
            range_obj.get("min") if isinstance(range_obj.get("min"), dict) else None
        )
    if not isinstance(price_obj, dict):
        return None, None
    amount = price_obj.get("amount")
    currency = price_obj.get("currency")
    try:
        price = float(amount) / 100.0
    except (TypeError, ValueError):
        price = None
    return price, str(currency) if isinstance(currency, str) else None


def _catalog_available(variant: Dict[str, Any]) -> bool | None:
    availability = variant.get("availability")
    if isinstance(availability, dict):
        value = availability.get("available")
        if isinstance(value, bool):
            return value
    return None


def _catalog_attributes(
    product: Dict[str, Any], variant: Dict[str, Any]
) -> Dict[str, Any]:
    attributes: Dict[str, Any] = {}
    metadata = product.get("metadata")
    if isinstance(metadata, dict):
        attributes.update(metadata)
    tags = product.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str):
                attributes[tag.strip().lower().replace(" ", "_")] = True
    categories = product.get("categories")
    if isinstance(categories, list):
        attributes["categories"] = categories
    options = variant.get("options") or product.get("options")
    if isinstance(options, list):
        attributes["options"] = options
    return attributes


def _catalog_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("plain", "markdown", "html"):
            if isinstance(value.get(key), str):
                return value[key]
    return ""


def _pick_int(source: Dict[str, Any], key: str) -> int | None:
    value = source.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False
