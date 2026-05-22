from __future__ import annotations

import uuid
from dataclasses import dataclass


_CAPABILITY_TO_TOOL: dict[str, str] = {
    "freeze_retrieval_protocol": "retrieval.freeze_protocol",
    "run_control_baseline": "experiment.run_control_baseline",
    "seed_hypotheses": "hypothesis.seed",
    "generate_variants": "variant.generate",
    "run_variant": "experiment.run_variant",
    "request_synthetic_validation": "validation.request_synthetic",
    "review_validation_readiness": "validation.review_readiness",
    "check_protocol_readiness": "protocol.readiness_check",
    "discover_protocol_candidates": "protocol.discover_candidates",
    "update_posterior_and_decisions": "learning.update_posterior_and_decisions",
    "recommend_next_action": "policy.recommend_next_action",
    "promote_variant_lab": "promotion.promote_lab",
    "promote_variant_prod": "promotion.promote_prod",
    "publish_copy_revision": "copy.publish_revision",
}

_TOOL_EFFECT_CLASS: dict[str, str] = {
    "retrieval.freeze_protocol": "write_low_risk",
    "experiment.run_control_baseline": "write_low_risk",
    "hypothesis.seed": "write_low_risk",
    "variant.generate": "write_low_risk",
    "experiment.run_variant": "write_low_risk",
    "validation.request_synthetic": "external_side_effect",
    "validation.review_readiness": "read",
    "protocol.readiness_check": "read",
    "protocol.discover_candidates": "read",
    "learning.update_posterior_and_decisions": "write_low_risk",
    "policy.recommend_next_action": "recommend",
    "promotion.promote_lab": "write_high_risk",
    "promotion.promote_prod": "write_high_risk",
    "copy.publish_revision": "write_high_risk",
}

_RUN_MODE_TO_POLICY_PROFILE = {
    "plan_only": "human_approval_required",
    "auto_execute_safe": "safe_auto",
}


def capability_to_tool_id(capability_name: str | None) -> str | None:
    key = str(capability_name or "").strip()
    if not key:
        return None
    return _CAPABILITY_TO_TOOL.get(key, f"legacy.{key}")


def tool_effect_class(tool_id: str | None) -> str | None:
    key = str(tool_id or "").strip()
    if not key:
        return None
    return _TOOL_EFFECT_CLASS.get(key, "write_low_risk")


def policy_profile_for_run_mode(run_mode: str | None) -> str:
    key = str(run_mode or "plan_only").strip().lower()
    return _RUN_MODE_TO_POLICY_PROFILE.get(key, "human_approval_required")


def new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class SkillSpec:
    id: str
    name: str
    description: str
    version: str
    tool_ids: tuple[str, ...]
    risk_class: str
    selection_priority: int = 100
    intent_tags: tuple[str, ...] = ()


