"""Lag-aware projection contract for authoritative completion decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from domain.workflow.outcome_serialization import completion_decision_digest
from domain.workflow.outcomes import (
    CompletionDecision,
    CompletionDisplayStatus,
    CompletionStatus,
    OutcomeContractError,
)


_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class CompletionProjection:
    """Operator-view cursor that cannot hide lag behind a terminal label."""

    decision_id: str
    decision_hash: str
    authoritative_status: CompletionStatus
    display_status: CompletionDisplayStatus
    decision_event_sequence: int
    authoritative_stream_sequence: int
    projected_event_sequence: int
    projected_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    @property
    def projection_lag(self) -> int:
        return self.authoritative_stream_sequence - self.projected_event_sequence

    @property
    def decision_lag(self) -> int:
        return self.authoritative_stream_sequence - self.decision_event_sequence

    def validate(self) -> None:
        _require_identifier("decision_id", self.decision_id)
        _require_digest("decision_hash", self.decision_hash)
        if type(self.authoritative_status) is not CompletionStatus:
            raise OutcomeContractError(
                "authoritative_status must be exact CompletionStatus"
            )
        if type(self.display_status) is not CompletionDisplayStatus:
            raise OutcomeContractError(
                "display_status must be exact CompletionDisplayStatus"
            )
        _require_nonnegative_int(
            "decision_event_sequence", self.decision_event_sequence
        )
        _require_nonnegative_int(
            "authoritative_stream_sequence", self.authoritative_stream_sequence
        )
        _require_nonnegative_int(
            "projected_event_sequence", self.projected_event_sequence
        )
        if self.decision_event_sequence > self.authoritative_stream_sequence:
            raise OutcomeContractError("decision cannot lead authoritative stream")
        if self.projected_event_sequence > self.authoritative_stream_sequence:
            raise OutcomeContractError("projection cannot lead authoritative events")
        expected = (
            CompletionDisplayStatus.STALE
            if self.projection_lag or self.decision_lag
            else CompletionDisplayStatus(self.authoritative_status.value)
        )
        if self.display_status is not expected:
            raise OutcomeContractError(
                "display status must expose projection lag or authoritative status"
            )
        object.__setattr__(
            self,
            "projected_at",
            _normalize_datetime("projected_at", self.projected_at),
        )


def project_completion(
    decision: CompletionDecision,
    *,
    decision_hash: str,
    authoritative_stream_sequence: int,
    projected_event_sequence: int,
    projected_at: datetime,
) -> CompletionProjection:
    """Create an operator projection that explicitly exposes stale state."""

    if type(decision) is not CompletionDecision:
        raise OutcomeContractError("decision must be CompletionDecision")
    decision.validate()
    _require_digest("decision_hash", decision_hash)
    if decision_hash != completion_decision_digest(decision):
        raise OutcomeContractError(
            "decision_hash must match the exact completion decision"
        )
    _require_nonnegative_int("projected_event_sequence", projected_event_sequence)
    _require_nonnegative_int(
        "authoritative_stream_sequence", authoritative_stream_sequence
    )
    if decision.authoritative_event_sequence > authoritative_stream_sequence:
        raise OutcomeContractError("decision cannot lead authoritative stream")
    if projected_event_sequence > authoritative_stream_sequence:
        raise OutcomeContractError("projection cannot lead authoritative stream")
    projected_at = _normalize_datetime("projected_at", projected_at)
    if projected_at < decision.evaluated_at:
        raise OutcomeContractError("projection cannot precede completion evaluation")
    display_status = (
        CompletionDisplayStatus.STALE
        if projected_event_sequence < authoritative_stream_sequence
        or decision.authoritative_event_sequence < authoritative_stream_sequence
        else CompletionDisplayStatus(decision.status.value)
    )
    return CompletionProjection(
        decision_id=decision.decision_id,
        decision_hash=decision_hash,
        authoritative_status=decision.status,
        display_status=display_status,
        decision_event_sequence=decision.authoritative_event_sequence,
        authoritative_stream_sequence=authoritative_stream_sequence,
        projected_event_sequence=projected_event_sequence,
        projected_at=projected_at,
    )


def _require_identifier(field_name: str, value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise OutcomeContractError(
            f"{field_name} must be a non-empty canonical exact string"
        )


def _require_digest(field_name: str, value: object) -> None:
    if type(value) is not str or _DIGEST_PATTERN.fullmatch(value) is None:
        raise OutcomeContractError(f"{field_name} must be a lowercase SHA-256 digest")


def _require_nonnegative_int(field_name: str, value: object) -> None:
    if type(value) is not int or value < 0:
        raise OutcomeContractError(
            f"{field_name} must be an exact non-negative integer"
        )


def _normalize_datetime(field_name: str, value: object) -> datetime:
    if type(value) is not datetime:
        raise OutcomeContractError(f"{field_name} must be exact datetime")
    if type(value.tzinfo) is not timezone or value.utcoffset() is None:
        raise OutcomeContractError(
            f"{field_name} must use immutable built-in fixed-offset timezone"
        )
    return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc)


__all__ = ["CompletionProjection", "project_completion"]
