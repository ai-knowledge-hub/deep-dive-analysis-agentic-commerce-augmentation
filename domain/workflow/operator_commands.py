"""Canonical contracts for governed conversational operator commands."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from domain.workflow.lifecycle import WorkflowStatus, require_workflow_transition


PROPOSAL_CONTRACT = "workflow.operator-command-proposal.v1"
RECEIPT_CONTRACT = "workflow.operator-command-receipt.v1"
PAUSE_COMMAND = "pause"
RESUME_COMMAND = "resume"
RESUME_PROPOSAL_CONTRACT = "workflow.operator-command-proposal.v2"
RESUME_RECEIPT_CONTRACT = "workflow.operator-command-receipt.v2"
RESUME_MODES = frozenset({"plan_only", "auto_execute_safe"})
CANCEL_COMMAND = "cancel"
CANCEL_PROPOSAL_CONTRACT = "workflow.operator-command-proposal.v3"
CANCEL_RECEIPT_CONTRACT = "workflow.operator-command-receipt.v3"
CANCEL_SOURCE_STATUSES = frozenset(
    {"created", "planning", "planned", "running", "paused"}
)
CANCEL_MODES = RESUME_MODES
DEFAULT_PROPOSAL_TTL_SECONDS = 300


class OperatorCommandInvariantError(ValueError):
    """Raised when a proposal or receipt fails its immutable contract."""


class OperatorCommandConflictError(RuntimeError):
    """Raised when a valid proposal no longer matches authoritative state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OperatorCommandCursorError(ValueError):
    """Raised when a command-history cursor is malformed or out of scope."""


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_proposal(
    *,
    command_type: str,
    tenant_id: str,
    principal_id: str,
    run: dict[str, Any],
    snapshot_digest: str,
    snapshot_cursor: str | None,
    latest_event: dict[str, Any] | None,
    preflight: dict[str, Any],
    now: datetime | None = None,
    ttl_seconds: int = DEFAULT_PROPOSAL_TTL_SECONDS,
) -> dict[str, Any]:
    issued = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires = issued + timedelta(seconds=max(30, int(ttl_seconds)))
    proposal_id = str(uuid.uuid4())
    core = {
        "contract": {
            PAUSE_COMMAND: PROPOSAL_CONTRACT,
            RESUME_COMMAND: RESUME_PROPOSAL_CONTRACT,
            CANCEL_COMMAND: CANCEL_PROPOSAL_CONTRACT,
        }[command_type],
        "proposal_id": proposal_id,
        "tenant_id": _required("tenant_id", tenant_id),
        "principal_id": _required("principal_id", principal_id),
        "run_id": _required("run_id", run.get("id")),
        "command_type": command_type,
        "parameters": {},
        "source": {
            "active_graph_revision": _positive_int(
                "active_graph_revision", run.get("active_graph_revision")
            ),
            "run_status": _required("run_status", run.get("status")),
            "run_state": _required("run_state", run.get("state")),
            "snapshot_digest": _digest("snapshot_digest", snapshot_digest),
            "snapshot_cursor": snapshot_cursor,
            "latest_event_id": (
                _required("latest_event_id", latest_event.get("id"))
                if latest_event
                else None
            ),
            "latest_event_timestamp": (
                _required("latest_event_timestamp", latest_event.get("timestamp"))
                if latest_event
                else None
            ),
            "harness_id": _optional(run.get("harness_id")),
            "policy_profile_id": _optional(run.get("policy_profile_id")),
            "registry_version": _optional(run.get("registry_version")),
            "registry_fingerprint": _optional(run.get("registry_fingerprint")),
        },
        "preflight": {
            "digest": canonical_digest(preflight),
            "result": preflight,
        },
        "idempotency_key": f"operator-{command_type}:{proposal_id}",
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
    }
    if command_type in {RESUME_COMMAND, CANCEL_COMMAND}:
        core["source"]["run_mode"] = run.get("run_mode")
        core["predicted_run_status"] = (
            cancel_target_status(run)
            if command_type == CANCEL_COMMAND
            else resume_target_status(run)
        )
    proposal = {**core, "proposal_digest": canonical_digest(core)}
    validate_operator_proposal(proposal)
    return proposal


