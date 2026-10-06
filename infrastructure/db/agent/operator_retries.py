"""Atomic conversation receipts composed with the existing retry action creation."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

from domain.workflow.operator_commands import (
    OperatorCommandConflictError,
    RETRY_RECEIPT_CONTRACT,
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


def commit_retry(
    *,
    proposal: dict[str, Any],
    principal_id: str,
    confirmation_state: Callable[[], dict[str, Any]],
    create_action: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    validate_operator_proposal(proposal)
    if proposal["command_type"] != "retry" or principal_id != proposal["principal_id"]:
        raise OperatorCommandConflictError(
            "proposal_principal_mismatch",
            "Only the exact proposing human may confirm this retry.",
        )
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM operator_retry_proposals WHERE proposal_id = ? AND tenant_id = ? AND workflow_id = ?",
            (proposal["proposal_id"], proposal["tenant_id"], proposal["run_id"]),
        ).fetchone()
        if row is None:
            raise OperatorCommandConflictError(
                "proposal_not_found", "The retry proposal is unavailable."
            )
        stored = json.loads(row["proposal_json"])
        validate_operator_proposal(stored)
        _require_proposal_row_matches(row, stored)
        if stored != proposal:
            raise OperatorCommandConflictError(
                "proposal_changed", "The exact retry proposal changed."
            )
        # Access is checked again even for replay, before new decision eligibility.
        _require_active_principal(conn, proposal)
        membership = conn.execute(
            "SELECT 1 FROM client_users WHERE client_id = ? AND user_id = ? AND lower(trim(role)) IN ('owner', 'admin', 'operator')",
            (proposal["tenant_id"], principal_id.removeprefix("human:")),
        ).fetchone()
        if membership is None:
            raise OperatorCommandConflictError(
                "membership_inactive", "The operator no longer has retry authority."
            )
        replay = conn.execute(
            "SELECT * FROM operator_retry_receipts WHERE proposal_id = ?",
            (proposal["proposal_id"],),
        ).fetchone()
        if replay is not None:
            receipt = verify_retry_receipt(replay)
            conn.commit()
            return {**receipt, "replayed": True}
        if proposal_is_expired(proposal):
            raise OperatorCommandConflictError(
                "proposal_expired",
                "The retry expired. Review a fresh proposal.",
            )
        current = confirmation_state()
        _require_snapshot_digest(proposal, current.get("snapshot_digest"))
        if (
            current.get("preflight", {}).get("allowed") is not True
            or canonical_digest(current.get("preflight"))
            != proposal["preflight"]["digest"]
        ):
            raise OperatorCommandConflictError(
                "preflight_changed", "The retry conditions changed."
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
                "proposal_expired", "The retry expired during confirmation."
            )
        action = create_action()
        if not conn.in_transaction:
            raise RuntimeError("retry creation escaped the conversation transaction")
        plan = proposal["parameters"]["retry_plan"]
        source_id = proposal["parameters"]["action_id"]
        if (
            not action
            or action["agent_run_id"] != proposal["run_id"]
            or action["status"] != "proposed"
            or action["inputs"] != plan["normalized_inputs"]
            or action["inputs_hash"] != plan["inputs_hash"]
            or action["dedupe_key"]
            != f"retry:{source_id}:same_action:{action['retry_count']}"
            or action.get("approval_id")
            or action.get("validation_job_id")
            or action.get("outputs")
        ):
            raise RuntimeError("retry action does not match the exact proposal")
        lifecycle_id = str(uuid.uuid4())
        receipt_id, event_id = str(uuid.uuid4()), str(uuid.uuid4())
        completed_at = datetime.now(timezone.utc).isoformat()
        retry_identity = {
            "action_id": action["id"],
            "source_action_id": source_id,
            "retry_strategy": "same_action",
            "retry_count": action["retry_count"],
            "action_sequence": action["sequence"],
            "effect_idempotency_key": action["dedupe_key"],
            "inputs_hash": action["inputs_hash"],
            "capability_name": action["capability_name"],
        }
        anchors = {
            **retry_identity,
            "proposal_contract": proposal["contract"],
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "receipt_id": receipt_id,
            "idempotency_key": proposal["idempotency_key"],
        }
        for audit_id, event_type, status in (
            (event_id, "operator_command_retry", "completed"),
            (lifecycle_id, "action_retry_proposed", "proposed"),
        ):
            _insert_event(
                conn,
                event_id=audit_id,
                run_row=run,
                event_type=event_type,
                status=status,
                principal_id=principal_id,
                action=action,
                note="Operator confirmed creation of one proposed retry action.",
                anchors=anchors,
            )
        core = {
            "contract": RETRY_RECEIPT_CONTRACT,
            "receipt_id": receipt_id,
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "tenant_id": proposal["tenant_id"],
            "principal_id": principal_id,
            "run_id": proposal["run_id"],
            "command_type": "retry",
            "idempotency_key": proposal["idempotency_key"],
            "request_hash": canonical_digest(
                {"proposal_digest": proposal["proposal_digest"], "confirmed": True}
            ),
            "outcome": "proposed",
            "prior_run_status": run["status"],
            "resulting_run_status": run["status"],
            "resulting_run_state": run["state"],
            "active_graph_revision": int(run["active_graph_revision"]),
            "event_ids": {
                "command": event_id,
                "lifecycle": lifecycle_id,
                "stopping_condition": None,
            },
            "acknowledgement": "retry_action_proposed",
            "propagation_state": "runtime_propagation_not_certified",
            "completed_at": completed_at,
            "run_mode": run["run_mode"],
            **retry_identity,
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
            "lifecycle_event_id": lifecycle_id,
            "stopping_event_id": None,
            "receipt_json": _json(receipt),
        }.items():
            values[columns.index(key)] = value
        conn.execute(
            f"INSERT INTO operator_retry_receipts ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            values,
        )
        conn.commit()
        return {**receipt, "replayed": False}
    except Exception:
        conn.rollback()
        raise


def verify_retry_receipt(row: sqlite3.Row) -> dict[str, Any]:
    receipt = json.loads(row["receipt_json"])
    digest = receipt.pop("receipt_digest", None)
    if digest != row["receipt_digest"] or digest != canonical_digest(receipt):
        raise ValueError("retry receipt digest changed")
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
    expected.update(
        contract=RETRY_RECEIPT_CONTRACT,
        run_id=row["workflow_id"],
        event_ids={
            "command": row["command_event_id"],
            "lifecycle": row["lifecycle_event_id"],
            "stopping_condition": row["stopping_event_id"],
        },
    )
    extra = {
        "action_id",
        "source_action_id",
        "retry_strategy",
        "retry_count",
        "action_sequence",
        "effect_idempotency_key",
        "inputs_hash",
        "capability_name",
        "run_mode",
    }
    if set(receipt) != set(expected) | extra or any(
        receipt.get(k) != v for k, v in expected.items()
    ):
        raise ValueError("retry receipt shape or columns changed")
    conn = get_connection()
    proposal_row = conn.execute(
        "SELECT * FROM operator_retry_proposals WHERE proposal_id = ?",
        (receipt["proposal_id"],),
    ).fetchone()
    if proposal_row is None:
        raise ValueError("retry receipt proposal is missing")
    proposal = json.loads(proposal_row["proposal_json"])
    validate_operator_proposal(proposal)
    _require_proposal_row_matches(proposal_row, proposal)
    if (
        receipt["source_action_id"] != proposal["parameters"]["action_id"]
        or receipt["run_id"] != proposal["run_id"]
        or receipt["tenant_id"] != proposal["tenant_id"]
        or receipt["principal_id"] != proposal["principal_id"]
        or receipt["proposal_digest"] != proposal["proposal_digest"]
        or receipt["inputs_hash"] != proposal["parameters"]["retry_plan"]["inputs_hash"]
        or receipt["capability_name"]
        != proposal["parameters"]["retry_plan"]["capability_name"]
        or receipt["run_mode"] != proposal["source"]["run_mode"]
        or receipt["command_type"] != "retry"
        or receipt["outcome"] != "proposed"
        or receipt["retry_strategy"] != "same_action"
        or receipt["effect_idempotency_key"]
        != f"retry:{receipt['source_action_id']}:same_action:{receipt['retry_count']}"
    ):
        raise ValueError("retry receipt binding changed")
    for key, event_type, status in (
        ("command", "operator_command_retry", "completed"),
        ("lifecycle", "action_retry_proposed", "proposed"),
    ):
        event = conn.execute(
            "SELECT * FROM agent_events WHERE id = ?", (receipt["event_ids"][key],)
        ).fetchone()
        if event is None:
            raise ValueError("retry receipt audit is missing")
        anchors = json.loads(event["anchors_json"])
        if (
            event["agent_run_id"] != receipt["run_id"]
            or event["action_id"] != receipt["action_id"]
            or event["principal_id"] != receipt["principal_id"]
            or event["principal_type"] != "human"
            or event["event_type"] != event_type
            or event["status"] != status
            or any(anchors.get(k) != receipt[k] for k in extra - {"run_mode"})
            or anchors.get("proposal_digest") != receipt["proposal_digest"]
            or anchors.get("receipt_id") != receipt["receipt_id"]
        ):
            raise ValueError("retry receipt audit binding changed")
    return {**receipt, "receipt_digest": digest}


def active_retry_source_ids(*, tenant_id: str, workflow_id: str) -> frozenset[str]:
    """Hold only receipt-backed failures while their exact retry is undecided/in flight.

    Historical failure and completion membership remain unchanged. A finished,
    rejected or failed child stops holding its source; another failed action is
    never hidden merely because some retry exists in the run.
    """
    rows = (
        get_connection()
        .execute(
            "SELECT receipt.* FROM operator_retry_receipts receipt WHERE receipt.tenant_id = ? AND receipt.workflow_id = ? LIMIT 501",
            (tenant_id, workflow_id),
        )
        .fetchall()
    )
    if len(rows) > 500:
        raise ValueError("retry receipt state exceeds the confirmation safety bound")
    links = {}
    active = set()
    for row in rows:
        receipt = verify_retry_receipt(row)
        links[receipt["action_id"]] = receipt["source_action_id"]
        child = (
            get_connection()
            .execute(
                "SELECT status, inputs_hash, dedupe_key FROM agent_actions WHERE id = ? AND agent_run_id = ?",
                (receipt["action_id"], workflow_id),
            )
            .fetchone()
        )
        if (
            child
            and child["status"] in {"proposed", "approved", "executing"}
            and child["inputs_hash"] == receipt["inputs_hash"]
            and child["dedupe_key"] == receipt["effect_idempotency_key"]
        ):
            active.add(receipt["source_action_id"])
    for source in tuple(active):
        seen = set()
        while source in links and source not in seen:
            seen.add(source)
            source = links[source]
            active.add(source)
    return frozenset(active)
