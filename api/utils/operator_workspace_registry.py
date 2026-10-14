"""Read current registry pins without committing inside creation admission."""

from application.services.agent_runtime import registry
import infrastructure.db.agent.agent_registry as agent_registry
import infrastructure.db.agent.agent_profiles as agent_profiles


def current_registry(tenant_id: str):
    def merge(defaults, persisted):
        records = {r["id"]: r for r in defaults}
        records.update({r["id"]: r for r in persisted})
        return list(records.values())

    harnesses = merge(
        registry.list_static_harness_profiles(),
        agent_registry.list_agent_registry_harness_profiles(status=None),
    )
    harnesses = [r for r in harnesses if r.get("status", "active") == "active"]
    profiles = merge(
        registry.list_static_agent_profile_defaults(),
        agent_profiles.list_agent_profiles(),
    )
    profiles = merge(profiles, agent_profiles.list_agent_profiles(tenant_id=tenant_id))
    ownership = (
        agent_registry.list_agent_registry_tool_ownership()
        or registry.default_tool_ownership_records()
    )
    kwargs = {
        "ownership_by_tool": ownership,
        "harness_profiles": harnesses,
        "agent_profile_defaults": profiles,
    }
    return registry.registry_contract_payload(**kwargs), registry.registry_fingerprint(
        **kwargs
    )
