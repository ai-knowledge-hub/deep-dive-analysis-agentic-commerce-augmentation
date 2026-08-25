from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Protocol

from domain.security.contract_v1 import REQUIRED_BLOCKED_CAPABILITIES


BETA_RELEASE_POLICY_ID = "agent-runtime-beta-v1"


class CapabilityMetadata(Protocol):
    name: str
    tool_id: str
    effect_class: str


@dataclass(frozen=True)
class CapabilityReleaseDisposition:
    capability_id: str
    tool_id: str
    effect_class: str
    status: str
    release_gate_id: str | None = None


class BetaReleaseGateError(ValueError):
    pass


def _allowed(
    capability_id: str, tool_id: str, effect_class: str
) -> CapabilityReleaseDisposition:
    return CapabilityReleaseDisposition(
        capability_id=capability_id,
        tool_id=tool_id,
        effect_class=effect_class,
        status="allowed",
    )


def _blocked(
    capability_id: str,
    tool_id: str,
    effect_class: str,
    release_gate_id: str,
) -> CapabilityReleaseDisposition:
    return CapabilityReleaseDisposition(
        capability_id=capability_id,
        tool_id=tool_id,
        effect_class=effect_class,
        status="blocked",
        release_gate_id=release_gate_id,
    )


# This is deliberately an exhaustive classification of the executable registry.
# Adding or renaming a capability must make an explicit beta release decision.
_BETA_CAPABILITY_DISPOSITIONS = {
    item.capability_id: item
    for item in (
        _allowed(
            "freeze_retrieval_protocol",
            "retrieval.freeze_protocol",
            "write_low_risk",
        ),
        _allowed(
            "run_control_baseline",
            "experiment.run_control_baseline",
            "write_low_risk",
        ),
        _allowed("seed_hypotheses", "hypothesis.seed", "write_low_risk"),
        _allowed("generate_variants", "variant.generate", "write_low_risk"),
        _allowed("run_variant", "experiment.run_variant", "write_low_risk"),
        _allowed(
            "request_synthetic_validation",
            "validation.request_synthetic",
            "external_side_effect",
        ),
        _allowed(
            "review_validation_readiness",
            "validation.review_readiness",
            "read",
        ),
        _allowed(
            "check_protocol_readiness",
            "protocol.readiness_check",
            "read",
        ),
        _allowed(
            "discover_protocol_candidates",
            "protocol.discover_candidates",
            "read",
        ),
        _allowed(
            "update_posterior_and_decisions",
            "learning.update_posterior_and_decisions",
            "write_low_risk",
        ),
        _allowed(
            "recommend_next_action",
            "policy.recommend_next_action",
            "recommend",
        ),
        _allowed("promote_variant_lab", "promotion.promote_lab", "write_high_risk"),
        *(
            _blocked(
                requirement.capability_id,
                requirement.tool_id,
                requirement.effect_class,
                requirement.release_gate_id,
            )
            for requirement in REQUIRED_BLOCKED_CAPABILITIES.values()
        ),
    )
}


def capability_release_dispositions() -> tuple[CapabilityReleaseDisposition, ...]:
    return tuple(_BETA_CAPABILITY_DISPOSITIONS.values())


def blocked_capability_release_dispositions(
) -> tuple[CapabilityReleaseDisposition, ...]:
    return tuple(
        item
        for item in capability_release_dispositions()
        if item.status == "blocked"
    )


def release_dispositions_for_gate(
    release_gate_id: str,
) -> tuple[CapabilityReleaseDisposition, ...]:
    return tuple(
        item
        for item in blocked_capability_release_dispositions()
        if item.release_gate_id == release_gate_id
    )


