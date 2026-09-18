"""Pure compatibility compiler for the current sequential agent runtime.

The compiled objects are immutable shadow contracts.  They do not authorize
execution and do not replace the current agent-run scheduler or approval
boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from domain.workflow.lifecycle import WorkflowStatus


COMPATIBILITY_SCHEMA_VERSION = "workflow.sequential-compatibility.v1"
INITIAL_GRAPH_REVISION = 1
RESULT_SCHEMA_ID = "agent-action-output"
RESULT_SCHEMA_VERSION = "v1"


class SequentialCompatibilityError(ValueError):
    """Raised when legacy state cannot form one exact workflow snapshot."""


@dataclass(frozen=True)
class SequentialCompatibilityTask:
    task_id: str
    source_action_id: str
    task_key: str
    sequence: int
    task_type: str
    capability_version: str | None
    initial_status: str
    effect_class: str
    skill_id: str | None
    skill_version: str | None
    tool_id: str | None
    tool_version: str | None
    input_json: str
    input_hash: str
    result_schema_id: str
    result_schema_version: str

    def structural_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "source_action_id": self.source_action_id,
            "task_key": self.task_key,
            "sequence": self.sequence,
            "task_type": self.task_type,
            "capability_version": self.capability_version,
            "effect_class": self.effect_class,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "tool_id": self.tool_id,
            "tool_version": self.tool_version,
            "input_hash": self.input_hash,
            "result_schema_id": self.result_schema_id,
            "result_schema_version": self.result_schema_version,
        }


@dataclass(frozen=True)
class SequentialCompatibilityEdge:
    edge_id: str
    from_task_id: str
    to_task_id: str
    join_policy: str = "all"

    def payload(self) -> dict[str, str]:
        return {
            "edge_id": self.edge_id,
            "from_task_id": self.from_task_id,
            "to_task_id": self.to_task_id,
            "join_policy": self.join_policy,
        }


@dataclass(frozen=True)
class SequentialCompatibilityEvent:
    event_id: str
    source_event_id: str
    source_row_order: int
    event_type: str
    entity_type: str
    entity_id: str
    principal_id: str
    causation_id: str
    correlation_id: str
    trace_id: str
    payload_json: str
    payload_hash: str
    occurred_at: str


@dataclass(frozen=True)
class SequentialWorkflowCompatibility:
    workflow_id: str
    tenant_id: str
    source_agent_run_id: str
    root_workflow_id: str
    parent_workflow_id: str | None
    objective_json: str
    objective_hash: str
    initial_status: str
    initial_state: str
    active_revision: int
    principal_type: str
    principal_id: str
    authority_json: str
    authority_hash: str
    budget_json: str
    agent_profile_id: str | None
    harness_id: str
    policy_profile_id: str
    registry_version: str
    registry_fingerprint: str
    idempotency_key: str | None
    request_hash: str
    trace_id: str
    source_created_at: str
    planner_contract_version: str
    graph_hash: str
    structural_digest: str
    tasks: tuple[SequentialCompatibilityTask, ...]
    edges: tuple[SequentialCompatibilityEdge, ...]
    events: tuple[SequentialCompatibilityEvent, ...]


def compile_sequential_workflow(
    *,
    run: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> SequentialWorkflowCompatibility:
    workflow_id = _identifier(run.get("id"), "workflow id")
    tenant_id = _identifier(run.get("client_id"), "tenant id")
    principal_id = _identifier(run.get("principal_id"), "principal id")
    principal_type = _identifier(run.get("principal_type"), "principal type")
    status = _identifier(run.get("status"), "workflow status")
    try:
        WorkflowStatus(status)
    except ValueError as exc:
        raise SequentialCompatibilityError(
            "source run status is outside the workflow lifecycle"
        ) from exc
    active_revision = _positive_int(
        run.get("active_graph_revision", INITIAL_GRAPH_REVISION),
        "active graph revision",
    )
    if active_revision != INITIAL_GRAPH_REVISION:
        raise SequentialCompatibilityError(
            "sequential compatibility supports only graph revision 1"
        )

    ordered_actions = sorted(
        actions,
        key=lambda item: (
            _positive_int(item.get("sequence"), "action sequence"),
            _identifier(item.get("id"), "action id"),
        ),
    )
    sequences = [int(item["sequence"]) for item in ordered_actions]
    if sequences != list(range(1, len(ordered_actions) + 1)):
        raise SequentialCompatibilityError(
            "sequential actions must have a gap-free sequence starting at 1"
        )
    tasks = tuple(_compile_task(action) for action in ordered_actions)
    task_ids = {task.task_id for task in tasks}
    for event in events:
        action_id = _optional_identifier(event.get("action_id"))
        if action_id is not None and action_id not in task_ids:
            raise SequentialCompatibilityError(
                "event action must belong to the projected workflow"
            )
    edges = tuple(
        _compile_edge(workflow_id, left.task_id, right.task_id)
        for left, right in zip(tasks, tasks[1:])
    )
    graph_payload = {
        "schema_version": COMPATIBILITY_SCHEMA_VERSION,
        "workflow_id": workflow_id,
        "revision": INITIAL_GRAPH_REVISION,
        "tasks": [item.structural_payload() for item in tasks],
        "edges": [item.payload() for item in edges],
    }
    graph_hash = _digest(graph_payload)

    objective = _mapping(run.get("objective"), "objective")
    budgets = _mapping(run.get("budgets"), "budgets")
    approval_policy = _mapping(run.get("approval_policy"), "approval policy")
    allowed_capabilities = _string_list(
        run.get("allowed_capabilities"), "allowed capabilities"
    )
    authority = {
        "schema_version": COMPATIBILITY_SCHEMA_VERSION,
        "authority_status": "compatibility_projection_only",
        "tenant_id": tenant_id,
        "principal_type": principal_type,
        "principal_id": principal_id,
        "allowed_capabilities": sorted(allowed_capabilities),
        "allowed_tools": sorted(
            {item.tool_id for item in tasks if item.tool_id is not None}
        ),
        "allowed_effect_classes": sorted({item.effect_class for item in tasks}),
        "requires_approval": bool(run.get("requires_approval", True)),
        "approval_policy": approval_policy,
        "agent_profile_id": _optional_identifier(run.get("agent_profile_id")),
        "harness_id": _identifier(run.get("harness_id"), "harness id"),
        "policy_profile_id": _identifier(
            run.get("policy_profile_id"), "policy profile id"
        ),
        "registry_version": _identifier(
            run.get("registry_version"), "registry version"
        ),
        "registry_fingerprint": _identifier(
            run.get("registry_fingerprint"), "registry fingerprint"
        ),
    }
    request_payload = {
        "objective": objective,
        "allowed_capabilities": sorted(allowed_capabilities),
        "budgets": budgets,
        "approval_policy": approval_policy,
        "principal_type": principal_type,
        "principal_id": principal_id,
        "agent_profile_id": authority["agent_profile_id"],
        "harness_id": authority["harness_id"],
        "policy_profile_id": authority["policy_profile_id"],
        "registry_version": authority["registry_version"],
        "registry_fingerprint": authority["registry_fingerprint"],
    }
    compiled_events = tuple(
        _compile_event(
            workflow_id,
            principal_id,
            _identifier(run.get("trace_id"), "trace id"),
            item,
        )
        for item in sorted(
            events,
            key=lambda event: (
                _non_negative_int(event.get("source_row_order"), "event row order"),
                _identifier(event.get("id"), "event id"),
            ),
        )
    )
    structural_digest = _digest(
        {
            "workflow_id": workflow_id,
            "tenant_id": tenant_id,
            "root_workflow_id": _optional_identifier(run.get("root_run_id"))
            or workflow_id,
            "parent_workflow_id": _optional_identifier(run.get("parent_run_id")),
            "objective_hash": _digest(objective),
            "authority_hash": _digest(authority),
            "budget_hash": _digest(budgets),
            "graph_hash": graph_hash,
            "request_hash": _digest(request_payload),
        }
    )
    return SequentialWorkflowCompatibility(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        source_agent_run_id=workflow_id,
        root_workflow_id=_optional_identifier(run.get("root_run_id")) or workflow_id,
        parent_workflow_id=_optional_identifier(run.get("parent_run_id")),
        objective_json=_canonical_json(objective),
        objective_hash=_digest(objective),
        initial_status=status,
        initial_state=_identifier(run.get("state"), "workflow state"),
        active_revision=INITIAL_GRAPH_REVISION,
        principal_type=principal_type,
        principal_id=principal_id,
        authority_json=_canonical_json(authority),
        authority_hash=_digest(authority),
        budget_json=_canonical_json(budgets),
        agent_profile_id=authority["agent_profile_id"],
        harness_id=str(authority["harness_id"]),
        policy_profile_id=str(authority["policy_profile_id"]),
        registry_version=str(authority["registry_version"]),
        registry_fingerprint=str(authority["registry_fingerprint"]),
        idempotency_key=_optional_identifier(run.get("idempotency_key")),
        request_hash=_digest(request_payload),
        trace_id=_identifier(run.get("trace_id"), "trace id"),
        source_created_at=_identifier(run.get("created_at"), "source created at"),
        planner_contract_version="agent-runtime-planner.v0",
        graph_hash=graph_hash,
        structural_digest=structural_digest,
        tasks=tasks,
        edges=edges,
        events=compiled_events,
    )


def _compile_task(action: Mapping[str, Any]) -> SequentialCompatibilityTask:
    action_id = _identifier(action.get("id"), "action id")
    inputs = _mapping(action.get("inputs"), "action inputs")
    input_hash = _digest(inputs)
    persisted_hash = _optional_identifier(action.get("inputs_hash"))
    if persisted_hash is not None and persisted_hash != input_hash:
        raise SequentialCompatibilityError(
            f"action {action_id} input hash does not match its payload"
        )
    return SequentialCompatibilityTask(
        task_id=action_id,
        source_action_id=action_id,
        task_key=f"agent-action:{action_id}",
        sequence=_positive_int(action.get("sequence"), "action sequence"),
        task_type=_identifier(action.get("capability_name"), "capability name"),
        capability_version=_optional_identifier(action.get("capability_version")),
        initial_status=_identifier(action.get("status"), "action status"),
        effect_class=_identifier(action.get("effect_class"), "effect class"),
        skill_id=_optional_identifier(action.get("skill_id")),
        skill_version=_optional_identifier(action.get("skill_version")),
        tool_id=_optional_identifier(action.get("tool_id")),
        tool_version=_optional_identifier(action.get("tool_version")),
        input_json=_canonical_json(inputs),
        input_hash=input_hash,
        result_schema_id=RESULT_SCHEMA_ID,
        result_schema_version=RESULT_SCHEMA_VERSION,
    )


def _compile_edge(
    workflow_id: str, from_task_id: str, to_task_id: str
) -> SequentialCompatibilityEdge:
    edge_key = _digest([workflow_id, INITIAL_GRAPH_REVISION, from_task_id, to_task_id])
    return SequentialCompatibilityEdge(
        edge_id=f"workflow-edge:{edge_key}",
        from_task_id=from_task_id,
        to_task_id=to_task_id,
    )


def _compile_event(
    workflow_id: str,
    principal_id: str,
    workflow_trace_id: str,
    event: Mapping[str, Any],
) -> SequentialCompatibilityEvent:
    source_event_id = _identifier(event.get("id"), "event id")
    action_id = _optional_identifier(event.get("action_id"))
    payload = {
        "source_event_id": source_event_id,
        "source_sequence": _non_negative_int(
            event.get("sequence", 0), "source event sequence"
        ),
        "source_status": _identifier(event.get("status"), "event status"),
        "capability_name": _optional_identifier(event.get("capability_name")),
        "capability_version": _optional_identifier(event.get("capability_version")),
        "tool_id": _optional_identifier(event.get("tool_id")),
        "skill_id": _optional_identifier(event.get("skill_id")),
        "effect_class": _optional_identifier(event.get("effect_class")),
        "anchors": _mapping(event.get("anchors"), "event anchors"),
        "note": str(event.get("note") or ""),
        "is_policy_event": bool(event.get("is_policy_event")),
    }
    return SequentialCompatibilityEvent(
        event_id=f"workflow-event:{source_event_id}",
        source_event_id=source_event_id,
        source_row_order=_non_negative_int(
            event.get("source_row_order"), "event row order"
        ),
        event_type=f"compatibility.agent.{_identifier(event.get('event_type'), 'event type')}",
        entity_type="task" if action_id else "workflow",
        entity_id=action_id or workflow_id,
        principal_id=_optional_identifier(event.get("principal_id")) or principal_id,
        causation_id=source_event_id,
        correlation_id=_optional_identifier(event.get("trace_id")) or workflow_trace_id,
        trace_id=_optional_identifier(event.get("trace_id")) or workflow_trace_id,
        payload_json=_canonical_json(payload),
        payload_hash=_digest(payload),
        occurred_at=_identifier(event.get("timestamp"), "event timestamp"),
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise SequentialCompatibilityError(f"{label} must be a canonical string")
    return value


def _optional_identifier(value: Any) -> str | None:
    if value is None:
        return None
    return _identifier(value, "optional identifier")


def _positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise SequentialCompatibilityError(f"{label} must be a positive integer")
    return value


def _non_negative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise SequentialCompatibilityError(f"{label} must be a non-negative integer")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise SequentialCompatibilityError(f"{label} must be an exact string-key map")
    try:
        return json.loads(_canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise SequentialCompatibilityError(f"{label} must be canonical JSON") from exc


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if type(value) is not list:
        raise SequentialCompatibilityError(f"{label} must be an exact list")
    parsed = tuple(_identifier(item, label) for item in value)
    if len(set(parsed)) != len(parsed):
        raise SequentialCompatibilityError(f"{label} must not contain duplicates")
    return parsed


__all__ = [
    "COMPATIBILITY_SCHEMA_VERSION",
    "INITIAL_GRAPH_REVISION",
    "SequentialCompatibilityEdge",
    "SequentialCompatibilityError",
    "SequentialCompatibilityEvent",
    "SequentialCompatibilityTask",
    "SequentialWorkflowCompatibility",
    "compile_sequential_workflow",
]
