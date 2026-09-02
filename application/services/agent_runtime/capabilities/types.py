from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CapabilityContext:
    client_id: str
    user_id: Optional[str]
    agent_action_id: Optional[str] = None
    approval_id: Optional[str] = None
    effect_idempotency_key: Optional[str] = None
    approval_effect_execution_id: Optional[str] = None


class CapabilityExecutionError(ValueError):
    pass