def validate_registry_release_policy(
    capabilities: Iterable[CapabilityMetadata],
) -> list[str]:
    actual = {item.name: item for item in capabilities}
    classified = set(_BETA_CAPABILITY_DISPOSITIONS)
    errors: list[str] = []
    missing = sorted(set(actual) - classified)
    if missing:
        errors.append(
            "beta release policy has unclassified registry capabilities: "
            + ", ".join(missing)
        )
    stale = sorted(classified - set(actual))
    if stale:
        errors.append(
            "beta release policy references missing registry capabilities: "
            + ", ".join(stale)
        )
    for capability_id in sorted(set(actual).intersection(classified)):
        spec = actual[capability_id]
        disposition = _BETA_CAPABILITY_DISPOSITIONS[capability_id]
        if spec.tool_id != disposition.tool_id:
            errors.append(
                f"{capability_id}: beta release policy tool_id "
                f"{disposition.tool_id!r} does not match registry {spec.tool_id!r}"
            )
        if spec.effect_class != disposition.effect_class:
            errors.append(
                f"{capability_id}: beta release policy effect_class "
                f"{disposition.effect_class!r} does not match registry "
                f"{spec.effect_class!r}"
            )
    for capability_id, requirement in REQUIRED_BLOCKED_CAPABILITIES.items():
        disposition = _BETA_CAPABILITY_DISPOSITIONS.get(capability_id)
        expected = (
            requirement.tool_id,
            requirement.effect_class,
            "blocked",
            requirement.release_gate_id,
        )
        actual_disposition = (
            disposition.tool_id,
            disposition.effect_class,
            disposition.status,
            disposition.release_gate_id,
        ) if disposition is not None else None
        if actual_disposition != expected:
            errors.append(
                f"{capability_id}: beta release disposition must exactly match "
                "the immutable v1 blocked-capability contract"
            )
    return errors


def assert_beta_capability_available(
    capability_id: str,
    *,
    tool_id: str | None = None,
    effect_class: str | None = None,
) -> None:
    normalized = str(capability_id or "").strip()
    required_block = REQUIRED_BLOCKED_CAPABILITIES.get(normalized)
    if required_block is not None:
        if (
            tool_id is not None
            and tool_id != required_block.tool_id
            or effect_class is not None
            and effect_class != required_block.effect_class
        ):
            raise BetaReleaseGateError(
                f"Capability '{normalized}' registry metadata drifted from "
                f"{BETA_RELEASE_POLICY_ID}"
            )
        raise BetaReleaseGateError(
            f"Capability '{normalized}' is blocked by beta release gate "
            f"'{required_block.release_gate_id}'"
        )
    disposition = _BETA_CAPABILITY_DISPOSITIONS.get(normalized)
    if disposition is None:
        raise BetaReleaseGateError(
            f"Capability '{normalized}' has no {BETA_RELEASE_POLICY_ID} disposition"
        )
    if tool_id is not None and tool_id != disposition.tool_id:
        raise BetaReleaseGateError(
            f"Capability '{normalized}' registry metadata drifted from "
            f"{BETA_RELEASE_POLICY_ID}"
        )
    if effect_class is not None and effect_class != disposition.effect_class:
        raise BetaReleaseGateError(
            f"Capability '{normalized}' registry metadata drifted from "
            f"{BETA_RELEASE_POLICY_ID}"
        )
    if disposition.status == "blocked":
        raise BetaReleaseGateError(
            f"Capability '{normalized}' is blocked by beta release gate "
            f"'{disposition.release_gate_id}'"
        )


def beta_release_policy_payload() -> Mapping[str, object]:
    return {
        "id": BETA_RELEASE_POLICY_ID,
        "capability_dispositions": [
            asdict(item) for item in capability_release_dispositions()
        ],
    }


__all__ = [
    "BETA_RELEASE_POLICY_ID",
    "BetaReleaseGateError",
    "CapabilityReleaseDisposition",
    "assert_beta_capability_available",
    "beta_release_policy_payload",
    "blocked_capability_release_dispositions",
    "capability_release_dispositions",
    "release_dispositions_for_gate",
    "validate_registry_release_policy",
]
