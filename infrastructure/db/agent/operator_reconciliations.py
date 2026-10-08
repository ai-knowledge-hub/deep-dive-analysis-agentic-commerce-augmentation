"""One owned transaction for evidence recording and an immutable human receipt."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from domain.workflow.operator_commands import (
    OperatorCommandConflictError,
    RECONCILIATION_RECEIPT_CONTRACT,
    canonical_digest,
    proposal_is_expired,
    validate_operator_proposal,
)
from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.transactions import JoinedTransaction
from infrastructure.db.agent.operator_command_integrity import (
    _insert_event,
    _json,
    _require_active_principal,
    _require_event_head,
    _require_proposal_row_matches,
    _require_run_fence,
    _require_snapshot_digest,
)


def commit_reconciliation(
    *,
    proposal: dict[str, Any],
    principal_id: str,
    require_access: Callable,
    confirmation_state: Callable,
    reconcile: Callable,
) -> dict[str, Any]:
    validate_operator_proposal(proposal)
    if (
        proposal["command_type"] != "reconcile_effect"
        or proposal["principal_id"] != principal_id
    ):
        raise OperatorCommandConflictError(
            "proposal_principal_mismatch",
            "Expected the confirming human's exact reconciliation proposal.",
        )
    conn = get_connection()
    transaction = JoinedTransaction(conn, "operator_reconciliation")
    try:
        row = conn.execute(
            "SELECT * FROM operator_reconciliation_proposals WHERE proposal_id = ? AND tenant_id = ? AND workflow_id = ?",
            (proposal["proposal_id"], proposal["tenant_id"], proposal["run_id"]),
        ).fetchone()
        if row is None:
            raise OperatorCommandConflictError(
                "proposal_not_found", "The proposal is unavailable."
            )
        stored = json.loads(row["proposal_json"])
        validate_operator_proposal(stored)
        _require_proposal_row_matches(row, stored)
        if stored != proposal:
            raise OperatorCommandConflictError(
                "proposal_changed", "The durable proposal changed."
            )
        require_access()
        _require_active_principal(conn, proposal)
        membership = conn.execute(
            "SELECT 1 FROM client_users WHERE client_id = ? AND user_id = ? AND role IN ('owner','admin','operator')",
            (proposal["tenant_id"], principal_id.removeprefix("human:")),
        ).fetchone()
        if membership is None:
            raise OperatorCommandConflictError(
                "access_changed", "Current operator access is required."
            )
        existing = conn.execute(
            "SELECT * FROM operator_reconciliation_receipts WHERE proposal_id = ?",
            (proposal["proposal_id"],),
        ).fetchone()
        if existing:
            receipt = verify_reconciliation_receipt(existing)
            transaction.commit()
            return {**receipt, "replayed": True}
        _require_fresh(proposal)
        current = confirmation_state()
        _require_snapshot_digest(proposal, current.get("snapshot_digest"))
        preflight = current.get("preflight")
        if (
            not isinstance(preflight, dict)
            or not preflight.get("allowed")
            or canonical_digest(preflight) != proposal["preflight"]["digest"]
        ):
            raise OperatorCommandConflictError(
                "evidence_changed",
                "Reconciliation evidence or admission changed; refresh the exact proposal.",
            )
        run_row = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ? AND client_id = ?",
            (proposal["run_id"], proposal["tenant_id"]),
        ).fetchone()
        if run_row is None:
            raise OperatorCommandConflictError(
                "run_not_found", "The scoped run is unavailable."
            )
        _require_run_fence(run_row, proposal["source"])
        _require_event_head(conn, proposal)
        proof = proposal["parameters"]["reconciliation"]
        winner = conn.execute(
            "SELECT 1 FROM operator_reconciliation_receipts WHERE effect_execution_id = ?",
            (proof["effect_execution_id"],),
        ).fetchone()
        if winner:
            raise OperatorCommandConflictError(
                "effect_already_recorded",
                "This effect already has a human reconciliation receipt; reload command history.",
            )
        _require_fresh(proposal)
        result = reconcile()
        if not conn.in_transaction:
            raise RuntimeError("Recovery escaped the confirmation transaction")
        execution, action = result["effect_execution"], result["action"]
        if (
            execution["execution_id"] != proof["effect_execution_id"]
            or execution["status"] != "succeeded"
            or execution["receipt_id"] != proof["receipt_id"]
            or execution["outputs_hash"] != proof["outputs_hash"]
            or action["status"] != "executed"
            or action.get("outputs_hash") != proof["outputs_hash"]
        ):
            raise OperatorCommandConflictError(
                "outcome_conflict",
                "Recorded effect/action outcome differs from verified evidence.",
            )
        resulting_run = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ? AND client_id = ?",
            (proposal["run_id"], proposal["tenant_id"]),
        ).fetchone()
        receipt_id, command_id, lifecycle_id = (str(uuid.uuid4()) for _ in range(3))
        core = {
            "contract": RECONCILIATION_RECEIPT_CONTRACT,
            "receipt_id": receipt_id,
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "tenant_id": proposal["tenant_id"],
            "principal_id": principal_id,
            "run_id": proposal["run_id"],
            "command_type": "reconcile_effect",
            "idempotency_key": proposal["idempotency_key"],
            "request_hash": canonical_digest(
                {"proposal_digest": proposal["proposal_digest"]}
            ),
            "outcome": "succeeded",
            "action_id": action["id"],
            "action_status": action["status"],
            "reconciliation": proof,
            "effect_execution_id": execution["execution_id"],
            "prior_run_status": run_row["status"],
            "prior_run_state": run_row["state"],
            "resulting_run_status": resulting_run["status"],
            "resulting_run_state": resulting_run["state"],
            "control_state_preserved": bool(preflight["preserve_control_state"]),
            "active_graph_revision": resulting_run["active_graph_revision"],
            "run_mode": resulting_run["run_mode"],
            "event_ids": {
                "command": command_id,
                "lifecycle": lifecycle_id,
                "stopping_condition": None,
            },
            "acknowledgement": "existing_effect_outcome_recorded",
            "propagation_state": "runtime_propagation_not_certified",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        anchors = {
            "proposal_contract": proposal["contract"],
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "receipt_id": receipt_id,
            "effect_execution_id": execution["execution_id"],
            "evidence_digest": proof["evidence_digest"],
            "origin": "operator_conversation",
        }
        for event_id, event_type, status in (
            (command_id, "operator_command_reconcile_effect", "completed"),
            (lifecycle_id, "action_effect_reconciled", "executed"),
        ):
            _insert_event(
                conn,
                event_id=event_id,
                run_row=run_row,
                action=action,
                event_type=event_type,
                status=status,
                principal_id=principal_id,
                note="Human confirmed recording an existing verified effect outcome; no capability invoked.",
                anchors=anchors,
            )
        receipt = {**core, "receipt_digest": canonical_digest(core)}
        columns = [
            "receipt_id",
            "proposal_id",
            "tenant_id",
            "workflow_id",
            "principal_id",
            "command_type",
            "proposal_digest",
            "idempotency_key",
            "request_hash",
            "outcome",
            "prior_run_status",
            "resulting_run_status",
            "resulting_run_state",
            "active_graph_revision",
            "command_event_id",
            "lifecycle_event_id",
            "stopping_event_id",
            "acknowledgement",
            "propagation_state",
            "receipt_json",
            "receipt_digest",
            "completed_at",
        ]
        values = {
            **receipt,
            "workflow_id": proposal["run_id"],
            "command_event_id": command_id,
            "lifecycle_event_id": lifecycle_id,
            "stopping_event_id": None,
            "receipt_json": _json(receipt),
        }
        conn.execute(
            f"INSERT INTO operator_reconciliation_receipts ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            [values[c] for c in columns],
        )
        transaction.commit()
        return {**receipt, "replayed": False}
    except Exception:
        transaction.rollback()
        raise


def _require_fresh(proposal):
    if proposal_is_expired(proposal):
        raise OperatorCommandConflictError(
            "proposal_expired",
            "The reconciliation proposal expired; request a fresh review.",
        )


def verify_reconciliation_receipt(row) -> dict[str, Any]:
    receipt = json.loads(row["receipt_json"])
    digest = receipt.pop("receipt_digest")
    expected = set(
        """contract receipt_id proposal_id proposal_digest tenant_id
        principal_id run_id command_type idempotency_key request_hash outcome
        action_id action_status reconciliation effect_execution_id prior_run_status
        prior_run_state resulting_run_status resulting_run_state control_state_preserved
        active_graph_revision run_mode event_ids acknowledgement propagation_state
        completed_at""".split()
    )
    if set(receipt) != expected:
        raise ValueError("reconciliation receipt shape changed")
    if canonical_digest(receipt) != digest or digest != row["receipt_digest"]:
        raise ValueError("reconciliation receipt digest changed")
    for key in (
        "receipt_id",
        "proposal_id",
        "proposal_digest",
        "tenant_id",
        "principal_id",
        "command_type",
        "idempotency_key",
        "request_hash",
        "outcome",
        "prior_run_status",
        "resulting_run_status",
        "resulting_run_state",
        "active_graph_revision",
        "acknowledgement",
        "propagation_state",
        "completed_at",
    ):
        if receipt.get(key) != row[key]:
            raise ValueError("reconciliation receipt columns changed")
    if (
        receipt["contract"] != RECONCILIATION_RECEIPT_CONTRACT
        or receipt["run_id"] != row["workflow_id"]
        or receipt["outcome"] != "succeeded"
        or receipt["action_status"] != "executed"
    ):
        raise ValueError("reconciliation receipt outcome changed")
    conn = get_connection()
    proposal_row = conn.execute(
        "SELECT * FROM operator_reconciliation_proposals WHERE proposal_id = ?",
        (receipt["proposal_id"],),
    ).fetchone()
    if proposal_row is None:
        raise ValueError("reconciliation proposal missing")
    proposal = json.loads(proposal_row["proposal_json"])
    validate_operator_proposal(proposal)
    _require_proposal_row_matches(proposal_row, proposal)
    if (
        any(
            receipt[k] != proposal[k]
            for k in (
                "run_id",
                "tenant_id",
                "principal_id",
                "proposal_digest",
                "idempotency_key",
            )
        )
        or receipt["reconciliation"] != proposal["parameters"]["reconciliation"]
        or receipt["action_id"] != proposal["parameters"]["action_id"]
        or receipt["effect_execution_id"]
        != proposal["parameters"]["effect_execution_id"]
    ):
        raise ValueError("reconciliation receipt scope/evidence changed")
    _require_receipt_source(receipt, proposal, row)
    for key, kind, status in (
        ("command", "operator_command_reconcile_effect", "completed"),
        ("lifecycle", "action_effect_reconciled", "executed"),
    ):
        if receipt["event_ids"][key] != row[f"{key}_event_id"]:
            raise ValueError("reconciliation event identity changed")
        event = conn.execute(
            "SELECT * FROM agent_events WHERE id = ?", (receipt["event_ids"][key],)
        ).fetchone()
        if (
            event is None
            or event["agent_run_id"] != receipt["run_id"]
            or event["action_id"] != receipt["action_id"]
            or event["principal_id"] != receipt["principal_id"]
            or event["principal_type"] != "human"
            or event["event_type"] != kind
            or event["status"] != status
        ):
            raise ValueError("reconciliation audit changed")
        anchors = json.loads(event["anchors_json"])
        if (
            any(
                anchors.get(k) != receipt[k]
                for k in (
                    "receipt_id",
                    "proposal_id",
                    "proposal_digest",
                    "effect_execution_id",
                )
            )
            or anchors.get("evidence_digest")
            != receipt["reconciliation"]["evidence_digest"]
        ):
            raise ValueError("reconciliation audit evidence changed")
    return {**receipt, "receipt_digest": digest}


def _require_receipt_source(receipt, proposal, row):
    source = proposal["source"]
    preserved = proposal["preflight"]["result"]["preserve_control_state"]
    if (
        receipt["request_hash"]
        != canonical_digest({"proposal_digest": proposal["proposal_digest"]})
        or receipt["prior_run_status"] != source["run_status"]
        or receipt["prior_run_state"] != source["run_state"]
        or receipt["active_graph_revision"] != source["active_graph_revision"]
        or receipt["run_mode"] != source["run_mode"]
        or type(receipt["control_state_preserved"]) is not bool
        or receipt["control_state_preserved"] != preserved
        or receipt["acknowledgement"] != "existing_effect_outcome_recorded"
        or receipt["propagation_state"] != "runtime_propagation_not_certified"
        or set(receipt["event_ids"]) != {"command", "lifecycle", "stopping_condition"}
        or receipt["event_ids"]["stopping_condition"] is not None
        or row["stopping_event_id"] is not None
        or (
            preserved
            and (
                receipt["resulting_run_status"] != source["run_status"]
                or receipt["resulting_run_state"] != source["run_state"]
            )
        )
    ):
        raise ValueError("reconciliation receipt control/source changed")
