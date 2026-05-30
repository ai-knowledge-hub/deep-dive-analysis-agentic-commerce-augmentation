from __future__ import annotations

from typing import Any, Dict

from application.services.agent_runtime.harness_posture import (
    capability_memory_effect,
    learning_memory_mutation_capabilities,
)
from application.services.agent_runtime.registry.catalog import (
    CapabilitySpec,
    list_capability_specs,
)


def memory_policy_contracts() -> list[Dict[str, Any]]:
    return [
        {
            "memory_policy": "no_mutation",
            "blocked_memory_effects": ["learning_memory_mutation"],
            "blocked_capabilities": learning_memory_mutation_capabilities(),
            "blocked_reason": "Harness memory_policy forbids learning/memory mutation.",
        }
    ]


def memory_metadata_for_capability(capability: CapabilitySpec) -> Dict[str, Any]:
    return _memory_metadata(capability_memory_effect(capability.name))


def memory_metadata_for_tool(tool_id: str) -> Dict[str, Any]:
    effects = {
        capability_memory_effect(spec.name)
        for spec in list_capability_specs()
        if spec.tool_id == tool_id
    }
    effect = "learning_memory_mutation" if "learning_memory_mutation" in effects else "none"
    return _memory_metadata(effect)


def _memory_metadata(memory_effect: str) -> Dict[str, Any]:
    return {
        "memory_effect": memory_effect,
        "blocked_by_memory_policies": (
            ["no_mutation"] if memory_effect == "learning_memory_mutation" else []
        ),
    }


__all__ = [
    "memory_metadata_for_capability",
    "memory_metadata_for_tool",
    "memory_policy_contracts",
]