_SKILL_SPECS: tuple[SkillSpec, ...] = (
    SkillSpec(
        id="discover-protocol-candidates",
        name="Discover Protocol Candidates",
        description="Find protocol-ready candidates or surface missing protocol fields.",
        version="v1",
        tool_ids=(
            "catalog.search",
            "protocol.acp.search",
            "protocol.ucp.search",
            "protocol.readiness_check",
            "protocol.discover_candidates",
            "product.read",
        ),
        risk_class="read",
        selection_priority=20,
        intent_tags=("discovery", "protocol"),
    ),
    SkillSpec(
        id="optimize-product-representation",
        name="Optimize Product Representation",
        description="Improve product representation for discoverability and retrieval.",
        version="v1",
        tool_ids=(
            "product.read",
            "brand.read",
            "retrieval.freeze_protocol",
            "experiment.run_control_baseline",
            "hypothesis.seed",
            "variant.generate",
            "experiment.run_variant",
            "representation.optimize",
            "copy.revise_draft",
            "learning.update_posterior_and_decisions",
            "policy.recommend_next_action",
        ),
        risk_class="write_low_risk",
        selection_priority=30,
        intent_tags=("optimization", "experimentation"),
    ),
    SkillSpec(
        id="request-validation-and-ingest-result",
        name="Request Validation And Ingest Result",
        description="Request validation, await a result, and ingest it into learning flows.",
        version="v1",
        tool_ids=(
            "validation.request",
            "validation.request_synthetic",
            "validation.review_readiness",
            "validation.result.read",
            "evidence.ingest",
        ),
        risk_class="external_side_effect",
        selection_priority=40,
        intent_tags=("validation", "learning"),
    ),
    SkillSpec(
        id="promote-and-publish-approved-copy",
        name="Promote And Publish Approved Copy",
        description="Promote validated variants and publish approved copy changes.",
        version="v1",
        tool_ids=(
            "validation.review_readiness",
            "promotion.promote_lab",
            "promotion.promote_prod",
            "copy.publish_revision",
        ),
        risk_class="write_high_risk",
        selection_priority=70,
        intent_tags=("promotion", "publishing"),
    ),
    SkillSpec(
        id="triage-failed-run",
        name="Triage Failed Run",
        description="Inspect a failed run and recommend the safest recovery path.",
        version="v1",
        tool_ids=("run.read", "event.read", "policy.inspect", "run.retry_safe"),
        risk_class="recommend",
        selection_priority=10,
        intent_tags=("recovery", "triage"),
    ),
    SkillSpec(
        id="run-safe-browser-fallback-check",
        name="Run Safe Browser Fallback Check",
        description="Verify platform state through a tightly governed browser fallback.",
        version="v1",
        tool_ids=("browser.open", "browser.extract", "browser.assert"),
        risk_class="external_side_effect",
        selection_priority=90,
        intent_tags=("browser_fallback",),
    ),
)


def list_skill_specs() -> list[SkillSpec]:
    return list(_SKILL_SPECS)


def skill_specs_for_tool_id(tool_id: str | None) -> list[SkillSpec]:
    key = str(tool_id or "").strip()
    if not key:
        return []
    return sorted(
        [skill for skill in _SKILL_SPECS if key in skill.tool_ids],
        key=lambda skill: (skill.selection_priority, skill.id),
    )


def select_skill_for_tool_id(
    tool_id: str | None,
    *,
    allowed_skill_ids: tuple[str, ...] | list[str] | set[str] | None = None,
    preferred_skill_id: str | None = None,
) -> SkillSpec | None:
    candidates = skill_specs_for_tool_id(tool_id)
    if not candidates:
        return None
    allowed = {
        str(skill_id).strip()
        for skill_id in (allowed_skill_ids or [])
        if str(skill_id).strip()
    }
    if allowed:
        candidates = [skill for skill in candidates if skill.id in allowed]
        if not candidates:
            return None
    preferred = str(preferred_skill_id or "").strip()
    if preferred:
        for skill in candidates:
            if skill.id == preferred:
                return skill
    return candidates[0]


def skill_id_for_tool_id(
    tool_id: str | None,
    *,
    allowed_skill_ids: tuple[str, ...] | list[str] | set[str] | None = None,
    preferred_skill_id: str | None = None,
) -> str | None:
    selected = select_skill_for_tool_id(
        tool_id,
        allowed_skill_ids=allowed_skill_ids,
        preferred_skill_id=preferred_skill_id,
    )
    return selected.id if selected else None


def skill_id_for_capability(
    capability_name: str | None,
    *,
    allowed_skill_ids: tuple[str, ...] | list[str] | set[str] | None = None,
    preferred_skill_id: str | None = None,
) -> str | None:
    return skill_id_for_tool_id(
        capability_to_tool_id(capability_name),
        allowed_skill_ids=allowed_skill_ids,
        preferred_skill_id=preferred_skill_id,
    )


__all__ = [
    "SkillSpec",
    "capability_to_tool_id",
    "list_skill_specs",
    "new_trace_id",
    "policy_profile_for_run_mode",
    "select_skill_for_tool_id",
    "skill_id_for_capability",
    "skill_id_for_tool_id",
    "skill_specs_for_tool_id",
    "tool_effect_class",
]
