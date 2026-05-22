from __future__ import annotations

from typing import Any, Dict, Iterable

from application.ports.deps import AppDeps
from application.services.admin.protocol_discovery_service import (
    ProtocolDiscoveryService,
)
from application.services.agent_runtime.adapters.registry import (
    validate_adapter_request,
)
from application.services.agent_runtime.adapters.types import (
    AdapterExecutionError,
    AdapterReceipt,
    AdapterRequest,
    stable_receipt_id,
)
from domain.protocol.types import ProtocolCandidate

ADAPTER_ID = "protocol.readiness.v1"
CHANNEL_TYPE = "protocol"
DISCOVERY_ADAPTER_ID = "protocol.discovery.v1"


def execute_protocol_readiness_check(
    *,
    deps: AppDeps,
    request: AdapterRequest,
) -> Dict[str, Any]:
    adapter_spec = validate_adapter_request(request=request)
    product_id = str(request.inputs.get("product_id") or "").strip()
    protocols = _normalize_protocols(request.inputs.get("protocols"))
    if not product_id:
        raise AdapterExecutionError("check_protocol_readiness missing product_id")

    product = deps.clients.get_product_for_client(
        client_id=request.client_id,
        product_id=product_id,
    )
    if not product:
        raise AdapterExecutionError("product not found")

    readiness = []
    for protocol in protocols:
        candidate = _to_protocol_candidate(product, protocol=protocol)
        validator = (
            deps.protocol_validate_ucp
            if protocol == "ucp"
            else deps.protocol_validate_acp
        )
        issues = validator(candidate)
        readiness.append(
            {
                "protocol": protocol,
                "product_id": candidate.id,
                "issue_count": len(issues),
                "issues": [getattr(issue, "__dict__", {}) for issue in issues],
                "ready": len(issues) == 0,
            }
        )

    evidence = {
        "protocols_checked": protocols,
        "ready_protocols": [item["protocol"] for item in readiness if item["ready"]],
        "issue_count": sum(int(item["issue_count"]) for item in readiness),
    }
    subject = {
        "product_id": product_id,
        "brand_id": product.get("brand_id"),
    }
    receipt = AdapterReceipt(
        receipt_id=stable_receipt_id(
            adapter_id=adapter_spec.id,
            capability_name=request.capability_name,
            client_id=request.client_id,
            subject=subject,
            evidence=evidence,
        ),
        adapter_id=adapter_spec.id,
        channel_type=adapter_spec.channel_type,
        capability_name=request.capability_name,
        permission_scope=adapter_spec.permission_scope,
        effect_class=adapter_spec.effect_class,
        status="completed",
        subject=subject,
        evidence=evidence,
        risk={
            "external_side_effects": adapter_spec.external_side_effects,
            "writes_external_system": adapter_spec.writes_external_system,
            "requires_operator_review": adapter_spec.requires_operator_review,
        },
    )
    return {
        "product_id": product_id,
        "protocol_readiness": readiness,
        "adapter": {
            "adapter_id": adapter_spec.id,
            "channel_type": adapter_spec.channel_type,
            "permission_scope": adapter_spec.permission_scope,
            "effect_class": adapter_spec.effect_class,
        },
        "receipt": receipt.to_dict(),
        "receipt_id": receipt.receipt_id,
        "status": "protocol_readiness_checked",
    }


