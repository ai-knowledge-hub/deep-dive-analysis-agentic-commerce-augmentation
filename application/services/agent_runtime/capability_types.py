from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CapabilityContext:
    client_id: str
    user_id: Optional[str]


class CapabilityExecutionError(ValueError):
    pass
