"""Research agent scaffold for catalog gaps."""

from __future__ import annotations

from typing import List

from shared.llm.gateway import generate_with_tools
from llm.tools import get_function_declarations, execute_tool


RESEARCH_PROMPT = """You are a shopping research agent.

Goal: Provide neutral, empowerment-first research when catalog data is thin.
Return a concise bullet summary with citations, plus risks and uncertainty.
Never fabricate sources. If data is unavailable, say so explicitly.
"""


def run_research(query: str, goals: List[str], context: str | None = None) -> dict:
    """Generate a research bundle using MCP tools (web_fetch, etc.)."""
    context_block = f"\n\nSession context:\n{context}" if context else ""
    goal_block = "\n".join(f"- {goal}" for goal in goals) or "- (no explicit goals)"
    prompt = (
        f"{RESEARCH_PROMPT}{context_block}\n\n"
        f"User goals:\n{goal_block}\n\n"
        f"Research query: {query}\n\n"
        "Use tools if needed, then return:\n"
        "1) Summary bullets with citations\n"
        "2) Risks/uncertainties\n"
        "3) Suggested next clarifying question"
    )

    tool_schema = get_function_declarations()
    response = generate_with_tools(prompt=prompt, tools=tool_schema)

    tool_calls = response.get("tool_calls", []) if isinstance(response, dict) else []
    tool_outputs = []
    for call in tool_calls:
        name = call.get("name")
        args = call.get("args", {})
        tool_outputs.append({"name": name, "output": execute_tool(name, args)})

    return {
        "query": query,
        "goals": goals,
        "context_used": bool(context),
        "model_response": response,
        "tool_calls": tool_calls,
        "tool_outputs": tool_outputs,
    }


__all__ = ["run_research"]
