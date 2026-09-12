"""Trusted command and host-authority inputs for the outcome ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from domain.workflow.outcome_authority import HostCompletionAuthority
from domain.workflow.outcomes import OutcomeContractError


class OutcomeLedgerConflict(RuntimeError):
    """Raised when an immutable or idempotent ledger write conflicts."""


@dataclass(frozen=True)
class OutcomeLedgerCommand:
    """Authenticated host command metadata retained beside an artifact write."""

    command_id: str
    tenant_id: str
    workflow_id: str
    principal_id: str
    authority_source: str
    authority_version: str
    idempotency_key: str
    issued_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "command_id",
            "tenant_id",
            "workflow_id",
            "principal_id",
            "authority_source",
            "authority_version",
            "idempotency_key",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        object.__setattr__(self, "issued_at", _utc("issued_at", self.issued_at))

    def persistence_payload(self, command_type: str) -> dict[str, object]:
        _require_identifier("command_type", command_type)
        return {
            "command_id": self.command_id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "command_type": command_type,
            "principal_id": self.principal_id,
            "authority_source": self.authority_source,
            "authority_version": self.authority_version,
            "idempotency_key": self.idempotency_key,
            "issued_at": _format_utc(self.issued_at),
        }


def _require_identifier(field_name: str, value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise OutcomeContractError(
            f"{field_name} must be a non-empty canonical exact string"
        )


def _utc(field_name: str, value: object) -> datetime:
    if type(value) is not datetime:
        raise OutcomeContractError(f"{field_name} must be exact datetime")
    if type(value.tzinfo) is not timezone or value.utcoffset() is None:
        raise OutcomeContractError(
            f"{field_name} must use immutable built-in fixed-offset timezone"
        )
    return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "HostCompletionAuthority",
    "OutcomeLedgerCommand",
    "OutcomeLedgerConflict",
]
