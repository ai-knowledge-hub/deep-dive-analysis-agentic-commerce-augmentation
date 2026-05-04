from __future__ import annotations

import sys
from typing import Any, Dict, List

from application.services.agent_runtime.registry import (
    default_tool_ownership_records,
    registry_contract_payload as _default_registry_contract_payload,
    registry_fingerprint as _default_registry_fingerprint,
)
from infrastructure.db.agent.agent_registry import (
    ensure_agent_registry_tool_ownership,
    list_agent_registry_tool_ownership,
)


def registry_ownership() -> List[Dict[str, Any]]:
    ownership = ensure_agent_registry_tool_ownership(
        ownership=default_tool_ownership_records(),
        source="registry_default",
    )
    return ownership or list_agent_registry_tool_ownership()


def registry_payload_and_fingerprint() -> tuple[Dict[str, Any], str]:
    ownership = registry_ownership()
    try:
        registry_payload = _registry_contract_payload()(ownership_by_tool=ownership)
    except TypeError:
        registry_payload = _registry_contract_payload()()
    try:
        fingerprint = _registry_fingerprint()(ownership_by_tool=ownership)
    except TypeError:
        fingerprint = _registry_fingerprint()()
    return registry_payload, fingerprint


def _registry_contract_payload():
    agent_runs_route = sys.modules.get("api.routes.agent_runs")
    return getattr(
        agent_runs_route,
        "registry_contract_payload",
        _default_registry_contract_payload,
    )


def _registry_fingerprint():
    agent_runs_route = sys.modules.get("api.routes.agent_runs")
    return getattr(
        agent_runs_route,
        "registry_fingerprint",
        _default_registry_fingerprint,
    )
