"""Privileged sequential-runtime bridge into completion governance."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from application.ports.deps import AppDeps
from application.ports.workflow_outcomes import WorkflowOutcomeLedgerStore
from application.services.agent_runtime.runtime.payloads import hash_payload
from application.services.agent_runtime.registry import next_state_for_capability
from application.services.workflow_outcomes.contracts import (
    HostCompletionAuthority,
    OutcomeLedgerCommand,
    OutcomeLedgerConflict,
)
from application.services.workflow_outcomes.service import WorkflowOutcomeService
from domain.workflow.outcomes import (
    OUTCOME_SCHEMA_VERSION,
    AuthoritativeTaskDefinition,
    CompletionCriteria,
    ContractAuthority,
    CoverageClaim,
    CoverageStatus,
    EvidenceAvailability,
    EvidenceProvenance,
    EvidenceRecord,
    EvidenceRequirement,
    ReceiptStatus,
    ResultOutcome,
    ResultValidationAuthority,
    ResultValidationStatus,
    TaskResult,
    evidence_set_digest,
)


_POLICY_ID = "sequential-completion-policy:v1"
_RESULT_SCHEMA_ID = "agent-action-output"
_RESULT_SCHEMA_VERSION = "v1"
_RESULT_SCHEMA_HASH = hashlib.sha256(
    b"agent-action-output:v1:canonical-json-object"
).hexdigest()
PRODUCTION_HOST_AUTHORITY = HostCompletionAuthority(
    publishing_authority=ContractAuthority(
        principal_id="policy:completion-publisher",
        authority_source="host-policy",
        authority_version="v1",
    ),
    criteria_authority_hash=hashlib.sha256(_POLICY_ID.encode("utf-8")).hexdigest(),
    result_validation_authority=ResultValidationAuthority(
        principal_id="coordinator:sequential-runtime",
        authority_source="workflow-coordinator",
        authority_version="v1",
    ),
    evaluation_authority=ContractAuthority(
        principal_id="runtime:completion-evaluator",
        authority_source="workflow-runtime",
        authority_version="v1",
    ),
)


class SequentialCompletionCoordinator:
    """Host-only adapter for the current one-action-at-a-time runtime."""

    def __init__(self, *, deps: AppDeps, store: WorkflowOutcomeLedgerStore) -> None:
        self._deps = deps
        self._store = store
        self._service = WorkflowOutcomeService(
            store=store, host_authority=PRODUCTION_HOST_AUTHORITY
        )

    def synchronize_run(self, *, run_id: str, lock_token: str) -> dict[str, Any]:
        run, governed_actions, publication, now = self._activate(run_id)
        if publication is None:
            return run
        accepted = {
            record["result"].task_id
            for record in self._store.list_accepted_task_results(
                tenant_id=str(run["client_id"]),
                workflow_id=run_id,
                graph_revision=int(run["active_graph_revision"]),
            )
        }
        for action in governed_actions:
            if action["status"] == "executed" and action["id"] not in accepted:
                self._accept_action_result(
                    run=run,
                    action=action,
                    criteria_id=publication["criteria_id"],
                    criteria_hash=publication["artifact_digest"],
                    lock_token=lock_token,
                    now=now,
                )
        refreshed = self._deps.agent_runs.get_agent_run(run_id=run_id)
        if refreshed and refreshed.get("completion_projection_is_current") is True:
            return refreshed
        return self._evaluate(
            run=run,
            criteria_id=publication["criteria_id"],
            criteria_hash=publication["artifact_digest"],
            lock_token=lock_token,
            now=now,
            projected_run_state=self._projected_run_state(run_id, run),
        )

    def activate_run(self, *, run_id: str) -> dict[str, Any]:
        """Publish completion authority immediately after production planning."""

        run, _, _, _ = self._activate(run_id)
        return self._deps.agent_runs.get_agent_run(run_id=run_id) or run

    def get_completion_read_model(
        self, *, tenant_id: str, workflow_id: str
    ) -> dict[str, Any] | None:
        """Return the verified operator projection without granting authority."""

        return self._store.get_completion_operational_view(
            tenant_id=tenant_id, workflow_id=workflow_id
        )

    def repair_completion_read_model(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        principal_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Replay immutable lifecycle authority into its compatibility view."""

        command = {
            "command_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
            "principal_type": "human",
            "principal_id": principal_id,
            "authority_source": "agent-principal-token",
            "authority_version": "agent-principal-signing-secret:v1",
            "idempotency_key": idempotency_key,
        }
        result = self._store.repair_completion_projection(command=command)
        if result.get("outcome") == "conflict":
            raise OutcomeLedgerConflict(str(result.get("reason") or "repair failed"))
        view = self.get_completion_read_model(
            tenant_id=tenant_id, workflow_id=workflow_id
        )
        if view is None:
            raise OutcomeLedgerConflict("completion workflow does not exist")
        return {"command": result, "completion": view}

    def _activate(self, run_id: str):
        run = self._deps.agent_runs.get_agent_run(run_id=run_id)
        if not run:
            raise OutcomeLedgerConflict("completion workflow does not exist")
        actions = self._deps.agent_actions.list_agent_actions(
            agent_run_id=run_id, limit=500
        )
        governed_actions = [
            action for action in actions if str(action.get("status")) != "rejected"
        ]
        if not governed_actions:
            active = self._store.get_active_completion_contract(
                tenant_id=str(run["client_id"]), workflow_id=run_id
            )
            publication = (
                {
                    "criteria_id": active["criteria"].criteria_id,
                    "artifact_digest": active["criteria_digest"],
                }
                if active is not None
                else None
            )
            return run, governed_actions, publication, datetime.now(timezone.utc)
        now = datetime.now(timezone.utc)
        publication = self._publish_contract(run, governed_actions, now)
        for action in governed_actions:
            self._store.register_sequential_attempt_authority(
                tenant_id=str(run["client_id"]),
                workflow_id=run_id,
                action_id=str(action["id"]),
                created_at=_format_utc(now),
            )
        return run, governed_actions, publication, now

    def _publish_contract(self, run, actions, now):
        tenant_id = str(run["client_id"])
        workflow_id = str(run["id"])
        definitions = tuple(
            sorted(
                (
                    AuthoritativeTaskDefinition(
                        task_id=str(action["id"]),
                        task_input_hash=hash_payload(action.get("inputs") or {}),
                        result_schema_id=_RESULT_SCHEMA_ID,
                        result_schema_version=_RESULT_SCHEMA_VERSION,
                        result_schema_hash=_RESULT_SCHEMA_HASH,
                    )
                    for action in actions
                ),
                key=lambda item: item.task_id,
            )
        )
        membership_hash = _digest(
            [(item.task_id, item.task_input_hash) for item in definitions]
        )
        active = self._store.get_active_completion_contract(
            tenant_id=tenant_id, workflow_id=workflow_id
        )
        if active is not None and active["task_definitions"] == definitions:
            return {
                "outcome": "current",
                "artifact_digest": active["criteria_digest"],
                "criteria_id": active["criteria"].criteria_id,
            }
        criteria_id = f"sequential-criteria:{membership_hash}"
        objective = run.get("objective") or {}
        objective_id = str(objective.get("objective_id") or f"agent-run:{workflow_id}")
        criteria = CompletionCriteria(
            criteria_id=criteria_id,
            schema_version=OUTCOME_SCHEMA_VERSION,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=int(run["active_graph_revision"]),
            objective_id=objective_id,
            criteria_version=f"v1:{membership_hash}",
            publishing_authority=PRODUCTION_HOST_AUTHORITY.publishing_authority,
            authority_hash=PRODUCTION_HOST_AUTHORITY.criteria_authority_hash,
            required_task_ids=tuple(item.task_id for item in definitions),
            evidence_requirements=tuple(
                EvidenceRequirement(
                    requirement_id=f"action-output:{item.task_id}",
                    task_id=item.task_id,
                    min_items=1,
                    max_age_seconds=86400,
                    require_verified_receipt=False,
                    allowed_source_types=("sequential_runtime",),
                )
                for item in definitions
            ),
            created_at=now,
        )
        command = _command(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            purpose=f"publish:{membership_hash}",
            authority=PRODUCTION_HOST_AUTHORITY.publishing_authority,
            now=now,
        )
        write = self._service.publish_completion_contract(
            command=command, criteria=criteria, task_definitions=definitions
        )
        if write["outcome"] not in {"applied", "replayed"}:
            raise OutcomeLedgerConflict(str(write.get("reason") or "publish failed"))
        write["criteria_id"] = criteria_id
        return write

    def _accept_action_result(
        self, *, run, action, criteria_id, criteria_hash, lock_token, now
    ):
        tenant_id = str(run["client_id"])
        workflow_id = str(run["id"])
        action_id = str(action["id"])
        attempt = f"action-attempt:{action_id}:{int(action.get('retry_count') or 0)}"
        output_hash = hash_payload(action.get("outputs") or {})
        evidence = EvidenceRecord(
            evidence_id=f"runtime-evidence:{action_id}:{output_hash}",
            schema_version=OUTCOME_SCHEMA_VERSION,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=int(run["active_graph_revision"]),
            task_id=action_id,
            attempt_id=attempt,
            action_id=action_id,
            availability=EvidenceAvailability.AVAILABLE,
            content_hash=output_hash,
            provenance=EvidenceProvenance(
                source_type="sequential_runtime",
                source_id=action_id,
                source_version=str(action.get("capability_version") or "v1"),
                source_contract_hash=str(
                    action.get("registry_fingerprint") or _RESULT_SCHEMA_HASH
                ),
                producer_principal_id=str(run["principal_id"]),
                capability_id=str(action["capability_name"]),
                tool_id=str(action.get("tool_id") or action["capability_name"]),
            ),
            receipt_status=ReceiptStatus.NOT_REQUIRED,
            receipt_id=None,
            observed_at=now,
            valid_until=now + timedelta(days=365),
            recorded_at=now,
            failure_code=None,
        )
        evidence_write = self._service.record_evidence(
            command=_command(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                purpose=f"evidence:{evidence.evidence_id}",
                authority=ContractAuthority(
                    principal_id=str(run["principal_id"]),
                    authority_source="sequential-runtime",
                    authority_version="v1",
                ),
                now=now,
            ),
            evidence=evidence,
        )
        if evidence_write["outcome"] not in {"applied", "replayed"}:
            raise OutcomeLedgerConflict(str(evidence_write.get("reason")))
        pending = TaskResult(
            result_id=f"runtime-result:{action_id}:{output_hash}",
            schema_version=OUTCOME_SCHEMA_VERSION,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=int(run["active_graph_revision"]),
            task_id=action_id,
            attempt_id=attempt,
            assignment_id=None,
            task_input_hash=hash_payload(action.get("inputs") or {}),
            result_schema_id=_RESULT_SCHEMA_ID,
            result_schema_version=_RESULT_SCHEMA_VERSION,
            result_schema_hash=_RESULT_SCHEMA_HASH,
            producer_principal_id=str(run["principal_id"]),
            outcome=ResultOutcome.SUCCEEDED,
            payload_hash=output_hash,
            evidence_ids=(evidence.evidence_id,),
            evidence_digest=evidence_set_digest((evidence,)),
            coverage=(
                CoverageClaim(
                    requirement_id=f"action-output:{action_id}",
                    status=CoverageStatus.SATISFIED,
                    evidence_ids=(evidence.evidence_id,),
                ),
            ),
            validation_status=ResultValidationStatus.PENDING,
            validation_authority=None,
            validated_at=None,
            created_at=now,
            error_code=None,
        )
        write = self._service.validate_submitted_result(
            command=_command(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                purpose=f"validate:{pending.result_id}",
                authority=PRODUCTION_HOST_AUTHORITY.result_validation_authority,
                now=now,
            ),
            submitted_result=pending,
            criteria_id=criteria_id,
            criteria_hash=criteria_hash,
            validation_status=ResultValidationStatus.ACCEPTED,
            lock_token=lock_token,
        )
        if write["outcome"] not in {"applied", "replayed"}:
            raise OutcomeLedgerConflict(str(write.get("reason")))

    def _evaluate(
        self,
        *,
        run,
        criteria_id,
        criteria_hash,
        lock_token,
        now,
        projected_run_state,
    ):
        tenant_id = str(run["client_id"])
        workflow_id = str(run["id"])
        publication = self._store.get_completion_contract(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            criteria_id=criteria_id,
            criteria_hash=criteria_hash,
        )
        if publication is None:
            raise OutcomeLedgerConflict("active completion contract is unavailable")
        result_ids = sorted(
            item["result"].result_id
            for item in self._store.list_accepted_task_results(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                graph_revision=int(run["active_graph_revision"]),
            )
            if item["result"].task_id in publication["criteria"].required_task_ids
        )
        snapshot_key = _digest(result_ids)
        snapshot_id = f"sequential-snapshot:{snapshot_key}"
        snapshot_write = self._service.issue_authority_snapshot(
            command=_command(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                purpose=f"snapshot:{snapshot_key}",
                authority=PRODUCTION_HOST_AUTHORITY.evaluation_authority,
                now=now,
            ),
            snapshot_id=snapshot_id,
            criteria_id=publication["criteria"].criteria_id,
            criteria_hash=criteria_hash,
        )
        if snapshot_write["outcome"] not in {"applied", "replayed"}:
            raise OutcomeLedgerConflict(str(snapshot_write.get("reason")))
        fence = self._store.get_completion_projection_fence(
            tenant_id=tenant_id, workflow_id=workflow_id
        )
        decision_key = _digest(
            [snapshot_key, fence.action_projection_digest if fence else "missing"]
        )
        write = self._service.evaluate_and_commit_lifecycle(
            command=_command(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                purpose=f"decision:{decision_key}",
                authority=PRODUCTION_HOST_AUTHORITY.evaluation_authority,
                now=now,
            ),
            snapshot_id=snapshot_id,
            decision_id=f"sequential-decision:{decision_key}",
            evaluated_at=now,
            lock_token=lock_token,
            projected_run_state=projected_run_state,
        )
        if write["outcome"] not in {"applied", "replayed"}:
            raise OutcomeLedgerConflict(str(write.get("reason")))
        return self._deps.agent_runs.get_agent_run(run_id=workflow_id) or run

    def _projected_run_state(self, run_id: str, run: dict[str, Any]) -> str:
        actions = self._deps.agent_actions.list_agent_actions(
            agent_run_id=run_id, limit=500
        )
        executed = [
            action for action in actions if str(action.get("status")) == "executed"
        ]
        if not executed:
            return str(run["state"])
        latest = max(
            executed,
            key=lambda action: (int(action.get("sequence") or 0), str(action["id"])),
        )
        return next_state_for_capability(
            str(latest.get("capability_name") or "")
        ) or str(run["state"])


def _command(*, workflow_id, tenant_id, purpose, authority, now):
    identity = hashlib.sha256(f"{workflow_id}:{purpose}".encode("utf-8")).hexdigest()
    return OutcomeLedgerCommand(
        command_id=f"completion-command:{identity}",
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        principal_id=authority.principal_id,
        authority_source=authority.authority_source,
        authority_version=authority.authority_version,
        idempotency_key=f"completion:{purpose}",
        issued_at=now,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = ["PRODUCTION_HOST_AUTHORITY", "SequentialCompletionCoordinator"]
