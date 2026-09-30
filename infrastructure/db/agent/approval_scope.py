"""Immutable approval-scope comparisons shared by ledger persistence."""

from domain.workflow.approval import ApprovalBinding


_SUPERSESSION_SCOPE_FIELDS = (
    "tenant_id",
    "principal_type",
    "principal_id",
    "workflow_id",
    "capability_id",
    "tool_id",
    "effect_class",
    "native_target",
    "authority_hash",
    "registry_version",
    "registry_fingerprint",
    "harness_id",
    "harness_version",
    "policy_profile_id",
    "policy_version",
)


def bindings_have_compatible_supersession_scope(
    source: ApprovalBinding, replacement: ApprovalBinding
) -> bool:
    return all(
        getattr(source, field) == getattr(replacement, field)
        for field in _SUPERSESSION_SCOPE_FIELDS
    )


__all__ = ["bindings_have_compatible_supersession_scope"]
