from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from application.services.agent_runtime.registry.harnesses import (
    list_static_agent_profile_defaults,
)


def normalize_agent_profile_defaults(
    agent_profile_defaults: Sequence[Mapping[str, Any]] | None,
) -> list[Dict[str, Any]]:
    profiles = (
        agent_profile_defaults
        if agent_profile_defaults is not None
        else list_static_agent_profile_defaults()
    )
    normalized = []
    for profile in profiles:
        item = dict(profile)
        item.pop("created_at", None)
        item.pop("updated_at", None)
        normalized.append(item)
    return normalized


__all__ = ["normalize_agent_profile_defaults"]
