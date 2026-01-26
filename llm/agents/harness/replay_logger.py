from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    result_summary: Optional[str] = None
    elapsed_ms: Optional[int] = None


@dataclass
class ReplayRecord:
    run_type: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    tool_calls: List[ToolCall] = field(default_factory=list)
    versions: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