def validate_operator_proposal(proposal: dict[str, Any]) -> None:
    expected = {
        "contract",
        "proposal_id",
        "tenant_id",
        "principal_id",
        "run_id",
        "command_type",
        "parameters",
        "source",
        "preflight",
        "idempotency_key",
        "issued_at",
        "expires_at",
        "proposal_digest",
    }
    resume = (
        isinstance(proposal, dict) and proposal.get("command_type") == RESUME_COMMAND
    )
    cancel = (
        isinstance(proposal, dict) and proposal.get("command_type") == CANCEL_COMMAND
    )
    if resume or cancel:
        expected.add("predicted_run_status")
    if type(proposal) is not dict or set(proposal) != expected:
        raise OperatorCommandInvariantError(
            "operator command proposal shape is invalid"
        )
    if proposal.get("contract") != (
        CANCEL_PROPOSAL_CONTRACT
        if cancel
        else RESUME_PROPOSAL_CONTRACT
        if resume
        else PROPOSAL_CONTRACT
    ):
        raise OperatorCommandInvariantError(
            "operator command proposal contract is invalid"
        )
    if (
        proposal.get("command_type")
        not in {PAUSE_COMMAND, RESUME_COMMAND, CANCEL_COMMAND}
        or proposal.get("parameters") != {}
    ):
        raise OperatorCommandInvariantError(
            "operator command proposal is not an exact supported command"
        )
    for field in (
        "proposal_id",
        "tenant_id",
        "principal_id",
        "run_id",
        "idempotency_key",
    ):
        _required(field, proposal.get(field))
    source = proposal.get("source")
    source_fields = {
        "active_graph_revision",
        "run_status",
        "run_state",
        "snapshot_digest",
        "snapshot_cursor",
        "latest_event_id",
        "latest_event_timestamp",
        "harness_id",
        "policy_profile_id",
        "registry_version",
        "registry_fingerprint",
    }
    if resume or cancel:
        source_fields.add("run_mode")
    if type(source) is not dict or set(source) != source_fields:
        raise OperatorCommandInvariantError("operator command source fence is invalid")
    if resume and proposal["predicted_run_status"] != resume_target_status(
        {"status": source["run_status"], "run_mode": source["run_mode"]}
    ):
        raise OperatorCommandInvariantError("resume outcome changed")
    if cancel and proposal["predicted_run_status"] != cancel_target_status(
        {"status": source["run_status"], "run_mode": source["run_mode"]}
    ):
        raise OperatorCommandInvariantError("cancel outcome changed")
    _positive_int("active_graph_revision", source.get("active_graph_revision"))
    _required("run_status", source.get("run_status"))
    _required("run_state", source.get("run_state"))
    _digest("snapshot_digest", source.get("snapshot_digest"))
    if (source.get("latest_event_id") is None) != (
        source.get("latest_event_timestamp") is None
    ):
        raise OperatorCommandInvariantError(
            "operator command event fence is incomplete"
        )
    preflight = proposal.get("preflight")
    if type(preflight) is not dict or set(preflight) != {"digest", "result"}:
        raise OperatorCommandInvariantError("operator command preflight is invalid")
    _digest("preflight digest", preflight.get("digest"))
    if preflight["digest"] != canonical_digest(preflight.get("result")):
        raise OperatorCommandInvariantError("operator command preflight digest changed")
    if not isinstance(preflight.get("result"), dict):
        raise OperatorCommandInvariantError(
            "operator command preflight result is invalid"
        )
    if preflight["result"].get("command_type") != proposal["command_type"]:
        raise OperatorCommandInvariantError("operator command preflight type changed")
    if preflight["result"].get("allowed") is not True:
        raise OperatorCommandInvariantError(
            "blocked operator command cannot be proposed"
        )
    issued = _timestamp("issued_at", proposal.get("issued_at"))
    expires = _timestamp("expires_at", proposal.get("expires_at"))
    if expires <= issued:
        raise OperatorCommandInvariantError(
            "operator command proposal expiry is invalid"
        )
    digest = _digest("proposal_digest", proposal.get("proposal_digest"))
    core = {key: value for key, value in proposal.items() if key != "proposal_digest"}
    if digest != canonical_digest(core):
        raise OperatorCommandInvariantError("operator command proposal digest changed")


