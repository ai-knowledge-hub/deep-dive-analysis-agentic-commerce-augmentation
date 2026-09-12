"""Independent fixtures for durable workflow outcome ledger tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from application.services.workflow_outcomes import (
    HostCompletionAuthority,
    OutcomeLedgerCommand,
    WorkflowOutcomeService,
)
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
from infrastructure.db.workflow.outcome_ledger import SQLiteWorkflowOutcomeLedger


NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HOST_PUBLISHER = ContractAuthority(
    principal_id="policy:completion-publisher",
    authority_source="host-policy",
    authority_version="v1",
)
HOST_COORDINATOR = ResultValidationAuthority(
    principal_id="coordinator:workflow",
    authority_source="workflow-coordinator",
    authority_version="v1",
)
HOST_EVALUATOR = ContractAuthority(
    principal_id="runtime:completion-evaluator",
    authority_source="workflow-runtime",
    authority_version="v1",
)
HOST_AUTHORITY = HostCompletionAuthority(
    publishing_authority=HOST_PUBLISHER,
    criteria_authority_hash=HASH_A,
    result_validation_authority=HOST_COORDINATOR,
    evaluation_authority=HOST_EVALUATOR,
)


class OutcomeTestDeps:
    """Test-only composition keeping privileged writes out of application deps."""

    def __init__(self, app_deps) -> None:
        self.app_deps = app_deps
        self.workflow_outcomes = SQLiteWorkflowOutcomeLedger(
            host_authority=HOST_AUTHORITY
        )

    def __getattr__(self, name: str):
        return getattr(self.app_deps, name)


def with_outcome_ledger(app_deps) -> OutcomeTestDeps:
    return OutcomeTestDeps(app_deps)


def create_workflow(deps, *, tenant_id: str = "tenant-a") -> str:
    deps.clients.create_client(client_id=tenant_id, name=tenant_id)
    run = deps.agent_runs.create_agent_run(
        client_id=tenant_id,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"objective_id": "objective-a"},
        allowed_capabilities=[],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=False,
        run_mode="observe",
        state="planned",
        status="planned",
        principal_type="internal_agent",
        principal_id="internal-agent:planner",
    )
    return run["id"]


def service(deps) -> WorkflowOutcomeService:
    return WorkflowOutcomeService(
        store=deps.workflow_outcomes,
        host_authority=HOST_AUTHORITY,
    )


def command(
    workflow_id: str,
    *,
    command_id: str,
    idempotency_key: str | None = None,
    tenant_id: str = "tenant-a",
    principal_id: str = "runtime:completion-evaluator",
    authority_source: str = "workflow-runtime",
    authority_version: str = "v1",
    issued_at: datetime | None = None,
) -> OutcomeLedgerCommand:
    return OutcomeLedgerCommand(
        command_id=command_id,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        principal_id=principal_id,
        authority_source=authority_source,
        authority_version=authority_version,
        idempotency_key=idempotency_key or f"idem:{command_id}",
        issued_at=issued_at or NOW + timedelta(minutes=30),
    )


def publisher_command(
    workflow_id: str, command_id: str, *, issued_at: datetime | None = None
) -> OutcomeLedgerCommand:
    return command(
        workflow_id,
        command_id=command_id,
        principal_id=HOST_PUBLISHER.principal_id,
        authority_source=HOST_PUBLISHER.authority_source,
        authority_version=HOST_PUBLISHER.authority_version,
        issued_at=issued_at,
    )


def coordinator_command(
    workflow_id: str, command_id: str, *, issued_at: datetime | None = None
) -> OutcomeLedgerCommand:
    return command(
        workflow_id,
        command_id=command_id,
        principal_id=HOST_COORDINATOR.principal_id,
        authority_source=HOST_COORDINATOR.authority_source,
        authority_version=HOST_COORDINATOR.authority_version,
        issued_at=issued_at,
    )


def evidence_command(
    workflow_id: str, command_id: str, *, issued_at: datetime | None = None
) -> OutcomeLedgerCommand:
    return command(
        workflow_id,
        command_id=command_id,
        principal_id="internal-agent:observer",
        authority_source="runtime-claims",
        authority_version="v1",
        issued_at=issued_at,
    )


def criteria(workflow_id: str, **overrides: object) -> CompletionCriteria:
    values: dict[str, object] = {
        "criteria_id": "criteria-a",
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "tenant_id": "tenant-a",
        "workflow_id": workflow_id,
        "graph_revision": 1,
        "objective_id": "objective-a",
        "criteria_version": "v1",
        "publishing_authority": HOST_PUBLISHER,
        "authority_hash": HASH_A,
        "required_task_ids": ("task-a",),
        "evidence_requirements": (
            EvidenceRequirement(
                requirement_id="requirement-a",
                task_id="task-a",
                min_items=1,
                max_age_seconds=3600,
                require_verified_receipt=True,
                allowed_source_types=("provider",),
            ),
        ),
        "created_at": NOW,
    }
    values.update(overrides)
    return CompletionCriteria(**values)  # type: ignore[arg-type]


def task_definitions() -> tuple[AuthoritativeTaskDefinition, ...]:
    return (
        AuthoritativeTaskDefinition(
            task_id="task-a",
            task_input_hash=HASH_B,
            result_schema_id="validation-result",
            result_schema_version="v1",
            result_schema_hash=HASH_C,
        ),
    )


def evidence(workflow_id: str, **overrides: object) -> EvidenceRecord:
    values: dict[str, object] = {
        "evidence_id": "evidence-a",
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "tenant_id": "tenant-a",
        "workflow_id": workflow_id,
        "graph_revision": 1,
        "task_id": "task-a",
        "attempt_id": "attempt-a1",
        "action_id": None,
        "availability": EvidenceAvailability.AVAILABLE,
        "content_hash": HASH_A,
        "provenance": EvidenceProvenance(
            source_type="provider",
            source_id="provider-job-a",
            source_version="v1",
            source_contract_hash=HASH_B,
            producer_principal_id="internal-agent:observer",
            capability_id="validation.observe",
            tool_id="validation.read_result",
        ),
        "receipt_status": ReceiptStatus.VERIFIED,
        "receipt_id": "provider-receipt-a",
        "observed_at": NOW + timedelta(seconds=1),
        "valid_until": NOW + timedelta(hours=1),
        "recorded_at": NOW + timedelta(seconds=2),
        "failure_code": None,
    }
    values.update(overrides)
    return EvidenceRecord(**values)  # type: ignore[arg-type]


def result(
    workflow_id: str,
    evidence_values: tuple[EvidenceRecord, ...],
    **overrides: object,
) -> TaskResult:
    evidence_ids = tuple(item.evidence_id for item in evidence_values)
    values: dict[str, object] = {
        "result_id": "result-a",
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "tenant_id": "tenant-a",
        "workflow_id": workflow_id,
        "graph_revision": 1,
        "task_id": "task-a",
        "attempt_id": "attempt-a1",
        "assignment_id": None,
        "task_input_hash": HASH_B,
        "result_schema_id": "validation-result",
        "result_schema_version": "v1",
        "result_schema_hash": HASH_C,
        "producer_principal_id": "internal-agent:validator",
        "outcome": ResultOutcome.SUCCEEDED,
        "payload_hash": HASH_B,
        "evidence_ids": evidence_ids,
        "evidence_digest": evidence_set_digest(evidence_values),
        "coverage": (
            CoverageClaim(
                requirement_id="requirement-a",
                status=CoverageStatus.SATISFIED,
                evidence_ids=evidence_ids,
            ),
        ),
        "validation_status": ResultValidationStatus.ACCEPTED,
        "validation_authority": HOST_COORDINATOR,
        "validated_at": NOW + timedelta(seconds=4),
        "created_at": NOW + timedelta(seconds=3),
        "error_code": None,
    }
    values.update(overrides)
    return TaskResult(**values)  # type: ignore[arg-type]


__all__ = [
    "HASH_A",
    "HOST_AUTHORITY",
    "HOST_COORDINATOR",
    "HOST_EVALUATOR",
    "HOST_PUBLISHER",
    "NOW",
    "command",
    "coordinator_command",
    "create_workflow",
    "criteria",
    "evidence",
    "evidence_command",
    "publisher_command",
    "result",
    "service",
    "task_definitions",
    "with_outcome_ledger",
]
