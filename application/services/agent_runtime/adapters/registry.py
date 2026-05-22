from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from application.services.agent_runtime.adapters.types import (
    AdapterExecutionError,
    AdapterRequest,
)


@dataclass(frozen=True)
class AdapterSpec:
    id: str
    channel_type: str
    permission_scope: str
    effect_class: str
    allowed_capabilities: tuple[str, ...]
    external_side_effects: bool = False
    writes_external_system: bool = False
    requires_operator_review: bool = False
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allowed_capabilities"] = list(self.allowed_capabilities)
        return payload


_ADAPTERS: dict[str, AdapterSpec] = {
    "protocol.readiness.v1": AdapterSpec(
        id="protocol.readiness.v1",
        channel_type="protocol",
        permission_scope="protocol.readiness:read",
        effect_class="read",
        allowed_capabilities=("check_protocol_readiness",),
        external_side_effects=False,
        writes_external_system=False,
        requires_operator_review=False,
        description="Read-only ACP/UCP readiness inspection for product metadata.",
    ),
    "protocol.discovery.v1": AdapterSpec(
        id="protocol.discovery.v1",
        channel_type="protocol",
        permission_scope="protocol.discovery:read",
        effect_class="read",
        allowed_capabilities=("discover_protocol_candidates",),
        external_side_effects=False,
        writes_external_system=False,
        requires_operator_review=False,
        description="Read-only ACP/UCP candidate discovery for product search.",
    ),
}


def get_adapter_spec(adapter_id: str | None) -> AdapterSpec | None:
    key = str(adapter_id or "").strip()
    if not key:
        return None
    return _ADAPTERS.get(key)


def list_adapter_specs() -> list[AdapterSpec]:
    return list(_ADAPTERS.values())


def adapter_spec_for_capability(capability_name: str | None) -> AdapterSpec | None:
    key = str(capability_name or "").strip()
    if not key:
        return None
    for adapter in list_adapter_specs():
        if key in adapter.allowed_capabilities:
            return adapter
    return None


def validate_adapter_request(
    *,
    request: AdapterRequest,
    expected: AdapterSpec | Mapping[str, Any] | None = None,
) -> AdapterSpec:
    spec = _coerce_adapter_spec(expected) or get_adapter_spec(request.adapter_id)
    if not spec:
        raise AdapterExecutionError(f"Unsupported adapter: {request.adapter_id}")
    if request.adapter_id != spec.id:
        raise AdapterExecutionError(
            f"Adapter id mismatch: request={request.adapter_id}, expected={spec.id}"
        )
    if request.channel_type != spec.channel_type:
        raise AdapterExecutionError(
            "Adapter channel mismatch: "
            f"request={request.channel_type}, expected={spec.channel_type}"
        )
    if request.capability_name not in spec.allowed_capabilities:
        raise AdapterExecutionError(
            f"Adapter '{spec.id}' cannot execute capability "
            f"'{request.capability_name}'"
        )
    return spec


def _coerce_adapter_spec(value: AdapterSpec | Mapping[str, Any] | None) -> AdapterSpec | None:
    if value is None:
        return None
    if isinstance(value, AdapterSpec):
        return value
    return AdapterSpec(
        id=str(value.get("id") or ""),
        channel_type=str(value.get("channel_type") or ""),
        permission_scope=str(value.get("permission_scope") or ""),
        effect_class=str(value.get("effect_class") or ""),
        allowed_capabilities=tuple(
            str(item)
            for item in value.get("allowed_capabilities", [])
            if str(item).strip()
        ),
        external_side_effects=bool(value.get("external_side_effects")),
        writes_external_system=bool(value.get("writes_external_system")),
        requires_operator_review=bool(value.get("requires_operator_review")),
        description=str(value.get("description") or ""),
    )
