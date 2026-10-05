"""Atomic conversation receipts composed with the existing approval ledger."""

import json
import sqlite3
import uuid
from collections.abc import Callable
from typing import Any

from domain.workflow.operator_commands import (
    OperatorCommandConflictError,
    REVIEW_RECEIPT_CONTRACT,
    canonical_digest,
    proposal_is_expired,
    validate_operator_proposal,
)
from infrastructure.db.core.connection import get_connection
from infrastructure.db.agent.operator_command_integrity import (
    _insert_event,
    _json,
    _require_active_principal,
    _require_event_head,
    _require_proposal_row_matches,
    _require_run_fence,
    _require_snapshot_digest,
)


def commit_review(
    *,
    proposal: dict[str, Any],
    principal_id: str,
    confirmation_state: Callable[[], dict[str, Any]],
    commit_decision: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    validate_operator_proposal(proposal)
    if (
        proposal["command_type"] not in {"approve", "reject"}
        or principal_id != proposal["principal_id"]
    ):
        raise OperatorCommandConflictError(
            "proposal_principal_mismatch",
            "Only the exact proposing human may confirm this action review.",
        )
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM operator_action_review_proposals WHERE proposal_id = ? AND tenant_id = ? AND workflow_id = ?",
            (proposal["proposal_id"], proposal["tenant_id"], proposal["run_id"]),
        ).fetchone()
        if row is None:
            raise OperatorCommandConflictError(
                "proposal_not_found", "The action review proposal is unavailable."
            )
        stored = json.loads(row["proposal_json"])
        validate_operator_proposal(stored)
        _require_proposal_row_matches(row, stored)
        if stored != proposal:
            raise OperatorCommandConflictError(
                "proposal_changed", "The exact action review proposal changed."
            )
        # Access is checked again even for replay, before new decision eligibility.
        _require_active_principal(conn, proposal)
        membership = conn.execute(
            "SELECT 1 FROM client_users WHERE client_id = ? AND user_id = ? AND lower(trim(role)) IN ('owner', 'admin', 'operator')",
            (proposal["tenant_id"], principal_id.removeprefix("human:")),
        ).fetchone()
        if membership is None:
            raise OperatorCommandConflictError(
                "membership_inactive", "The operator no longer has decision authority."
            )
        replay = conn.execute(
            "SELECT * FROM operator_action_review_receipts WHERE proposal_id = ?",
            (proposal["proposal_id"],),
        ).fetchone()
        if replay is not None:
            receipt = verify_review_receipt(replay)
            conn.commit()
            return {**receipt, "replayed": True}
        if proposal_is_expired(proposal):
            raise OperatorCommandConflictError(
                "proposal_expired",
                "The action review expired. Review a fresh proposal.",
            )
        current = confirmation_state()
        _require_snapshot_digest(proposal, current.get("snapshot_digest"))
        if (
            current.get("preflight", {}).get("allowed") is not True
            or canonical_digest(current.get("preflight"))
            != proposal["preflight"]["digest"]
        ):
            raise OperatorCommandConflictError(
                "preflight_changed", "The action review conditions changed."
            )
        run = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ? AND client_id = ?",
            (proposal["run_id"], proposal["tenant_id"]),
        ).fetchone()
        if run is None:
            raise OperatorCommandConflictError(
                "run_not_found", "The run is unavailable."
            )
        _require_run_fence(run, proposal["source"])
        _require_event_head(conn, proposal)
        if proposal_is_expired(proposal):
            raise OperatorCommandConflictError(
                "proposal_expired", "The action review expired during confirmation."
            )
        decision = commit_decision()
        # The approval adapter must leave ownership of the outer transaction here.
        if not conn.in_transaction:
            raise RuntimeError("approval decision escaped the conversation transaction")
        approval, command = decision["approval"], decision["command"]
        action_id = proposal["parameters"]["action_id"]
        if (
            command["action_id"] != action_id
            or command["principal_id"] != principal_id
            or command["command_type"] != proposal["command_type"]
            or command["idempotency_key"] != proposal["idempotency_key"]
        ):
            raise RuntimeError(
                "approval command does not match the conversational proposal"
            )
        lifecycle = conn.execute(
            "SELECT id FROM agent_events WHERE agent_run_id = ? AND action_id = ? AND json_extract(anchors_json, '$.approval_command_id') = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (proposal["run_id"], action_id, command["command_id"]),
        ).fetchone()
        if lifecycle is None:
            raise RuntimeError("approval decision has no durable audit")
        receipt_id, event_id = str(uuid.uuid4()), str(uuid.uuid4())
        _insert_event(
            conn,
            event_id=event_id,
            run_row=run,
            event_type=f"operator_command_{proposal['command_type']}",
            status="completed",
            principal_id=principal_id,
            note="Operator confirmed an exact action review.",
            anchors={
                "proposal_contract": proposal["contract"],
                "proposal_id": proposal["proposal_id"],
                "proposal_digest": proposal["proposal_digest"],
                "receipt_id": receipt_id,
                "action_id": action_id,
                "approval_command_id": command["command_id"],
                "approval_id": approval["approval_id"],
                "approval_envelope_digest": approval["envelope_digest"],
            },
        )
        core = {
            "contract": REVIEW_RECEIPT_CONTRACT,
            "receipt_id": receipt_id,
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "tenant_id": proposal["tenant_id"],
            "principal_id": principal_id,
            "run_id": proposal["run_id"],
            "command_type": proposal["command_type"],
            "idempotency_key": proposal["idempotency_key"],
            "request_hash": canonical_digest(
                {"proposal_digest": proposal["proposal_digest"], "confirmed": True}
            ),
            "outcome": approval["status"],
            "prior_run_status": run["status"],
            "resulting_run_status": run["status"],
            "resulting_run_state": run["state"],
            "active_graph_revision": int(run["active_graph_revision"]),
            "event_ids": {
                "command": event_id,
                "lifecycle": lifecycle["id"],
                "stopping_condition": None,
            },
            "acknowledgement": "exact_action_decision_recorded",
            "propagation_state": "runtime_propagation_not_certified",
            "completed_at": command["completed_at"],
            "action_id": action_id,
            "approval_command_id": command["command_id"],
            "approval_id": approval["approval_id"],
            "approval_envelope_digest": approval["envelope_digest"],
            "approval_sequence": approval["sequence"],
            "run_mode": run["run_mode"],
        }
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
        values = [receipt.get(k) for k in columns]
        for key, value in {
            "workflow_id": proposal["run_id"],
            "command_event_id": event_id,
            "lifecycle_event_id": lifecycle["id"],
            "stopping_event_id": None,
            "receipt_json": _json(receipt),
        }.items():
            values[columns.index(key)] = value
        conn.execute(
            f"INSERT INTO operator_action_review_receipts ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            values,
        )
        conn.commit()
        return {**receipt, "replayed": False}
    except Exception:
        conn.rollback()
        raise


