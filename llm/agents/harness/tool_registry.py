from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from llm.agents.harness.replay_logger import ToolCall
from infrastructure.llm.tools import execute_tool, llm_schema


@dataclass(frozen=True)
class ToolExecution:
    output: dict
    call: ToolCall


class ToolRegistry:
    """Small adapter around `llm.tools`.

    Goals:
    - Provide a single place to build tool schemas for LLM calls.
    - Provide an execution surface that returns ToolCall records.
    """

    def llm_schema(self) -> List[dict]:
        return llm_schema()

    def execute(self, name: str, args: Dict[str, Any]) -> dict:
        return execute_tool(name, args)

    def execute_with_record(
        self,
        name: str,
        args: Dict[str, Any],
        *,
        elapsed_ms: Optional[int] = None,
    ) -> ToolExecution:
        start = time.perf_counter()
        output = self.execute(name, args)
        ms = (
            elapsed_ms
            if elapsed_ms is not None
            else int((time.perf_counter() - start) * 1000)
        )
        call = ToolCall(
            name=name or "tool",
            arguments=args if isinstance(args, dict) else {},
            result_summary="ok"
            if isinstance(output, dict) and not output.get("error")
            else "error",
            elapsed_ms=ms,
        )
        return ToolExecution(output=output, call=call)
