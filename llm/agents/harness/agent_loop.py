from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from llm.agents.harness.replay_logger import ReplayRecord, ToolCall
from llm.agents.harness.tool_registry import ToolRegistry


@dataclass(frozen=True)
class ToolRunResult:
    model_response: dict
    tool_calls: List[dict]
    tool_outputs: List[dict]
    tool_call_records: List[ToolCall]
    elapsed_ms: Optional[int]


class AgentLoop:
    """Minimal agent harness loop (single-turn tool execution).

    This is intentionally small:
    - One LLM call with tool schema
    - Execute returned tool calls
    - Return tool outputs + structured ToolCall records for replay logging
    """

    def __init__(
        self,
        *,
        tools: Optional[ToolRegistry] = None,
        generate_with_tools_fn: Optional[Callable[..., dict]] = None,
    ) -> None:
        self.tools = tools or ToolRegistry()
        if generate_with_tools_fn is None:
            from infrastructure.llm.gateway import generate_with_tools as default_generate_with_tools

            self._generate_with_tools = default_generate_with_tools
        else:
            self._generate_with_tools = generate_with_tools_fn

    def run_tools_once(
        self,
        *,
        prompt: str,
        run_type: str,
        inputs: Dict[str, Any],
        versions: Dict[str, str],
    ) -> tuple[ToolRunResult, ReplayRecord]:
        tool_schema = self.tools.llm_schema()

        response: dict
        llm_call_ms: Optional[int] = None
        start = time.perf_counter()
        response = self._generate_with_tools(prompt=prompt, tools=tool_schema)
        llm_call_ms = int((time.perf_counter() - start) * 1000)

        tool_calls = (
            response.get("tool_calls", []) if isinstance(response, dict) else []
        )
        tool_outputs: List[dict] = []
        tool_call_records: List[ToolCall] = [
            ToolCall(
                name="generate_with_tools",
                arguments={"prompt_chars": len(prompt), "tool_count": len(tool_schema)},
                result_summary=f"tool_calls={len(tool_calls)}",
                elapsed_ms=llm_call_ms,
            )
        ]

        for call in tool_calls:
            name = call.get("name")
            args = call.get("args", {})
            execution = self.tools.execute_with_record(
                name or "tool", args if isinstance(args, dict) else {}
            )
            tool_outputs.append({"name": name, "output": execution.output})
            tool_call_records.append(execution.call)

        replay = ReplayRecord(
            run_type=run_type,
            inputs=inputs,
            outputs={
                "tool_calls": len(tool_calls),
                "tool_outputs": len(tool_outputs),
            },
            tool_calls=tool_call_records,
            versions=versions,
        )

        return (
            ToolRunResult(
                model_response=response,
                tool_calls=tool_calls,
                tool_outputs=tool_outputs,
                tool_call_records=tool_call_records,
                elapsed_ms=llm_call_ms,
            ),
            replay,
        )


__all__ = ["AgentLoop", "ToolRunResult"]