def execute_protocol_candidate_discovery(
    *,
    deps: AppDeps,
    request: AdapterRequest,
) -> Dict[str, Any]:
    adapter_spec = validate_adapter_request(request=request)
    query = str(request.inputs.get("query") or "").strip()
    if not query:
        raise AdapterExecutionError("discover_protocol_candidates missing query")
    brand_id = str(request.inputs.get("brand_id") or "").strip() or None
    protocol = str(request.inputs.get("protocol") or "").strip().lower() or None
    if protocol not in {"ucp", "acp", None}:
        raise AdapterExecutionError("protocol must be one of: ucp, acp")
    limit = _safe_limit(request.inputs.get("limit"))
    inferred_intent = request.inputs.get("inferred_intent")
    service = ProtocolDiscoveryService(
        discover_acp_fn=deps.protocol_discover_acp,
        discover_ucp_fn=deps.protocol_discover_ucp,
        validate_acp_fn=deps.protocol_validate_acp,
        validate_ucp_fn=deps.protocol_validate_ucp,
    )
    result = service.discover(
        client_id=request.client_id,
        query=query,
        protocol=protocol,  # type: ignore[arg-type]
        brand_id=brand_id,
        limit=limit,
        inferred_intent=inferred_intent if isinstance(inferred_intent, dict) else None,
    )
    candidates = result.get("candidates") or []
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    evidence = {
        "query": query,
        "protocol": protocol or "all",
        "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
        "candidate_ids": [
            str(item.get("id") or "")
            for item in candidates
            if isinstance(item, dict) and item.get("id")
        ],
        "errors": int(summary.get("errors") or 0),
        "warnings": int(summary.get("warnings") or 0),
    }
    subject = {"brand_id": brand_id, "query": query}
    receipt = AdapterReceipt(
        receipt_id=stable_receipt_id(
            adapter_id=adapter_spec.id,
            capability_name=request.capability_name,
            client_id=request.client_id,
            subject=subject,
            evidence=evidence,
        ),
        adapter_id=adapter_spec.id,
        channel_type=adapter_spec.channel_type,
        capability_name=request.capability_name,
        permission_scope=adapter_spec.permission_scope,
        effect_class=adapter_spec.effect_class,
        status="completed",
        subject=subject,
        evidence=evidence,
        risk={
            "external_side_effects": adapter_spec.external_side_effects,
            "writes_external_system": adapter_spec.writes_external_system,
            "requires_operator_review": adapter_spec.requires_operator_review,
        },
    )
    return {
        **result,
        "adapter": {
            "adapter_id": adapter_spec.id,
            "channel_type": adapter_spec.channel_type,
            "permission_scope": adapter_spec.permission_scope,
            "effect_class": adapter_spec.effect_class,
        },
        "receipt": receipt.to_dict(),
        "receipt_id": receipt.receipt_id,
        "status": "protocol_candidates_discovered",
    }


def _normalize_protocols(value: Any) -> list[str]:
    if isinstance(value, str):
        raw: Iterable[Any] = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        raw = value
    else:
        raw = ["ucp", "acp"]
    protocols = []
    for item in raw:
        protocol = str(item or "").strip().lower()
        if protocol in {"ucp", "acp"} and protocol not in protocols:
            protocols.append(protocol)
    return protocols or ["ucp", "acp"]


def _safe_limit(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 10
    return max(1, min(parsed, 50))


def _to_protocol_candidate(product: Dict[str, Any], *, protocol: str) -> ProtocolCandidate:
    metadata = product.get("metadata") if isinstance(product.get("metadata"), dict) else {}
    protocol_meta = metadata.get(protocol) if isinstance(metadata.get(protocol), dict) else {}
    attributes = protocol_meta.get("attributes") or metadata.get("attributes") or {}
    return ProtocolCandidate(
        id=str(product.get("id") or ""),
        name=str(product.get("name") or ""),
        description=str(product.get("description") or ""),
        protocol=protocol,  # type: ignore[arg-type]
        offer_url=_pick(protocol_meta, metadata, "offer_url", "url")
        or product.get("url"),
        merchant_name=_pick(protocol_meta, metadata, "merchant_name"),
        price=_pick_number(protocol_meta, metadata, "price") or product.get("price"),
        currency=_pick(protocol_meta, metadata, "currency"),
        availability=_pick(protocol_meta, metadata, "availability"),
        available_for_sale=_pick_bool(
            protocol_meta,
            metadata,
            "available_for_sale",
        ),
        inventory_quantity=_pick_int(protocol_meta, metadata, "inventory_quantity"),
        attributes=attributes if isinstance(attributes, dict) else {},
        raw={"product": {**product, "metadata": metadata}},
    )


def _pick(primary: Dict[str, Any], fallback: Dict[str, Any], *keys: str) -> Any:
    for source in (primary, fallback):
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return value
    return None


def _pick_number(primary: Dict[str, Any], fallback: Dict[str, Any], key: str) -> float | None:
    value = _pick(primary, fallback, key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _pick_int(primary: Dict[str, Any], fallback: Dict[str, Any], key: str) -> int | None:
    value = _pick(primary, fallback, key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _pick_bool(primary: Dict[str, Any], fallback: Dict[str, Any], key: str) -> bool | None:
    value = _pick(primary, fallback, key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None
