from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    skill_id_for_tool_id,
    tool_effect_class,
)


def record_run_event(
    *,
    deps: AppDeps,
    run_id: str,
    sequence: int,
    event_type: str,
    status: str,
    note: Optional[str],
) -> None:
    run = deps.agent_runs.get_agent_run(run_id=run_id) or {}
    deps.agent_events.create_agent_event(
        agent_run_id=run_id,
        action_id=None,
        sequence=sequence,
        event_type=event_type,
        status=status,
        capability_name=None,
        capability_version=None,
        principal_type=run.get("principal_type"),
        principal_id=run.get("principal_id"),
        trace_id=run.get("trace_id"),
        note=note,
        is_policy_event=False,
        anchors={},
    )


def record_action_event(
    *,
    deps: AppDeps,
    run_id: str,
    action: Dict[str, Any],
    event_type: str,
    status: str,
    note: Optional[str],
    is_policy_event: bool = False,
) -> None:
    run = deps.agent_runs.get_agent_run(run_id=run_id) or {}
    outputs = action.get("outputs") or {}
    receipt = outputs.get("receipt") if isinstance(outputs, dict) else None
    metric_id = None
    if isinstance(outputs, dict):
        metric_id = (
            outputs.get("metric_id")
            or outputs.get("new_metric_id")
            or outputs.get("source_metric_id")
        )
    deps.agent_events.create_agent_event(
        agent_run_id=run_id,
        action_id=str(action.get("id") or "") or None,
        sequence=int(action.get("sequence") or 0),
        event_type=event_type,
        status=status,
        capability_name=str(action.get("capability_name") or "") or None,
        capability_version=str(action.get("capability_version") or "") or None,
        principal_type=run.get("principal_type"),
        principal_id=run.get("principal_id"),
        tool_id=action.get("tool_id")
        or capability_to_tool_id(str(action.get("capability_name") or "")),
        skill_id=action.get("skill_id")
        or skill_id_for_tool_id(
            action.get("tool_id")
            or capability_to_tool_id(str(action.get("capability_name") or ""))
        ),
        effect_class=action.get("effect_class")
        or tool_effect_class(
            action.get("tool_id")
            or capability_to_tool_id(str(action.get("capability_name") or ""))
        ),
        trace_id=run.get("trace_id"),
        note=str(note) if note is not None else None,
        is_policy_event=is_policy_event,
        anchors={
            "experiment_id": run.get("experiment_id"),
            "variant_id": action.get("variant_id"),
            "validation_job_id": action.get("validation_job_id"),
            "hypothesis_id": action.get("hypothesis_id"),
            "snapshot_version": action.get("snapshot_version"),
            "metric_id": metric_id,
            "inputs_hash": action.get("inputs_hash"),
            "outputs_hash": action.get("outputs_hash"),
            "registry_version": action.get("registry_version"),
            "registry_fingerprint": action.get("registry_fingerprint"),
            "tool_version": action.get("tool_version"),
            "skill_version": action.get("skill_version"),
            "receipt_id": action.get("receipt_id")
            or (outputs.get("receipt_id") if isinstance(outputs, dict) else None),
            "adapter": outputs.get("adapter") if isinstance(outputs, dict) else None,
            "receipt": receipt if isinstance(receipt, dict) else None,
        },
    )
