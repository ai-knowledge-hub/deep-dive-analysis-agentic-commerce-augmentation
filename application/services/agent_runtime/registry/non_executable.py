from __future__ import annotations

from typing import Any, Dict, Mapping

from application.services.agent_runtime.adapters.registry import list_adapter_specs

_NON_EXECUTABLE_TOOL_ADAPTER_IDS = {
    "protocol.acp.checkout": "protocol.checkout.v1",
    "protocol.ucp.checkout": "protocol.checkout.v1",
    "protocol.payment.delegate": "protocol.payment_delegation.v1",
    "browser.checkout_fallback": "fallback.browser_checkout.v1",
}


def non_executable_tool_contract(
    tool_id: str | None,
    *,
    adapters_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    requested_tool_id = str(tool_id or "").strip()
    adapter_id = _NON_EXECUTABLE_TOOL_ADAPTER_IDS.get(requested_tool_id)
    if not adapter_id:
        return {}
    adapters = dict(
        adapters_by_id
        or {adapter.id: adapter.to_dict() for adapter in list_adapter_specs()}
    )
    adapter = dict(adapters.get(adapter_id) or {})
    return {
        "adapter_id": adapter_id,
        "contract_intent": adapter.get("contract_intent") or "readiness_boundary",
        "receipt_contract": dict(adapter.get("receipt_contract") or {}),
        "blocked_reason": (
            "readiness_boundary_only_no_transaction_execution"
            if adapter.get("contract_intent") == "readiness_boundary"
            else "non_executable_contract"
        ),
    }
