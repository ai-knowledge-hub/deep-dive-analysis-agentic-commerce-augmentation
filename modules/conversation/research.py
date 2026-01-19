"""Research agent scaffold for catalog gaps."""

from __future__ import annotations

from typing import Dict, List

from shared.llm.gateway import generate_with_tools
from shared.config.env import settings
from llm.tools import get_llm_tools, execute_tool


RESEARCH_PROMPT = """You are a catalog gap research agent.

Goal: Provide neutral discovery research when catalog data is thin.
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

    tool_schema = get_llm_tools()
    response = None
    try:
        if settings.llm_provider == "openrouter" and not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key missing")
        response = generate_with_tools(prompt=prompt, tools=tool_schema)
    except Exception as exc:
        response = {"text": "", "error": str(exc)}

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
        "insights": _build_insights(response),
    }


def _build_insights(response: Dict[str, object] | str) -> List[dict]:
    if isinstance(response, dict):
        text = str(response.get("content") or response.get("text") or "")
    else:
        text = str(response or "")

    lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    insights = []
    for idx, line in enumerate(lines):
        insights.append(
            {
                "id": f"research-{idx + 1}",
                "title": line if line else "Research insight",
                "summary": line,
                "confidence": 0.35,
                "source": "research",
            }
        )
    return insights


__all__ = ["run_research"]
