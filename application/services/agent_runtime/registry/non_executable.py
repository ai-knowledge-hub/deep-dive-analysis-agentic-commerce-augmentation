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


def non_executable_tool_contracts(
    *,
    skill_ids_by_tool: Mapping[str, list[str]],
    adapters_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[Dict[str, Any]]:
    contracts = []
    for tool_id in sorted(skill_ids_by_tool):
        contract = non_executable_tool_contract(
            tool_id,
            adapters_by_id=adapters_by_id,
        )
        if contract.get("contract_intent") == "readiness_boundary":
            contracts.append(
                {
                    "tool_id": tool_id,
                    "skill_ids": list(skill_ids_by_tool.get(tool_id) or []),
                    "executable": False,
                    **contract,
                }
            )
    return contracts


def build_skill_tool_mappings(
    *,
    skills: list[Mapping[str, Any]],
    executable_tool_ids: set[str],
    adapters_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[Dict[str, list[str]], list[Dict[str, Any]]]:
    skill_ids_by_tool: Dict[str, list[str]] = {}
    for skill in skills:
        for tool_id in skill.get("tool_ids", []) or []:
            skill_ids_by_tool.setdefault(str(tool_id), []).append(str(skill.get("id")))
    mappings = [
        {
            "tool_id": tool_id,
            "skill_ids": skill_ids,
            "executable": tool_id in executable_tool_ids,
        }
        for tool_id, skill_ids in sorted(skill_ids_by_tool.items())
    ]
    apply_non_executable_tool_contracts(
        skill_tool_mappings=mappings,
        adapters_by_id=adapters_by_id,
    )
    return skill_ids_by_tool, mappings


def apply_non_executable_tool_contracts(
    *,
    skill_tool_mappings: list[Dict[str, Any]],
    adapters_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    for mapping in skill_tool_mappings:
        mapping.update(
            non_executable_tool_contract(
                str(mapping.get("tool_id") or ""),
                adapters_by_id=adapters_by_id,
            )
        )
