"""Atomic durable evidence for locally committed governed effects."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from typing import Any, Dict, Mapping

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


_LAB_PROMOTION_CAPABILITY = "promote_variant_lab"


def commit_lab_promotion(
    *,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    approval_id: str,
    effect_idempotency_key: str,
    approval_effect_execution_id: str,
    experiment_id: str,
    variant_id: str,
    brand_id: str | None,
    product_id: str | None,
    reason: str,
    source_metric_id: str,
    posterior: Any,
    decision_action: str | None,
    promotion_tier: str,
    policy_version: str | None,
    uncertainty: float,
    expected_gain: float,
) -> Dict[str, Any]:
    """Commit both lab-promotion projections and their receipt as one effect."""

    identifiers = {
        "tenant_id": tenant_id,
        "workflow_id": workflow_id,
        "action_id": action_id,
        "approval_id": approval_id,
        "effect_idempotency_key": effect_idempotency_key,
        "approval_effect_execution_id": approval_effect_execution_id,
        "experiment_id": experiment_id,
        "variant_id": variant_id,
        "reason": reason,
        "source_metric_id": source_metric_id,
        "promotion_tier": promotion_tier,
    }
    for field, value in identifiers.items():
        _require_identifier(field, value)

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """
            SELECT * FROM governed_effect_receipts
            WHERE approval_effect_execution_id = ? AND tenant_id = ?
            """,
            (approval_effect_execution_id, tenant_id),
        ).fetchone()
        if existing is not None:
            receipt = _row(existing)
            _require_replay_match(
                receipt=receipt,
                workflow_id=workflow_id,
                action_id=action_id,
                approval_id=approval_id,
                effect_idempotency_key=effect_idempotency_key,
                experiment_id=experiment_id,
                variant_id=variant_id,
                reason=reason,
                source_metric_id=source_metric_id,
                posterior=posterior,
                decision_action=decision_action,
                decision_tier=promotion_tier,
                decision_policy_version=policy_version,
            )
            conn.rollback()
            return receipt

        effect = conn.execute(
            """
            SELECT * FROM approval_effect_executions
            WHERE execution_id = ? AND tenant_id = ? AND workflow_id = ?
              AND action_id = ? AND approval_id = ? AND effect_idempotency_key = ?
            """,
            (
                approval_effect_execution_id,
                tenant_id,
                workflow_id,
                action_id,
                approval_id,
                effect_idempotency_key,
            ),
        ).fetchone()
        if effect is None or effect["status"] not in {"started", "uncertain"}:
            raise ValueError(
                "lab-promotion receipt does not match an open effect start"
            )
        snapshot = from_json(effect["authorization_snapshot_json"], default={})
        capability = (
            snapshot.get("capability_contract") if type(snapshot) is dict else None
        )
        if (
            type(capability) is not dict
            or capability.get("name") != _LAB_PROMOTION_CAPABILITY
        ):
            raise ValueError("effect start is not authorized for lab promotion")

        analytics_event_id = str(uuid.uuid4())
        decision_event_id = str(uuid.uuid4())
        receipt_id = f"lab-promotion:{approval_effect_execution_id}"
        outputs = {
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "promotion_tier": "lab",
            "reason": reason,
            "source_metric_id": source_metric_id,
            "posterior": posterior,
            "decision_action": decision_action,
            "decision_tier": promotion_tier,
            "decision_policy_version": policy_version,
            "analytics_event_id": analytics_event_id,
            "decision_event_id": decision_event_id,
            "status": "variant_promoted_lab",
        }
        outputs_json = _canonical_json(outputs)
        outputs_hash = hashlib.sha256(outputs_json.encode("utf-8")).hexdigest()
        conn.execute(
            """
            INSERT INTO analytics_events (
                id, client_id, brand_id, product_id, variant_id, experiment_id,
                event_type, source, event_timestamp, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, 'variant_promoted_lab', 'agent_runtime',
                      NULL, json(?))
            """,
            (
                analytics_event_id,
                tenant_id,
                brand_id,
                product_id,
                variant_id,
                experiment_id,
                to_json(
                    {
                        "reason": reason,
                        "metric_id": source_metric_id,
                        "decision_action": decision_action,
                        "decision_tier": promotion_tier,
                        "posterior": posterior,
                        "policy_version": policy_version,
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO decision_events (
                id, client_id, brand_id, product_id, policy_action,
                uncertainty, expected_gain, selected_reason
            ) VALUES (?, ?, ?, ?, 'promote_variant_lab', ?, ?, ?)
            """,
            (
                decision_event_id,
                tenant_id,
                brand_id,
                product_id,
                uncertainty,
                expected_gain,
                reason,
            ),
        )
        conn.execute(
            """
            INSERT INTO governed_effect_receipts (
                receipt_id, tenant_id, workflow_id, action_id, approval_id,
                effect_idempotency_key, approval_effect_execution_id,
                capability_name, analytics_event_id, decision_event_id,
                outputs_json, outputs_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?), ?)
            """,
            (
                receipt_id,
                tenant_id,
                workflow_id,
                action_id,
                approval_id,
                effect_idempotency_key,
                approval_effect_execution_id,
                _LAB_PROMOTION_CAPABILITY,
                analytics_event_id,
                decision_event_id,
                outputs_json,
                outputs_hash,
            ),
        )
        row = conn.execute(
            "SELECT * FROM governed_effect_receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
        conn.commit()
        if row is None:  # pragma: no cover - guarded by the successful insert
            raise RuntimeError("lab-promotion receipt was not persisted")
        return _row(row)
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("lab-promotion effect commit conflicted") from exc
    except Exception:
        conn.rollback()
        raise


def get_receipt_for_effect_execution(
    *, approval_effect_execution_id: str, tenant_id: str
) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
        SELECT * FROM governed_effect_receipts
        WHERE approval_effect_execution_id = ? AND tenant_id = ?
        """,
            (approval_effect_execution_id, tenant_id),
        )
        .fetchone()
    )
    return _row(row) if row is not None else None


def _require_replay_match(*, receipt: Mapping[str, Any], **expected: Any) -> None:
    outputs = receipt.get("outputs")
    identity = {
        "workflow_id": receipt.get("workflow_id"),
        "action_id": receipt.get("action_id"),
        "approval_id": receipt.get("approval_id"),
        "effect_idempotency_key": receipt.get("effect_idempotency_key"),
        "experiment_id": outputs.get("experiment_id")
        if type(outputs) is dict
        else None,
        "variant_id": outputs.get("variant_id") if type(outputs) is dict else None,
        "reason": outputs.get("reason") if type(outputs) is dict else None,
        "source_metric_id": (
            outputs.get("source_metric_id") if type(outputs) is dict else None
        ),
        "posterior": outputs.get("posterior") if type(outputs) is dict else None,
        "decision_action": (
            outputs.get("decision_action") if type(outputs) is dict else None
        ),
        "decision_tier": (
            outputs.get("decision_tier") if type(outputs) is dict else None
        ),
        "decision_policy_version": (
            outputs.get("decision_policy_version") if type(outputs) is dict else None
        ),
    }
    if any(identity.get(field) != value for field, value in expected.items()):
        raise ValueError(
            "lab-promotion effect identity was replayed with different data"
        )


def _require_identifier(field: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{field} must be canonical non-empty text")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "receipt_id": row["receipt_id"],
        "tenant_id": row["tenant_id"],
        "workflow_id": row["workflow_id"],
        "action_id": row["action_id"],
        "approval_id": row["approval_id"],
        "effect_idempotency_key": row["effect_idempotency_key"],
        "approval_effect_execution_id": row["approval_effect_execution_id"],
        "capability_name": row["capability_name"],
        "analytics_event_id": row["analytics_event_id"],
        "decision_event_id": row["decision_event_id"],
        "outputs": from_json(row["outputs_json"], default={}),
        "outputs_hash": row["outputs_hash"],
        "created_at": row["created_at"],
    }


__all__ = ["commit_lab_promotion", "get_receipt_for_effect_execution"]
