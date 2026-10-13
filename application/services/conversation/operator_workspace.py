"""Pre-run objective preparation and exact governed creation on the shared gateway."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.capabilities.support import (
    resolve_control_variant_id,
)
from application.services.agent_runtime.governed_runs import (
    create_governed_agent_run_with_initial_plan,
)
from application.services.agent_runtime.planner import build_initial_plan
from application.services.agent_runtime.registry import get_capability_spec
from application.services.agent_runtime.plan_validation import (
    validate_plan_capabilities,
)
from application.services.agent_runtime.harness_posture import (
    validate_harness_capability_effects,
    validate_harness_memory_policy,
    validate_harness_runtime_posture,
)
from domain.workflow.operator_commands import canonical_digest

CAPABILITIES = (
    "freeze_retrieval_protocol",
    "run_control_baseline",
    "seed_hypotheses",
    "generate_variants",
    "run_variant",
    "request_synthetic_validation",
    "review_validation_readiness",
    "update_posterior_and_decisions",
    "recommend_next_action",
)
GOAL = re.compile(
    r"\b(improve|optimise|optimize|compare|evaluate|performance|baseline|commerce)\b",
    re.I,
)
UNSUPPORTED = re.compile(
    r"\b(publish|production|purchase|payment|delete|unlimited|bypass)\b", re.I
)


def require_workspace(
    deps: AppDeps, *, tenant_id: str, principal_id: str, session_id: str
) -> dict:
    workspace = deps.operator_workspace.get_workspace(
        session_id=session_id, tenant_id=tenant_id, principal_id=principal_id
    )
    session = deps.sessions.get_session(session_id=session_id, client_id=tenant_id)
    if (
        not workspace
        or not session
        or session["user_id"] != principal_id.removeprefix("human:")
    ):
        raise LookupError("Conversation not found")
    expected = "operator_run" if workspace["run_id"] else "operator_workspace"
    if (
        session["state"].get("conversation_kind") != expected
        or session["state"].get("run_id") != workspace["run_id"]
    ):
        raise ValueError("Conversation binding is inconsistent")
    return workspace


def open_workspace(
    deps: AppDeps, *, tenant_id: str, principal_id: str, session_id: str | None
) -> dict:
    if session_id:
        return require_workspace(
            deps, tenant_id=tenant_id, principal_id=principal_id, session_id=session_id
        )
    user_id = principal_id.removeprefix("human:")
    deps.users.ensure_user(user_id)
    session = deps.sessions.create_session(
        user_id=user_id,
        client_id=tenant_id,
        state={"conversation_kind": "operator_workspace", "run_id": None},
    )
    deps.operator_workspace.register_workspace(
        session_id=session["id"], tenant_id=tenant_id, principal_id=principal_id
    )
    return require_workspace(
        deps, tenant_id=tenant_id, principal_id=principal_id, session_id=session["id"]
    )


def creation_preflight(
    deps: AppDeps, *, tenant_id: str, message: str, experiment_id: str, registry: Any
) -> dict:
    if not GOAL.search(message) or UNSUPPORTED.search(message):
        raise ValueError(
            "Describe a bounded experiment improvement or comparison objective. Publication and unrestricted execution are unsupported."
        )
    experiment = deps.experiments.get_experiment(experiment_id, client_id=tenant_id)
    if not experiment:
        raise LookupError("Selected experiment is unavailable")
    product = deps.clients.get_product_for_client(
        client_id=tenant_id, product_id=experiment.get("product_id")
    )
    if not product or experiment.get("brand_id") not in {None, product["brand_id"]}:
        raise ValueError("Experiment product scope could not be verified")
    battery = deps.query_batteries.get_battery(
        battery_id=experiment.get("battery_id"), client_id=tenant_id
    )
    if not battery or battery.get("product_id") not in {None, product["id"]}:
        raise ValueError("A tenant-bound query battery is required for this objective")
    queries = deps.query_batteries.list_queries(battery["id"], limit=101)
    if not queries or len(queries) > 100 or not any(q.get("enabled") for q in queries):
        raise ValueError(
            "This objective requires an enabled query battery with at most 100 queries"
        )
    control_id = resolve_control_variant_id(deps=deps, experiment_id=experiment_id)
    control = deps.experiments.get_variant(control_id) if control_id else None
    if not control or control.get("experiment_id") != experiment_id:
        raise ValueError("This objective requires a control variant for its baseline")
    payload, fingerprint = registry()
    harness = next(
        (
            h
            for h in payload["harness_profiles"]
            if h["id"] == "conversation_supervised"
        ),
        None,
    )
    if not harness:
        raise ValueError("The conversation execution posture is unavailable")
    objective = {"type": "experiment_optimisation", "goal": message}
    validate_plan_capabilities(CAPABILITIES, objective=objective)
    validate_harness_runtime_posture(
        harness_profile=harness,
        run_mode="auto_execute_safe",
        policy_profile_id="human_approval_required",
    )
    validate_harness_capability_effects(
        harness_profile=harness, allowed_capabilities=list(CAPABILITIES)
    )
    validate_harness_memory_policy(
        harness_profile=harness, allowed_capabilities=list(CAPABILITIES)
    )
    parameters = {
        "brand_id": product["brand_id"],
        "product_id": product["id"],
        "experiment_id": experiment_id,
        "objective": objective,
        "allowed_capabilities": list(CAPABILITIES),
        "capability_versions": {
            name: get_capability_spec(name).default_version for name in CAPABILITIES
        },
        "budgets": {"max_actions": 12, "max_variant_runs": 1, "max_cost_usd": 5},
        "approval_policy": {},
        "requires_approval": True,
        "run_mode": "auto_execute_safe",
        "harness_id": "conversation_supervised",
        "policy_profile_id": "human_approval_required",
        "agent_profile_id": None,
        "state": "battery_ready",
        "status": "planned",
    }
    plan = [
        a.to_dict()
        for a in build_initial_plan(
            experiment_id=experiment_id,
            allowed_capabilities=list(CAPABILITIES),
            capability_versions=parameters["capability_versions"],
            objective=objective,
            planner_mode=harness["planner_mode"],
        )
    ]
    return {
        "parameters": parameters,
        "registry_fingerprint": fingerprint,
        "scope_digest": canonical_digest(
            {
                "experiment": experiment,
                "product": product,
                "battery": battery,
                "queries": queries,
                "control_variant": control,
            }
        ),
        "plan": plan,
        "scope": {"experiment": experiment["name"], "product": product["name"]},
        "execution_posture": "The worker may schedule work after creation; every action requires its own human approval. No capability runs during creation.",
    }


def prepare_creation(
    deps: AppDeps,
    *,
    workspace: dict,
    message: str,
    experiment_id: str | None,
    registry: Any,
) -> dict:
    if workspace["run_id"]:
        raise ValueError("Use the bound run conversation to supervise this objective")
    candidates = deps.experiments.list_experiments(
        client_id=workspace["tenant_id"], limit=101
    )
    if not experiment_id:
        matches = [
            e
            for e in candidates
            if e.get("name") and e["name"].casefold() in message.casefold()
        ]
        if len(matches) == 1 and len(candidates) <= 100:
            experiment_id = matches[0]["id"]
        elif len(candidates) == 1:
            experiment_id = candidates[0]["id"]
        else:
            return {
                "state": "clarification",
                "answer": "Choose one experiment for this objective.",
                "candidates": [
                    {
                        "id": e["id"],
                        "name": e["name"],
                        "product_name": (
                            deps.clients.get_product_for_client(
                                client_id=workspace["tenant_id"],
                                product_id=e.get("product_id"),
                            )
                            or {}
                        ).get("name", "Unavailable product"),
                    }
                    for e in candidates[:100]
                ],
                "has_more": len(candidates) > 100,
            }
    preflight = creation_preflight(
        deps,
        tenant_id=workspace["tenant_id"],
        message=message,
        experiment_id=experiment_id,
        registry=registry,
    )
    now = datetime.now(timezone.utc)
    proposal = {
        "contract": "workflow.operator-run-creation-proposal.v1",
        "command_type": "create_run",
        "proposal_id": str(uuid.uuid4()),
        "session_id": workspace["session_id"],
        "tenant_id": workspace["tenant_id"],
        "principal_id": workspace["principal_id"],
        "preflight": preflight,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
    }
    return {
        "state": "proposed",
        "answer": "Review this objective and its bounded plan before creating the run.",
        "proposal": deps.operator_workspace.create_proposal(proposal=proposal),
    }


def confirm_creation(
    deps: AppDeps, *, proposal: dict, authorize: Any, registry: Any, coordinator: Any
) -> dict:
    def current():
        require_workspace(
            deps,
            tenant_id=proposal["tenant_id"],
            principal_id=proposal["principal_id"],
            session_id=proposal["session_id"],
        )
        params = proposal["preflight"]["parameters"]
        return creation_preflight(
            deps,
            tenant_id=proposal["tenant_id"],
            message=params["objective"]["goal"],
            experiment_id=params["experiment_id"],
            registry=registry,
        )

    def create():
        payload, fingerprint = registry()
        deps.agent_registry.ensure_agent_registry_version(
            registry_version=str(payload["registry_version"]),
            registry_fingerprint=fingerprint,
            payload=payload,
        )
        run = create_governed_agent_run_with_initial_plan(
            deps=deps,
            completion_coordinator=coordinator,
            client_id=proposal["tenant_id"],
            principal_type="human",
            principal_id=proposal["principal_id"],
            idempotency_key=f"workspace:{proposal['proposal_id']}",
            registry_payload=payload,
            active_registry_fingerprint=fingerprint,
            **proposal["preflight"]["parameters"],
        )

        actions = deps.agent_actions.list_agent_actions(
            agent_run_id=run["id"], limit=501
        )
        actual = [
            (a["capability_name"], a["capability_version"], a["inputs"])
            for a in actions
        ]
        expected = [
            (a["capability_name"], a["capability_version"], a["inputs"])
            for a in proposal["preflight"]["plan"]
        ]
        if actual != expected:
            raise ValueError("Committed plan differs from the reviewed plan")
        return run

    def audit(run):
        return deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=None,
            sequence=0,
            event_type="command_issued",
            status="planned",
            principal_type="human",
            principal_id=proposal["principal_id"],
            note="Confirmed governed conversational run creation",
            is_policy_event=True,
            anchors={
                "command": "create_run",
                "proposal_id": proposal["proposal_id"],
                "proposal_digest": proposal["proposal_digest"],
                "session_id": proposal["session_id"],
            },
        )

    return deps.operator_workspace.commit_creation(
        proposal=proposal,
        authorize=authorize,
        current_preflight=current,
        create_run=create,
        audit=audit,
    )
