"""Compatibility shim: conversation research agent.

Canonical runner lives in `infrastructure.llm.research_agent`.

Important: tests monkeypatch `modules.conversation.research.generate_with_tools`, so
this wrapper injects the module-level symbols into the infrastructure runner.
"""

from __future__ import annotations

from typing import List

from infrastructure.llm.gateway import generate, generate_with_tools
from infrastructure.llm.research_agent import run_research as _run_research


RESEARCH_PROMPT = """You are a catalog gap research agent.

Goal: Provide neutral discovery research when catalog data is thin.
Return a concise bullet summary with citations, plus risks and uncertainty.
Never fabricate sources. If data is unavailable, say so explicitly.
"""


def run_research(
    query: str,
    goals: List[str],
    context: str | None = None,
    *,
    client_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    return _run_research(
        query=query,
        goals=goals,
        context=context,
        client_id=client_id,
        user_id=user_id,
        session_id=session_id,
        generate_fn=generate,
        generate_with_tools_fn=generate_with_tools,
        prompt_template=RESEARCH_PROMPT,
    )


__all__ = ["RESEARCH_PROMPT", "run_research"]

