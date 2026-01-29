from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    func: Callable[..., Any]


class ToolExecutor:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def execute(self, name: str, **kwargs: Any) -> Any:
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Tool not registered: {name}")
        return tool.func(**kwargs)


__all__ = ["ToolExecutor", "ToolSpec"]
