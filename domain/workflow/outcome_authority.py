"""Host-owned authority policy for durable workflow outcome writes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from domain.workflow.outcomes import (
    ContractAuthority,
    OutcomeContractError,
    ResultValidationAuthority,
)


_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class HostCompletionAuthority:
    """Trusted authority configured outside worker-controlled payloads."""

    publishing_authority: ContractAuthority
    criteria_authority_hash: str
    result_validation_authority: ResultValidationAuthority
    evaluation_authority: ContractAuthority

    def __post_init__(self) -> None:
        for name in ("publishing_authority", "evaluation_authority"):
            value = getattr(self, name)
            if type(value) is not ContractAuthority:
                raise OutcomeContractError(f"{name} must be exact ContractAuthority")
            value.validate()
        if type(self.result_validation_authority) is not ResultValidationAuthority:
            raise OutcomeContractError(
                "result_validation_authority must be exact ResultValidationAuthority"
            )
        self.result_validation_authority.validate()
        if (
            type(self.criteria_authority_hash) is not str
            or _DIGEST_PATTERN.fullmatch(self.criteria_authority_hash) is None
        ):
            raise OutcomeContractError(
                "criteria_authority_hash must be a lowercase SHA-256 digest"
            )


__all__ = ["HostCompletionAuthority"]
