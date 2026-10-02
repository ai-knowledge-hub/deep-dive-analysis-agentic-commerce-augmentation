"""Canonical contracts for governed conversational operator commands."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


PROPOSAL_CONTRACT = "workflow.operator-command-proposal.v1"
RECEIPT_CONTRACT = "workflow.operator-command-receipt.v1"
PAUSE_COMMAND = "pause"
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


def build_pause_proposal(
    *,
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
        "contract": PROPOSAL_CONTRACT,
        "proposal_id": proposal_id,
        "tenant_id": _required("tenant_id", tenant_id),
        "principal_id": _required("principal_id", principal_id),
        "run_id": _required("run_id", run.get("id")),
        "command_type": PAUSE_COMMAND,
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
        "idempotency_key": f"operator-pause:{proposal_id}",
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
    }
    proposal = {**core, "proposal_digest": canonical_digest(core)}
    validate_pause_proposal(proposal)
    return proposal


def validate_pause_proposal(proposal: dict[str, Any]) -> None:
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
    if type(proposal) is not dict or set(proposal) != expected:
        raise OperatorCommandInvariantError(
            "operator command proposal shape is invalid"
        )
    if proposal.get("contract") != PROPOSAL_CONTRACT:
        raise OperatorCommandInvariantError(
            "operator command proposal contract is invalid"
        )
    if (
        proposal.get("command_type") != PAUSE_COMMAND
        or proposal.get("parameters") != {}
    ):
        raise OperatorCommandInvariantError(
            "operator command proposal is not an exact pause"
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
    if type(source) is not dict or set(source) != {
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
    }:
        raise OperatorCommandInvariantError("operator command source fence is invalid")
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
    if preflight["result"].get("command_type") != PAUSE_COMMAND:
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


def proposal_is_expired(
    proposal: dict[str, Any], *, now: datetime | None = None
) -> bool:
    validate_pause_proposal(proposal)
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
    "DEFAULT_PROPOSAL_TTL_SECONDS",
    "OperatorCommandConflictError",
    "OperatorCommandInvariantError",
    "PAUSE_COMMAND",
    "PROPOSAL_CONTRACT",
    "RECEIPT_CONTRACT",
    "build_pause_proposal",
    "canonical_digest",
    "proposal_is_expired",
    "validate_pause_proposal",
]
