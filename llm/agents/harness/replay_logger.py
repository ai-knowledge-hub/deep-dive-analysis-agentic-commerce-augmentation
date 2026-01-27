from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


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


class ReplayLogger:
    """Persist replay records via an injected persistence function."""

    def __init__(
        self,
        *,
        persist_fn: Callable[..., Dict[str, Any]],
    ) -> None:
        self._persist_fn = persist_fn

    def persist(
        self,
        *,
        run_type: str,
        record: ReplayRecord,
        client_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._persist_fn(
            run_type=run_type,
            record=record.to_dict(),
            client_id=client_id,
            user_id=user_id,
            session_id=session_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )


__all__ = ["ToolCall", "ReplayRecord", "ReplayLogger"]
