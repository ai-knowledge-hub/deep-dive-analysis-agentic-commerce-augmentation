from __future__ import annotations

import sys
from typing import Any, Dict, List

from application.services.agent_runtime.registry import (
    default_tool_ownership_records,
    list_static_harness_profiles,
    registry_contract_payload as _default_registry_contract_payload,
    registry_fingerprint as _default_registry_fingerprint,
)
from api.utils.agent_profile_defaults import registry_agent_profile_defaults
from infrastructure.db.agent.agent_registry import (
    ensure_agent_registry_harness_profiles,
    ensure_agent_registry_tool_ownership,
    list_agent_registry_harness_profiles,
    list_agent_registry_tool_ownership,
)


def registry_ownership() -> List[Dict[str, Any]]:
    ownership = ensure_agent_registry_tool_ownership(
        ownership=default_tool_ownership_records(),
        source="registry_default",
    )
    return ownership or list_agent_registry_tool_ownership()


def registry_harness_profiles() -> List[Dict[str, Any]]:
    profiles = ensure_agent_registry_harness_profiles(
        profiles=list_static_harness_profiles(),
        source="registry_default",
    )
    return profiles or list_agent_registry_harness_profiles(status="active")


def registry_payload_and_fingerprint(
    *, client_id: str | None = None
) -> tuple[Dict[str, Any], str]:
    ownership = registry_ownership()
    harness_profiles = registry_harness_profiles()
    agent_profile_defaults = registry_agent_profile_defaults(client_id=client_id)
    try:
        registry_payload = _registry_contract_payload()(
            ownership_by_tool=ownership,
            harness_profiles=harness_profiles,
            agent_profile_defaults=agent_profile_defaults,
        )
    except TypeError:
        registry_payload = _registry_contract_payload()()
    try:
        fingerprint = _registry_fingerprint()(
            ownership_by_tool=ownership,
            harness_profiles=harness_profiles,
            agent_profile_defaults=agent_profile_defaults,
        )
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