def verify_review_receipt(row: sqlite3.Row) -> dict[str, Any]:
    receipt = json.loads(row["receipt_json"])
    digest = receipt.pop("receipt_digest", None)
    if (
        digest != row["receipt_digest"]
        or digest != canonical_digest(receipt)
        or receipt.get("contract") != REVIEW_RECEIPT_CONTRACT
    ):
        raise ValueError("action review receipt integrity failed")
    expected = {
        key: row[key]
        for key in (
            "receipt_id",
            "proposal_id",
            "tenant_id",
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
            "acknowledgement",
            "propagation_state",
            "completed_at",
        )
    }
    expected["run_id"] = row["workflow_id"]
    expected["event_ids"] = {
        "command": row["command_event_id"],
        "lifecycle": row["lifecycle_event_id"],
        "stopping_condition": row["stopping_event_id"],
    }
    if set(receipt) != set(expected) | {
        "contract",
        "action_id",
        "approval_command_id",
        "approval_id",
        "approval_envelope_digest",
        "approval_sequence",
        "run_mode",
    }:
        raise ValueError("action review receipt shape changed")
    if any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError("action review receipt columns changed")
    conn = get_connection()
    command = conn.execute(
        "SELECT * FROM approval_commands WHERE command_id = ? AND tenant_id = ? AND workflow_id = ?",
        (receipt["approval_command_id"], row["tenant_id"], row["workflow_id"]),
    ).fetchone()
    if command is None:
        raise ValueError("action review approval command is missing")
    result = json.loads(command["result_json"])
    result_hash = result.pop("result_hash", None)
    approval = result.get("approval", {})
    if (
        result_hash != command["result_hash"]
        or result_hash != canonical_digest(result)
        or receipt["action_id"] != command["action_id"]
        or receipt["principal_id"] != command["principal_id"]
        or receipt["command_type"] != command["command_type"]
        or receipt["idempotency_key"] != command["idempotency_key"]
        or command["principal_type"] != "human"
        or command["status"] != "committed"
        or receipt["outcome"]
        != {"approve": "approved", "reject": "rejected"}.get(receipt["command_type"])
        or receipt["approval_id"] != command["approval_id"]
        or receipt["approval_envelope_digest"] != approval.get("envelope_digest")
        or receipt["approval_sequence"] != approval.get("sequence")
        or receipt["outcome"] != approval.get("status")
    ):
        raise ValueError("action review receipt does not match approval authority")
    return {**receipt, "receipt_digest": digest}
