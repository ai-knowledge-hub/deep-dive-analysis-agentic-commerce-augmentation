from __future__ import annotations

import csv
import io
import json
import os
from typing import Any, Dict
import urllib.error
import urllib.parse
import urllib.request

from domain.protocol.scoring import score_structured_match
from domain.protocol.types import ProtocolCandidate, StructuredQuery
import infrastructure.db.catalog.clients as clients_repo

DEFAULT_HTTP_TIMEOUT_SECONDS = 8


def discover_live_acp_feed_candidates(
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
    live_config = _acp_live_discovery_config(metadata)
    if not live_config:
        return []
    feed_url = str(live_config.get("feed_url") or "").strip()
    if not feed_url:
        return []
    text = _fetch_text(
        feed_url,
        timeout_seconds=int(
            live_config.get("timeout_seconds") or DEFAULT_HTTP_TIMEOUT_SECONDS
        ),
    )
    if not text:
        return []
    records = _parse_feed_records(text, feed_url=feed_url)
    candidates = [
        _candidate_from_feed_record(record, brand=brand, feed_url=feed_url)
        for record in records
        if _eligible_for_search(record)
    ]
    scored = [
        candidate
        for candidate in candidates
        if score_structured_match(structured_query, candidate).score > 0
    ]
    scored.sort(
        key=lambda candidate: score_structured_match(
            structured_query,
            candidate,
        ).score,
        reverse=True,
    )
    return scored[:limit]


def _acp_live_discovery_config(metadata: Dict[str, Any]) -> Dict[str, Any] | None:
    acp = metadata.get("acp") if isinstance(metadata.get("acp"), dict) else {}
    config = (
        acp.get("live_discovery")
        if isinstance(acp.get("live_discovery"), dict)
        else {}
    )
    enabled = _truthy(
        config.get("enabled")
        or acp.get("live_discovery_enabled")
        or metadata.get("acp_live_discovery_enabled")
    )
    if not enabled:
        return None
    feed_url = config.get("feed_url") or acp.get("feed_url") or metadata.get("acp_feed_url")
    if not isinstance(feed_url, str) or not feed_url.strip():
        return None
    return {
        "feed_url": feed_url,
        "timeout_seconds": config.get("timeout_seconds"),
    }


def _fetch_text(url: str, *, timeout_seconds: int) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    if not _host_allowed(parsed.hostname):
        return ""
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json, application/x-ndjson, text/csv, text/plain",
            "User-Agent": "AgenticCommerceControlPlane/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            if not _response_url_allowed(url, response):
                return ""
            raw = response.read(5_000_000)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ""


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


def _parse_feed_records(text: str, *, feed_url: str) -> list[Dict[str, Any]]:
    stripped = text.strip()
    if not stripped:
        return []
    parsed_url = urllib.parse.urlparse(feed_url)
    path = parsed_url.path.lower()
    if path.endswith(".csv") or path.endswith(".csv.gz"):
        return _parse_csv_records(stripped)
    if "\n" in stripped and not stripped.startswith(("{", "[")):
        return _parse_jsonl_records(stripped)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return _parse_jsonl_records(stripped)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("products", "items", "data"):
            items = payload.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return [payload]
    return []


def _parse_jsonl_records(text: str) -> list[Dict[str, Any]]:
    records: list[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _parse_csv_records(text: str) -> list[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _eligible_for_search(record: Dict[str, Any]) -> bool:
    return _truthy(
        record.get("is_eligible_search")
        if "is_eligible_search" in record
        else record.get("enable_search")
    )


def _candidate_from_feed_record(
    record: Dict[str, Any],
    *,
    brand: Dict[str, Any],
    feed_url: str,
) -> ProtocolCandidate:
    price, currency = _parse_price(record.get("price") or record.get("sale_price"))
    attributes = {
        key: value
        for key, value in record.items()
        if key
        not in {
            "id",
            "title",
            "description",
            "link",
            "url",
            "price",
            "sale_price",
            "availability",
            "is_eligible_search",
            "enable_search",
            "is_eligible_checkout",
            "enable_checkout",
        }
        and value not in (None, "")
    }
    return ProtocolCandidate(
        id=str(record.get("id") or record.get("item_id") or record.get("offer_id") or ""),
        name=str(record.get("title") or record.get("name") or ""),
        description=str(record.get("description") or ""),
        protocol="acp",
        offer_url=_string(record.get("link") or record.get("url")),
        merchant_name=str(record.get("seller_name") or brand.get("name") or ""),
        price=price,
        currency=currency,
        availability=_string(record.get("availability")),
        available_for_sale=_availability_for_sale(record.get("availability")),
        inventory_quantity=_pick_int(record, "inventory_quantity"),
        attributes=attributes,
        raw={
            "source": "acp_product_feed",
            "brand_id": brand.get("id"),
            "feed_url": feed_url,
            "product": record,
        },
    )


def _parse_price(value: Any) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    parts = str(value).strip().split()
    if not parts:
        return None, None
    try:
        price = float(parts[0])
    except ValueError:
        return None, parts[-1] if len(parts[-1]) == 3 else None
    currency = parts[-1].upper() if len(parts) > 1 and len(parts[-1]) == 3 else None
    return price, currency


def _availability_for_sale(value: Any) -> bool | None:
    availability = str(value or "").strip().lower()
    if availability in {"in_stock", "pre_order", "backorder"}:
        return True
    if availability == "out_of_stock":
        return False
    return None


def _string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


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


def _pick_int(source: Dict[str, Any], key: str) -> int | None:
    value = source.get(key)
    try:
        return int(value) if value is not None and value != "" else None
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