def resume_target_status(run: dict[str, Any]) -> str:
    """Restrict the existing start mapping to an exactly paused source run.

    The sequential compatibility runtime returns planned for plan_only; this
    does not add a paused->planned edge to the portable workflow kernel.
    """
    if run.get("status") != "paused" or run.get("run_mode") not in RESUME_MODES:
        raise OperatorCommandInvariantError(
            "resume requires a paused run in a supported mode"
        )
    return "planned" if run["run_mode"] == "plan_only" else "running"


def build_pause_proposal(**kwargs: Any) -> dict[str, Any]:
    return _build_proposal(command_type=PAUSE_COMMAND, **kwargs)


def build_resume_proposal(**kwargs: Any) -> dict[str, Any]:
    return _build_proposal(command_type=RESUME_COMMAND, **kwargs)


def cancel_target_status(run: dict[str, Any]) -> str:
    if (
        run.get("status") not in CANCEL_SOURCE_STATUSES
        or run.get("run_mode") not in CANCEL_MODES
    ):
        raise OperatorCommandInvariantError(
            "cancel requires a nonterminal run in a supported mode"
        )
    require_workflow_transition(WorkflowStatus(run["status"]), WorkflowStatus.CANCELED)
    return "canceled"


def build_cancel_proposal(**kwargs: Any) -> dict[str, Any]:
    return _build_proposal(command_type=CANCEL_COMMAND, **kwargs)


def validate_pause_proposal(proposal: dict[str, Any]) -> None:
    validate_operator_proposal(proposal)
    if proposal["command_type"] != PAUSE_COMMAND:
        raise OperatorCommandInvariantError(
            "operator command proposal is not an exact pause"
        )


def proposal_is_expired(
    proposal: dict[str, Any], *, now: datetime | None = None
) -> bool:
    validate_operator_proposal(proposal)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return current >= _timestamp("expires_at", proposal["expires_at"])


def _required(field: str, value: Any) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > 512
    ):
        raise OperatorCommandInvariantError(f"{field} is invalid")
    return value


def _optional(value: Any) -> str | None:
    if value is None:
        return None
    return _required("optional identity", value)


def _positive_int(field: str, value: Any) -> int:
    if type(value) is not int or value < 1:
        raise OperatorCommandInvariantError(f"{field} is invalid")
    return value


def _digest(field: str, value: Any) -> str:
    text = _required(field, value)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise OperatorCommandInvariantError(f"{field} is invalid")
    return text


def _timestamp(field: str, value: Any) -> datetime:
    text = _required(field, value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OperatorCommandInvariantError(f"{field} is invalid") from exc
    if parsed.tzinfo is None:
        raise OperatorCommandInvariantError(f"{field} is invalid")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "CANCEL_COMMAND",
    "CANCEL_MODES",
    "CANCEL_SOURCE_STATUSES",
    "CANCEL_PROPOSAL_CONTRACT",
    "CANCEL_RECEIPT_CONTRACT",
    "DEFAULT_PROPOSAL_TTL_SECONDS",
    "OperatorCommandConflictError",
    "OperatorCommandInvariantError",
    "PAUSE_COMMAND",
    "PROPOSAL_CONTRACT",
    "RECEIPT_CONTRACT",
    "RESUME_COMMAND",
    "RESUME_MODES",
    "RESUME_PROPOSAL_CONTRACT",
    "RESUME_RECEIPT_CONTRACT",
    "build_pause_proposal",
    "build_resume_proposal",
    "build_cancel_proposal",
    "cancel_target_status",
    "canonical_digest",
    "proposal_is_expired",
    "resume_target_status",
    "validate_operator_proposal",
    "validate_pause_proposal",
]
